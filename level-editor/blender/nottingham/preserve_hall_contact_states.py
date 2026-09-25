"""Append a source-baked roof contact to exact approved hall material states."""
import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'level-editor/work/nottingham-refinement'
sys.path[:0] = [str(ROOT / 'level-editor/refinement/blender'), str(Path(__file__).parent)]
EXTENSION = 'building-505__castle-hall-northwest-contact'
CONTEXT = 'Castle hall northwestern spire / Structural volume 519'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def signature(obj):
    """Bind physical mesh, UV coordinates, face assignments and packed source bytes."""
    materials = []
    for material in obj.data.materials:
        if material is None:
            materials.append(None)
            continue
        nodes = []
        for node in material.node_tree.nodes if material.use_nodes else []:
            entry = dict(name=node.name, type=node.bl_idname,
                         defaults={s.identifier: list(s.default_value) if hasattr(s.default_value, '__len__')
                                   and not isinstance(s.default_value, str) else s.default_value
                                   for s in node.inputs if hasattr(s, 'default_value')
                                   and isinstance(s.default_value, (float, int, str, bool)) or
                                   hasattr(s, 'default_value') and type(s.default_value).__name__ == 'bpy_prop_array'})
            if node.type == 'TEX_IMAGE' and node.image:
                image = node.image
                entry['image'] = dict(name=image.name, size=list(image.size),
                    packed_sha256=hashlib.sha256(bytes(image.packed_file.data)).hexdigest()
                    if image.packed_file else sha(image.filepath), interpolation=node.interpolation)
            if node.type == 'UVMAP':
                entry['uv_map'] = node.uv_map
            nodes.append(entry)
        materials.append(dict(name=material.name, diffuse=list(material.diffuse_color), nodes=nodes,
                              links=[(l.from_node.name, l.from_socket.identifier,
                                      l.to_node.name, l.to_socket.identifier)
                                     for l in material.node_tree.links] if material.use_nodes else []))
    payload = dict(matrix=[list(r) for r in obj.matrix_world],
                   vertices=[list(v.co) for v in obj.data.vertices],
                   faces=[(list(p.vertices), p.material_index, p.use_smooth) for p in obj.data.polygons],
                   uv=[dict(name=u.name, coords=[list(v.uv) for v in u.data]) for u in obj.data.uv_layers],
                   materials=materials)
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def promote_covered(new):
    """Promote verified covered materials without rerunning source baking."""
    import bpy
    from refinement_review import render_review
    from refinement_workspace import validate
    from audit_stored_materials import run
    from audit_spire_source_projection import exact_rgb
    old = WORK / 'round-42/assets/nottingham-castle-main-hall'
    manifest_path = new / 'inspection/state-models/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    state_hashes = {s['model']: sha(s['model']) for s in manifest['states']}
    covered = next(s for s in manifest['states'] if s['state'] == 'covered')
    proof = json.loads(Path(covered['preservation_report']).read_text())
    assert proof['status'] == 'PASS'
    assert sha(covered['model']) == covered['model_sha256'] == proof['model_sha256']
    config = json.loads((new / 'workspace.json').read_text())
    # Validate the intended primary before replacing any current review artifact.
    bpy.ops.wm.open_mainfile(filepath=covered['model'])
    validation = validate(new)
    before_sha = sha(new / 'model.blend')
    history = new / 'history/before-covered-state-promotion'
    history.mkdir(parents=True, exist_ok=False)
    for name in ['model.blend', 'modified', 'validation.json', 'known-rgb-validation.json', 'geometry-report.json']:
        if (new / name).exists():
            if name == 'model.blend' or name == 'geometry-report.json':
                shutil.copy2(new / name, history / name)
            else:
                (new / name).rename(history / name)
    if (new / 'inspection/stored-materials').exists():
        (new / 'inspection/stored-materials').rename(history / 'stored-materials')
    shutil.copy2(covered['model'], new / 'model.blend')
    bpy.ops.wm.open_mainfile(filepath=str(new / 'model.blend'))
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.get('asset_group') == config['asset_id']:
            obj.hide_render = False
    frames = json.loads((new / 'input/views.json').read_text())
    frames['render_object_names'] = sorted(covered['object_names'])
    layers = json.loads((old / 'projection-state-layers.json').read_text())['covered']
    layers[0].setdefault('receiver_components', []).append(dict(source_node='building-505',
        projection_components=['castle-hall-retained-roof', 'castle-hall-removable-cover',
                               'castle-hall-northwest-contact'], patch_id='patch-008'))
    render_review(new / 'modified', scene_name=config['scene_name'],
                  collection_name=config['collection_name'], asset_id=config['asset_id'],
                  source_path=config['source_path'], frame_manifest=frames,
                  projection_layers=layers, source_mask_manifest=config['source_mask_manifest'],
                  render_object_names=covered['object_names'],
                  allow_projection_revision=True, allow_mask_revision=True)
    run(new, new / 'inspection/stored-materials', render=True, export=False,
        render_object_names=covered['object_names'], frame_manifest=new / 'modified/views.json')
    exact_rgb(new)
    bpy.ops.wm.open_mainfile(filepath=str(new / 'model.blend'))
    write(new / 'validation.json', validate(new))
    assert state_hashes == {s['model']: sha(s['model']) for s in manifest['states']}
    manifest['primary_model_sha256'] = sha(new / 'model.blend')
    manifest['status'] = 'awaiting-independent-joint-review'
    write(manifest_path, manifest)
    report_path = new / 'geometry-report.json'
    report = json.loads(report_path.read_text())
    report['model_sha256'] = sha(new / 'model.blend')
    report['modified_views_sha256'] = sha(new / 'modified/views.json')
    report['covered_material_promotion'] = dict(previous_primary_sha256=before_sha,
        covered_state_sha256=covered['model_sha256'], state_models_unchanged=True,
        source_preservation_report=covered['preservation_report'])
    write(report_path, report)


def main():
    import bpy
    from render_slots import acquire
    from refinement_review import render_review
    from audit_stored_materials import run
    acquire(slots=2)
    new = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
    if '--promote-covered' in sys.argv:
        promote_covered(new)
        return
    old = WORK / 'round-42/assets/nottingham-castle-main-hall'
    original = json.loads((old / 'inspection/state-models/manifest.json').read_text())
    assert sha(old / 'model.blend') == original['primary_model_sha256']
    config = json.loads((new / 'workspace.json').read_text())
    state_layers = json.loads((old / 'projection-state-layers.json').read_text())
    records = []
    for state in original['states']:
        label = state['state']
        if '--state' in sys.argv and label != sys.argv[sys.argv.index('--state') + 1]:
            continue
        assert sha(state['model']) == state['model_sha256']
        bpy.ops.wm.open_mainfile(filepath=state['model'])
        owned = [o for o in bpy.data.objects if o.type == 'MESH' and o.get('asset_group') == config['asset_id']]
        before = {o.name: signature(o) for o in owned}
        with bpy.data.libraries.load(str(new / 'model.blend'), link=False) as (source, target):
            assert EXTENSION in source.objects and CONTEXT in source.objects
            target.objects = [EXTENSION, CONTEXT]
        extension, donor = target.objects
        bpy.data.collections[config['collection_name']].objects.link(extension)
        body = bpy.data.objects[CONTEXT]
        body.data = donor.data.copy()
        body.matrix_world = donor.matrix_world.copy()
        bpy.data.objects.remove(donor, do_unlink=True)
        assert extension.name == EXTENSION
        assert before == {o.name: signature(o) for o in owned}, 'Original hall source data changed'
        expected_extension = signature(extension)
        names = state['object_names'] + [EXTENSION]
        for o in owned + [extension]:
            o.hide_render = o.name not in names
        dest = new / 'inspection/state-models' / label
        dest.mkdir(parents=True, exist_ok=False)
        write(dest / 'workspace.json', config)
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(dest / 'model.blend'))
        bpy.ops.wm.open_mainfile(filepath=str(dest / 'model.blend'))
        after = {n: signature(bpy.data.objects[n]) for n in before}
        assert before == after and signature(bpy.data.objects[EXTENSION]) == expected_extension
        write(dest / 'source-preservation.json', dict(status='PASS', original_model_sha256=state['model_sha256'],
              model_sha256=sha(dest / 'model.blend'), original_owned_object_hashes=before,
              saved_owned_object_hashes=after, extension_hash=expected_extension,
              note='All original hall meshes, per-face materials, UV coordinates and packed image bytes unchanged.'))
        layers = copy.deepcopy(state_layers[label])
        if label == 'revealed':
            layers[0].setdefault('receiver_components', []).append(dict(source_node='building-505',
                projection_components=['castle-hall-retained-roof', 'castle-hall-removable-cover'], patch_id='patch-008'))
            exterior = copy.deepcopy(state_layers['covered'][0])
            exterior['receiver_nodes'] = ['building-505']
            exterior['occluder_nodes'] = layers[0]['occluder_nodes']
            exterior['receiver_components'] = [dict(source_node='building-505',
                projection_components=['castle-hall-northwest-contact'], patch_id='patch-008')]
            layers.append(exterior)
        for o in bpy.data.objects:
            if o.type == 'MESH' and o.get('asset_group') == config['asset_id']:
                o.hide_render = False
        diagnostic = new / 'states-contact/patch-008' / label
        source_path = state_layers[label][0]['source_path']
        frames = json.loads(Path(state['frame_manifest']).read_text())
        frames['render_object_names'] = sorted(names)
        render_review(diagnostic, scene_name=config['scene_name'], collection_name=config['collection_name'],
                      asset_id=config['asset_id'], source_path=source_path,
                      frame_manifest=frames, projection_layers=layers,
                      source_mask_manifest=config['source_mask_manifest'], render_object_names=names,
                      allow_projection_revision=True, allow_mask_revision=True)
        write(dest / 'modified/views.json', json.loads((diagnostic / 'views.json').read_text()))
        audit = run(dest, dest / 'actual', render=True, export=False, render_object_names=names,
                    frame_manifest=diagnostic / 'views.json')
        assert not audit['problems'], audit['problems']
        records.append(dict(state=label, model=str(dest / 'model.blend'), model_sha256=sha(dest / 'model.blend'),
                            object_names=names, frame_manifest=str(diagnostic / 'views.json'),
                            frame_manifest_sha256=sha(diagnostic / 'views.json'), actual=str(dest / 'actual/materials.png'),
                            preservation_report=str(dest / 'source-preservation.json')))
    write(new / ('inspection/state-models/manifest.json' if '--state' not in sys.argv
                 else f'inspection/state-models/{records[0]["state"]}-manifest.json'), dict(version=1,
          primary_model_sha256=sha(new / 'model.blend'), states=records, status='awaiting-independent-review'))


if __name__ == '__main__':
    main()
