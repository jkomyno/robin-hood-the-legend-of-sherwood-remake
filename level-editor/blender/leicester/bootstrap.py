"""Freeze an ungrouped Leicester checkpoint and comprehensive object inventory.

blender --background --python level-editor/blender/leicester/bootstrap.py -- \
  --source-image IMAGE --output level-editor/work/leicester-refinement/round-1

Existing output is rejected; all subsequent work must use copies of baseline.blend.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from setup_map import setup_map
from refinement_inventory import inventory


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def matrix(value):
    return [list(row) for row in value]


def properties(owner):
    result = {}
    for key in owner.keys():
        value = owner[key]
        if hasattr(value, 'to_dict'):
            value = value.to_dict()
        elif hasattr(value, 'to_list'):
            value = value.to_list()
        result[key] = value
    return result


def object_record(obj):
    record = {
        'object': obj.name, 'type': obj.type,
        'parent': obj.parent.name if obj.parent else None,
        'collections': sorted(c.name for c in obj.users_collection),
        'matrix_world': matrix(obj.matrix_world), 'matrix_local': matrix(obj.matrix_local),
        'matrix_parent_inverse': matrix(obj.matrix_parent_inverse),
        'hide_render': obj.hide_render, 'hide_viewport': obj.hide_viewport,
        'properties': properties(obj),
        'animation': {'action': obj.animation_data.action.name if obj.animation_data and obj.animation_data.action else None,
                      'nla_tracks': [track.name for track in obj.animation_data.nla_tracks] if obj.animation_data else []},
    }
    if obj.type == 'MESH':
        geometry = {'vertices': [list(v.co) for v in obj.data.vertices],
                    'edges': [list(e.vertices) for e in obj.data.edges],
                    'polygons': [list(p.vertices) for p in obj.data.polygons]}
        uv = {layer.name: [list(loop.uv) for loop in layer.data] for layer in obj.data.uv_layers}
        record.update(mesh=obj.data.name, geometry=geometry, uv_layers=uv,
                      geometry_sha256=digest(geometry), uv_sha256=digest(uv),
                      materials=[slot.material.name if slot.material else None for slot in obj.material_slots],
                      polygon_material_indices=[p.material_index for p in obj.data.polygons])
    if obj.type == 'CAMERA':
        record['camera'] = {'type': obj.data.type, 'ortho_scale': obj.data.ortho_scale,
                            'clip_start': obj.data.clip_start, 'clip_end': obj.data.clip_end,
                            'sensor_fit': obj.data.sensor_fit, 'shift_x': obj.data.shift_x, 'shift_y': obj.data.shift_y}
    record['transform_sha256'] = digest(record['matrix_world'])
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-image', required=True, type=Path)
    parser.add_argument('--metadata', type=Path, default=Path('level-editor/library/scenes/leicester-volumes.scene.json'))
    parser.add_argument('--patch-manifest', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / 'source'
    frozen.mkdir()
    sources = []
    for origin, name in [(args.metadata, 'leicester-volumes.scene.json'),
                         (args.metadata.with_suffix('.glb'), 'leicester-volumes.scene.glb'),
                         (args.source_image, 'source.png')]:
        origin = origin.resolve(strict=True)
        target = frozen / name
        shutil.copy2(origin, target)
        target.chmod(0o444)
        sources.append({'origin': str(origin), 'frozen': str(target), 'sha256': sha(target)})
    patch = None
    if args.patch_manifest:
        patch = frozen / 'patch-manifest.json'
        shutil.copy2(args.patch_manifest.resolve(strict=True), patch)
        patch.chmod(0o444)
        sources.append({'origin': str(args.patch_manifest.resolve()), 'frozen': str(patch), 'sha256': sha(patch)})
    bpy.ops.wm.read_factory_settings(use_empty=True)
    checkpoint = output / 'baseline.blend'
    result = setup_map(frozen / 'leicester-volumes.scene.json', checkpoint)
    working = bpy.data.collections['Leicester Working']
    for obj in working.all_objects:
        if 'source_obstacle' not in obj:
            raise ValueError(f'Missing source identity: {obj.name}')
        exported = obj['source_obstacle']
        obj['source_export_node'] = exported
        # Terrace mesh names retain the obstacle number used by the asset catalog.
        canonical = 'building-' + exported.removeprefix('terrace-') if exported.startswith('terrace-') else exported
        obj['source_obstacle'] = canonical
        obj['source_node'] = canonical
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint))
    report = inventory(output / 'inventory', collection_name=working.name, map_name='Leicester',
                       source_path=frozen / 'source.png', patch_manifest=patch)
    records = [object_record(obj) for obj in sorted(bpy.context.scene.objects, key=lambda item: item.name)]
    materials = []
    for material in sorted(bpy.data.materials, key=lambda item: item.name):
        materials.append({'name': material.name, 'diffuse_color': list(material.diffuse_color),
                          'use_nodes': material.use_nodes,
                          'image_nodes': [{'name': n.name, 'image': n.image.name if n.image else None}
                                          for n in material.node_tree.nodes if n.type == 'TEX_IMAGE'] if material.use_nodes else []})
    images = []
    for image in bpy.data.images:
        images.append({'name': image.name, 'size': list(image.size), 'filepath': image.filepath,
                       'packed_sha256': hashlib.sha256(image.packed_file.data).hexdigest() if image.packed_file else None})
    dump(output / 'inventory' / 'complete-scene.json', {
        'version': 1, 'map': 'Leicester', 'scene': bpy.context.scene.name,
        'baseline_sha256': sha(checkpoint), 'objects': records, 'materials': materials, 'images': images,
        'render': {'resolution': [bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y],
                   'resolution_percentage': bpy.context.scene.render.resolution_percentage,
                   'camera': bpy.context.scene.camera.name},
        'limitations': ['Imported atlas contains inferred fill and lossy JPEG pixels; use frozen source.png as pixel authority.',
                        'Native patch/state ownership must be reviewed separately; absence of imported animation is not proof of static behavior.']})
    dump(output / 'freeze-manifest.json', {'version': 1, 'map': 'Leicester', 'sources': sources,
         'baseline': str(checkpoint), 'baseline_sha256': sha(checkpoint), 'blender_version': bpy.app.version_string,
         'bootstrap_script_sha256': sha(__file__), 'arguments': sys.argv[sys.argv.index('--') + 1:],
         'inventory_sha256': sha(output / 'inventory' / 'inventory.json'),
         'complete_inventory_sha256': sha(output / 'inventory' / 'complete-scene.json')})
    checkpoint.chmod(0o444)
    print(json.dumps({'setup': result, 'inventory': report, 'freeze_manifest': str(output / 'freeze-manifest.json')}))


if __name__ == '__main__':
    main()
