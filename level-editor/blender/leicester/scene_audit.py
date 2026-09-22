"""Restore two omitted native Leicester components in a copied preflight scene.

Run with --baseline BLEND --level LEVEL_JSON --source-image PNG --patch-manifest
JSON --output DIRECTORY. The immutable imported baseline is never overwritten.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bootstrap import sha, dump, object_record
from refinement_inventory import inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'level', 'source-image', 'patch-manifest', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    original_sha = sha(args.baseline)
    bpy.ops.wm.open_mainfile(filepath=str(args.baseline.resolve()))
    bpy.context.window.scene = bpy.data.scenes['Leicester Refinement']
    collection = bpy.data.collections['Leicester Working']
    before = {o.name: object_record(o) for o in collection.all_objects}
    level = json.loads(args.level.read_text())
    patch_manifest = json.loads(args.patch_manifest.read_text())
    root = next(o for o in collection.all_objects if o.get('source_node') == 'map')
    material = bpy.data.materials.new('Leicester unprojected native geometry')
    material.diffuse_color = (0.45, 0.45, 0.45, 1)
    restored = []
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    for index, reason in [(273, 'Upper component clipped against removable covered-state component 277.'),
                          (342, 'Thin sloped roof component omitted by the volume minimum-height filter.')]:
        node = f'building-{index:03}'
        if any(o.get('source_node') == node for o in collection.all_objects):
            raise RuntimeError(f'Component already present: {node}')
        points = level['sight_obstacles'][index]['points']
        count = len(points)
        vertices = [(p['x'], -p['y'] / sine, p[z] / cosine)
                    for z in ('z_bottom', 'z_top') for p in points]
        faces = [tuple(reversed(range(count))), tuple(range(count, 2 * count))]
        faces += [(i, (i + 1) % count, (i + 1) % count + count, i + count) for i in range(count)]
        # Thin native wedges have coincident top/bottom corners; weld them and
        # discard collapsed sides rather than adding zero-area faces.
        unique = list(dict.fromkeys(vertices))
        remap = {index: unique.index(vertex) for index, vertex in enumerate(vertices)}
        clean_faces = []
        for face in faces:
            mapped = list(dict.fromkeys(remap[index] for index in face))
            if len(mapped) >= 3:
                clean_faces.append(tuple(mapped))
        vertices, faces = unique, clean_faces
        mesh = bpy.data.meshes.new(node + ' restored native volume')
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(node + ' restored', mesh)
        collection.objects.link(obj)
        world = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_world = world
        obj['source_node'] = obj['source_obstacle'] = node
        obj['source_export_node'] = 'absent from imported scene'
        obj['restoration_reason'] = reason
        obj['projection_status'] = 'unprojected; neutral pending reviewed ownership'
        mesh.materials.append(material)
        restored.append({'source_node': node, 'reason': reason, 'native_obstacle': level['sight_obstacles'][index]})
    state_pairs = []
    for patch in patch_manifest['patches']:
        if not (patch['sight_before'] and patch['sight_after']):
            continue
        state_pairs.append({'patch': patch['id'], 'name': patch['name'],
                            'initial_sight': patch['sight_before'], 'applied_sight': patch['sight_after'],
                            'render_visibility': 'unresolved: select and verify sprite endpoint artwork before hiding geometry'})
        for state, nodes in [('initial', patch['sight_before']), ('applied', patch['sight_after'])]:
            for node in nodes:
                obj = next(o for o in collection.all_objects if o.get('source_node') == node)
                obj['native_patch'] = patch['id']
                obj['native_sight_state'] = state
                obj['render_state_review'] = 'pending endpoint artwork review'
    bpy.context.view_layer.update()
    changes = []
    for name, record in before.items():
        after = object_record(bpy.data.objects[name])
        for key in ['geometry_sha256', 'uv_sha256', 'transform_sha256', 'hide_render', 'hide_viewport']:
            if record.get(key) != after.get(key):
                changes.append({'object': name, 'field': key})
    if changes:
        raise RuntimeError(f'Existing scene components changed: {changes}')
    scene_path = out / 'preflight.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(scene_path))
    result = inventory(out / 'inventory', collection_name=collection.name, map_name='Leicester',
                       source_path=args.source_image, patch_manifest=args.patch_manifest)
    dump(out / 'inventory' / 'complete-scene.json', {'version': 1, 'map': 'Leicester',
         'objects': [object_record(o) for o in sorted(bpy.context.scene.objects, key=lambda o: o.name)]})
    if sha(args.baseline) != original_sha:
        raise RuntimeError('Baseline hash changed')
    dump(out / 'validation.json', {'status': 'PASS', 'baseline_sha256': original_sha,
         'scene_sha256': sha(scene_path), 'native_level_sha256': sha(args.level),
         'script_sha256': sha(__file__), 'source_image_sha256': sha(args.source_image),
         'restored': restored, 'existing_geometry_uv_transform_visibility_changes': changes,
         'bridge_state_pairs': state_pairs, 'inventory': result,
         'limitations': ['Restored geometry is neutral and has no source projection yet.',
                        'Bridge alternatives remain visible until endpoint render ownership is reviewed. Sight activity is not rendering ownership.',
                        'Ground is a flat source-image receiver, not reconstructed terrain relief.']})
    scene_path.chmod(0o444)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
