"""Separate planar-background and native-plateau refinement packets.

Run inside a disposable Blender process; heavy packet work needs a render slot.
No terrain relief, water depth, or retaining-wall sculpt is inferred here.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def prepare_ground(root, workspace):
    import bpy
    import refinement_workspace as worker
    if workspace.exists():
        raise FileExistsError(workspace)
    source_blend = Path(bpy.data.filepath).resolve()
    bpy.context.window.scene = bpy.data.scenes['Leicester Refinement']
    collection = bpy.data.collections['Leicester Working']
    ground = [o for o in collection.all_objects if o.type == 'MESH' and o.get('source_node') == 'ground']
    if len(ground) != 1:
        raise RuntimeError('Expected one separately inventoried background plane')
    obj = ground[0]
    obj['asset_group'] = 'leicester-ground-background'
    obj['asset_name'] = 'Planar Background Artwork'
    config = dict(version=1, asset_id='leicester-ground-background',
                  scene_name='Leicester Refinement', collection_name='Leicester Working', map_name='Leicester',
                  width=384, height=256, elevation_degrees=35.0, context_padding=0, framing_padding=1.04,
                  source_blend=str(source_blend), source_blend_sha256=sha(source_blend),
                  grouping_manifest_sha256=None, projection_manifest=None, part_ids=['ground'],
                  terrain_role='Explicit separate planar background; excluded from building catalog')
    workspace.mkdir(parents=True)
    reference = workspace / 'reference'
    reference.mkdir()
    shutil.copy2(root / 'layers/covered.png', reference / 'source.png')
    shutil.copy2(root / 'catalog/state-and-terrain.json', reference / 'state-and-terrain.json')
    config['source_path'] = str(reference / 'source.png')
    masks = json.loads((root / 'terrain-inspection/ownership-v2/source-masks.json').read_text())
    masks['mask_inventory'] = str(root / 'terrain-inspection/ownership-v2/inventory.json')
    dump(workspace / 'source-masks.json', masks)
    config['source_mask_manifest'] = str(workspace / 'source-masks.json')
    worker._freeze_masks(workspace, config)
    targets, outside = worker._ownership(config)
    config['outside_geometry'] = outside
    for mesh in worker._objects(config):
        mesh.hide_select = mesh not in targets
        mesh.select_set(mesh in targets)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'baseline.blend'), copy=True)
    config['baseline_sha256'] = sha(workspace / 'baseline.blend')
    # The source-only packet checks actual source visibility and ownership. The
    # old ground atlas is frozen in baseline and is not accepted as evidence.
    worker._render(config, workspace / 'input')
    config['input_files'] = worker._files(workspace / 'input')
    config['reference_files'] = worker._files(reference)
    dump(workspace / 'workspace.json', config)
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
    (workspace / 'INSTRUCTIONS.md').write_text('Own only source_node ground. Preserve all other geometry. This separate terrain packet uses source-only masked pixels; no terrain heightfield or physical foliage is reconstructed. Geometry approval remains pending.\n')
    return config


def terrace_geometry(root, workspace):
    import bpy
    import bmesh
    from mathutils import Vector
    import refinement_workspace as worker
    config = json.loads((workspace / 'workspace.json').read_text())
    targets, _ = worker._ownership(config)
    if len(targets) != 1 or targets[0].get('source_node') != 'building-123':
        raise RuntimeError('Expected only the native lower-bailey plateau')
    obj = targets[0]
    if obj.get('terrain_recipe') == 'native-flat-terrace-v1':
        return {'reused': True, 'source_node': 'building-123'}
    level_path = root / 'source-audit/Leicester.rhp.json'
    points = json.loads(level_path.read_text())['sight_obstacles'][123]['points']
    if max(p['z_top'] for p in points)-min(p['z_top'] for p in points) > 1e-4:
        raise RuntimeError('Expected constant native terrace elevation')
    matrix = obj.matrix_world.copy()
    inverse = matrix.inverted()
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    vertices = [inverse @ Vector((p['x'], -p['y']/sine, p[z]/cosine))
                for z in ('z_bottom', 'z_top') for p in points]
    n = len(points)
    faces = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
    faces += [(i, (i+1) % n, (i+1) % n+n, i+n) for i in range(n)]
    mesh = bpy.data.meshes.new('Native flat lower-bailey terrace')
    mesh.from_pydata(vertices, [], faces)
    for material in obj.data.materials:
        mesh.materials.append(material)
    mesh.uv_layers.new(name='Projection pending')
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # Keep the native concave outline; triangulate planar caps without a hull.
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bad = sum(not e.is_manifold for e in bm.edges)
    degenerate = sum(f.calc_area() < 1e-8 for f in bm.faces)
    if bad or degenerate:
        bm.free()
        raise RuntimeError(f'Terrace topology invalid: {bad=}, {degenerate=}')
    bm.to_mesh(mesh)
    bm.free()
    before = worker._geometry(obj)
    obj.data = mesh
    obj['terrain_recipe'] = 'native-flat-terrace-v1'
    if obj.matrix_world != matrix:
        raise RuntimeError('Terrace transform changed')
    return {'source_node': 'building-123', 'native_points': n, 'native_height': points[0]['z_top'],
            'vertices': len(mesh.vertices), 'faces': len(mesh.polygons), 'nonmanifold_edges': bad,
            'degenerate_faces': degenerate, 'before': before, 'after': worker._geometry(obj),
            'transform_drift': 0, 'level_sha256': sha(level_path),
            'limitations': ['Only native constant-height plateau and its boundary retained.',
                            'Retaining sides remain neutral; no new wall or sculpted relief inferred.']}


def ground_projection(root, workspace):
    import bpy
    import numpy as np
    from PIL import Image
    config = json.loads((workspace / 'workspace.json').read_text())
    objects = [o for o in bpy.data.collections['Leicester Working'].all_objects
               if o.type == 'MESH' and o.get('source_node') == 'ground']
    if len(objects) != 1:
        raise RuntimeError('Expected one background plane')
    obj = objects[0]
    output = workspace / 'projection/background'
    prior = output / 'ownership.json'
    mask_path = root / 'terrain-inspection/ownership-v2/ground.png'
    if obj.get('terrain_background_source') == sha(config['source_path']) and obj.get('terrain_background_mask') == sha(mask_path):
        if not prior.exists():
            raise RuntimeError('Background recipe marker has no ownership report')
        return {**json.loads(prior.read_text()), 'reused': True}
    source = np.array(Image.open(config['source_path']).convert('RGB'))
    mask = np.array(Image.open(mask_path).convert('L')) > 0
    protected = np.full_like(source, 115)
    protected[mask] = source[mask]
    output.mkdir(parents=True, exist_ok=True)
    texture = output / 'source-protected.png'
    Image.fromarray(protected).save(texture)
    material = bpy.data.materials.new('Source-protected planar background')
    material.use_nodes = True
    material['projection_preserve'] = True
    nodes = material.node_tree.nodes
    nodes.clear()
    result = nodes.new('ShaderNodeOutputMaterial')
    emission = nodes.new('ShaderNodeEmission')
    image_node = nodes.new('ShaderNodeTexImage')
    image_node.image = bpy.data.images.load(str(texture), check_existing=False)
    image_node.image.pack()
    image_node.interpolation = 'Closest'
    image_node.extension = 'CLIP'
    material.node_tree.links.new(image_node.outputs['Color'], emission.inputs['Color'])
    material.node_tree.links.new(emission.outputs[0], result.inputs['Surface'])
    obj.data = obj.data.copy()
    obj.data.materials.clear()
    obj.data.materials.append(material)
    fallback = obj.data.attributes.get('reprojection_fallback_material')
    if fallback is not None:
        for entry in fallback.data:
            entry.value = 0
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name='Source projection')
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    height, width = mask.shape
    for face in obj.data.polygons:
        face.material_index = 0
        for loop in face.loop_indices:
            p = obj.matrix_world @ obj.data.vertices[obj.data.loops[loop].vertex_index].co
            uv.data[loop].uv = (p.x/width, 1-(-p.y*sine-p.z*cosine)/height)
    report = {'source_node': 'ground', 'geometry_changed': False, 'source_sha256': sha(config['source_path']),
              'mask_sha256': sha(mask_path), 'texture_sha256': sha(texture),
              'accepted_pixels': int(mask.sum()), 'unknown_pixels': int((~mask).sum()),
              'source_rgb_mismatch': int(np.any(protected[mask] != source[mask], axis=1).sum()),
              'unknown_value': [115, 115, 115], 'role': 'planar background artwork, not physical terrain'}
    dump(output / 'ownership.json', report)
    obj['terrain_background_source'] = report['source_sha256']
    obj['terrain_background_mask'] = report['mask_sha256']
    return report


def main():
    import bpy
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--kind', choices=('terrace', 'ground'), required=True)
    parser.add_argument('--phase', choices=('prepare', 'refine'), required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    root, workspace = args.root.resolve(), args.workspace.resolve()
    sys.path.insert(0, str(root.parents[1] / 'blender'))
    import refinement_workspace as worker
    if args.phase == 'prepare':
        if args.kind == 'ground':
            prepare_ground(root, workspace)
        else:
            worker.prepare(workspace, asset_id='leicester-lower-bailey-terrace',
                           scene_name='Leicester Refinement', collection_name='Leicester Working',
                           source_path=str(root / 'layers/covered.png'),
                           grouping_manifest=str(root / 'catalog/catalog.json'),
                           inventory_path=str(root / 'round-1/preflight/inventory/inventory.json'),
                           review_path=str(root / 'catalog/grouping-review.json'),
                           source_mask_manifest=str(root / 'terrain-inspection/ownership-v2/source-masks.json'),
                           width=384, height=256)
        return
    if Path(bpy.data.filepath).resolve() != workspace / 'model.blend':
        raise RuntimeError('Open worker model.blend; never edit frozen source')
    before = worker.validate(workspace)
    report = terrace_geometry(root, workspace) if args.kind == 'terrace' else ground_projection(root, workspace)
    worker.validate(workspace)
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
    dump(workspace / 'terrain-report.json', report)
    worker.modified(workspace)
    shutil.copy2(__file__, workspace / 'recipe.py')
    ownership = (workspace / 'projection/background/ownership.json' if args.kind == 'ground' else
                 max((p for p in (workspace / 'projection').glob('*/ownership.json')
                      if p.parent.name != 'input'), key=lambda p: p.stat().st_mtime_ns))
    dump(workspace / 'handoff.json', {'status': 'validation-pending', 'all_eight_views_inspected': False,
                                    'recipe': 'recipe.py', 'ownership': str(ownership.relative_to(workspace)),
                                    'geometry_approval': 'pending', 'texture_generation': 'not-started',
                                    'role': args.kind, 'outside_validation': before,
                                    'notes': report.get('limitations', ['Planar background evidence only; no recovered terrain relief.'])})


if __name__ == '__main__':
    main()
