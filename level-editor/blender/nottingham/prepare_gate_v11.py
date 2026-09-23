"""Prepare fresh V11 gate packets while preserving the previously refined meshes."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'level-editor/work/nottingham-refinement'
ARCH = 'nottingham-south-gate-arch'
TOWER = 'nottingham-south-gate-east-tower'
sys.path.insert(0, str(Path(__file__).parent))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key(obj):
    return (obj.get('source_node'), obj.get('projection_component', ''))


def geometry(obj):
    return {'vertices': [list(v.co) for v in obj.data.vertices],
            'faces': [list(p.vertices) for p in obj.data.polygons],
            'matrix': [list(row) for row in obj.matrix_world]}


def capture(path, asset_id):
    """Evaluate and capture world coordinates before changing scenes or parents."""
    import bpy
    bpy.ops.wm.open_mainfile(filepath=str(path))
    bpy.context.view_layer.update()
    result = {}
    for obj in bpy.data.collections['nottingham Working'].all_objects:
        if obj.type != 'MESH' or obj.hide_render or obj.get('asset_group') != asset_id:
            continue
        if any(modifier.show_viewport or modifier.show_render for modifier in obj.modifiers):
            raise ValueError(('Apply source modifiers before geometry transfer', obj.name))
        item = key(obj)
        if item in result:
            raise ValueError(('Duplicate source receiver', item))
        matrix = obj.matrix_world.copy()
        result[item] = {
            'name': obj.name,
            'world_vertices': [list(matrix @ v.co) for v in obj.data.vertices],
            'faces': [list(p.vertices) for p in obj.data.polygons],
            'uv_layers': {layer.name: [list(v.uv) for v in layer.data]
                          for layer in obj.data.uv_layers},
            'projection_properties': {
                k: obj[k] for k in obj.keys()
                if k.startswith('projection_') and k != 'projection_component'},
            'source_matrix_world': [list(row) for row in matrix],
            'source_blend': str(path), 'source_blend_sha256': sha(path)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset', choices=[ARCH, TOWER], required=True)
    parser.add_argument('--output-round', type=int, default=15)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    from render_slots import acquire
    acquire()
    from freeze_tooling import select_tooling
    tooling = select_tooling(WORK / 'tooling/58744eeaf71a21e9')
    import bpy
    from mathutils import Vector
    import refinement_review
    from refinement_workspace import prepare, modified

    workspace = WORK / f'round-{args.output_round}/assets' / args.asset
    if workspace.exists():
        raise FileExistsError(workspace)
    sources = {ARCH: WORK / 'round-14/assets' / ARCH,
               TOWER: WORK / 'round-13/assets' / TOWER}
    protected_files = {str(directory / 'model.blend'): sha(directory / 'model.blend')
                       for directory in sources.values()}
    tower = capture(sources[TOWER] / 'model.blend', TOWER)
    if args.asset == ARCH:
        imports = capture(sources[ARCH] / 'model.blend', ARCH)
        if set(imports) != {(f'building-{n}', '') for n in (205, 213, 214)}:
            raise ValueError(('Unexpected refined arch receivers', list(imports)))
        imports[('building-212', '')] = tower[('building-212', '')]
    else:
        imports = {k: value for k, value in tower.items() if k[0] != 'building-212'}
    mask_source = sources[args.asset] / 'source-masks.json'
    masks = json.loads(mask_source.read_text())
    if args.asset == ARCH:
        tower_masks = json.loads((sources[TOWER] / 'source-masks.json').read_text())
        pier = next(a for a in tower_masks['projections']['exterior']['assignments']
                    if a.get('source_node') == 'building-212')
        # The reviewed arch already uses this same native129 assignment. Check
        # the two inventories before preserving the pier assignment explicitly.
        for index in pier['mask_indices']:
            paths = []
            for document in (masks, tower_masks):
                inventory = Path(document['mask_inventory'])
                record = next(m for m in json.loads(inventory.read_text())['masks']
                              if m['index'] == index)
                paths.append(inventory.parent / record['png'])
            if sha(paths[0]) != sha(paths[1]):
                raise ValueError(('Native pier mask changed', index))
        assignments = masks['projections']['exterior']['assignments']
        matches = [i for i, a in enumerate(assignments)
                   if a.get('source_node') == 'building-212']
        if len(matches) != 1:
            raise ValueError('Expected exactly one exterior pier assignment')
        assignments[matches[0]] = copy.deepcopy(pier)
    provenance = WORK / 'gate-membership-v11'
    provenance.mkdir(exist_ok=True)
    mask_path = provenance / f'{args.asset}-source-masks.json'
    if mask_path.exists() and json.loads(mask_path.read_text()) != masks:
        raise ValueError('Existing gate membership mask authority differs')
    mask_path.write_text(json.dumps(masks, indent=2) + '\n')

    grouped = WORK / 'grouped/nottingham-grouped-v11.blend'
    evidence = grouped.with_suffix('.evidence')
    protected_files[str(grouped)] = sha(grouped)
    bpy.ops.wm.open_mainfile(filepath=str(grouped))
    bpy.context.view_layer.update()
    collection = bpy.data.collections['nottingham Working']
    # Imported partition artifacts can lack their neutral material slot.
    neutral = bpy.data.materials.new('V11 gate unknown neutral')
    neutral.diffuse_color = (.45, .45, .45, 1)
    for obj in collection.all_objects:
        if obj.type == 'MESH' and not obj.data.materials:
            obj.data.materials.append(neutral)
    targets = {key(o): o for o in collection.all_objects
               if o.type == 'MESH' and not o.hide_render and o.get('asset_group') == args.asset}
    if set(targets) != set(imports):
        raise ValueError(('V11 target/import membership mismatch', list(targets), list(imports)))
    outside = {o.name: geometry(o) for o in collection.all_objects
               if o.type == 'MESH' and o not in targets.values()}
    planned = [Vector(p) for record in imports.values() for p in record['world_vertices']]
    original_fit = refinement_review.fit_camera

    def fit(*positional, **kwargs):
        kwargs['points'] = list(kwargs['points']) + planned
        return original_fit(*positional, **kwargs)

    refinement_review.fit_camera = fit
    config = json.loads((sources[args.asset] / 'workspace.json').read_text())
    try:
        prepared = prepare(
            workspace, asset_id=args.asset, scene_name='nottingham Refinement',
            collection_name='nottingham Working', source_path=WORK / 'source-states/covered.png',
            grouping_manifest=evidence / 'catalog.json', inventory_path=evidence / 'inventory.json',
            review_path=evidence / 'grouping-review.json', source_mask_manifest=mask_path,
            width=config['width'], height=config['height'], context_padding=50,
            framing_padding=1.15)
    finally:
        refinement_review.fit_camera = original_fit
    rows = []
    for identity, target in targets.items():
        record = imports[identity]
        matrix = target.matrix_world.copy()
        inverse = matrix.inverted()
        mesh = bpy.data.meshes.new(target.name + ' / preserved refined geometry')
        mesh.from_pydata([inverse @ Vector(p) for p in record['world_vertices']], [], record['faces'])
        mesh.update()
        for name, coordinates in record['uv_layers'].items():
            layer = mesh.uv_layers.new(name=name)
            if len(layer.data) != len(coordinates):
                raise ValueError(('UV loop count changed', target.name, name))
            for value, uv in zip(layer.data, coordinates):
                value.uv = uv
        mesh.materials.append(neutral)
        target.data = mesh
        for name, value in record['projection_properties'].items():
            target[name] = value
        maximum = max((matrix @ v.co - Vector(p)).length
                      for v, p in zip(mesh.vertices, record['world_vertices']))
        if maximum > .001 or target.matrix_world != matrix:
            raise ValueError(('Imported world geometry drift', target.name, maximum))
        rows.append({'source_node': identity[0], 'projection_component': identity[1],
                     'source_blend': record['source_blend'],
                     'source_blend_sha256': record['source_blend_sha256'],
                     'source_matrix_world': record['source_matrix_world'],
                     'maximum_world_vertex_drift': maximum,
                     'vertices': len(mesh.vertices), 'faces': len(mesh.polygons)})
    if outside != {o.name: geometry(o) for o in collection.all_objects
                   if o.type == 'MESH' and o not in targets.values()}:
        raise ValueError('Outside geometry changed during import')
    imported = {o.name: geometry(o) for o in targets.values()}
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
    validation = modified(workspace)
    if imported != {o.name: geometry(o) for o in targets.values()}:
        raise ValueError('Projection changed imported geometry')
    for path, expected in protected_files.items():
        if sha(path) != expected:
            raise ValueError(('Source or grouped baseline changed', path))
    report = {'status': 'PASS', 'grouping_revision': 11, 'asset_id': args.asset,
              'tooling': tooling, 'source_imports': rows, 'source_files': protected_files,
              'outside_geometry_preserved': len(outside), 'post_projection_geometry_preserved': True,
              'prepared': prepared, 'validation': validation,
              'model_sha256': sha(workspace / 'model.blend'),
              'modified_views_sha256': sha(workspace / 'modified/views.json'),
              'scope': 'Move existing refined pier212 into the arch. Preserve all imported refined geometry.'}
    (workspace / 'membership-revision.json').write_text(json.dumps(report, indent=2) + '\n')
    candidate = {'version': 1, 'asset_id': args.asset, 'status': 'fix-needed',
                 'geometry_refined': True, 'geometry_reviewed': False, 'inspected_views': [],
                 'recipe': str(Path(__file__).resolve()), 'recipe_sha256': sha(__file__),
                 'model_sha256': report['model_sha256'],
                 'modified_views_sha256': report['modified_views_sha256'],
                 'changes': [report['scope'], 'Fresh V11 baseline and matched eight-view source projection.'],
                 'limitations': ['Standalone framing and pier/crown source alignment await visual review.',
                                 'Concealed backs and pre-existing inferred depth remain unknown.'],
                 'approval': 'pending', 'texture_generation': 'not-started',
                 'membership_evidence': 'membership-revision.json'}
    (workspace / 'candidate.json').write_text(json.dumps(candidate, indent=2) + '\n')
    (workspace / 'review.md').write_text('# Gate membership revision\n\n' + report['scope'] +
                                       '\n\nFresh V11 packet awaits all-eight-view review.\n')
    print('V11_GATE_PACKET_COMPLETE', args.asset, report['model_sha256'], flush=True)


if __name__ == '__main__':
    main()
