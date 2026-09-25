"""Compare every approved Lincoln worker model with the grouped scene it would publish from.

blender --background --threads 2 --python level-editor/blender/lincoln/verify_publication_scene.py -- \
    <gallery-progress.json> <scene.blend> <report.json> [scene collection]

For each approved asset, the visible meshes owned by the asset (asset_group) in its approved
model.blend are compared to the scene's visible meshes of the same asset, keyed by
source node and projection component (grouping renames meshes): world-space vertices
(tolerance 1e-3), topology, UV layers, face material indices, and material identity by node graph
plus packed image content hashes. Read-only; writes only the report.
"""
import hashlib
import json
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_slots import acquire

COLLECTION = 'lincoln Working'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def image_hash(image, cache):
    key = image.name
    if key not in cache:
        if image.packed_file:
            cache[key] = hashlib.sha256(image.packed_file.data).hexdigest()
        else:
            cache[key] = 'external:' + bpy.path.abspath(image.filepath)
    return cache[key]


def material_identity(material, cache):
    if material is None:
        return None
    if not material.use_nodes:
        return ['no-nodes', list(material.diffuse_color)]
    nodes = sorted([node.type, getattr(node, 'uv_map', None) or '',
                    image_hash(node.image, cache) if node.type == 'TEX_IMAGE' and node.image else '']
                   for node in material.node_tree.nodes)
    links = sorted([link.from_node.type, link.from_socket.identifier, link.to_node.type, link.to_socket.identifier]
                   for link in material.node_tree.links)
    return hashlib.sha256(json.dumps([nodes, links, material.blend_method if hasattr(material, 'blend_method') else '']).encode()).hexdigest()


def mesh_record(obj, cache):
    mesh = obj.data
    n = len(mesh.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    mesh.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    m = np.array(obj.matrix_world, dtype=np.float64)
    world = co @ m[:3, :3].T + m[:3, 3]
    loops = np.empty(len(mesh.loops), dtype=np.int64)
    mesh.loops.foreach_get('vertex_index', loops)
    totals = np.empty(len(mesh.polygons), dtype=np.int64)
    mesh.polygons.foreach_get('loop_total', totals)
    mats = np.empty(len(mesh.polygons), dtype=np.int64)
    mesh.polygons.foreach_get('material_index', mats)
    uvs = {}
    for layer in mesh.uv_layers:
        data = np.empty(len(mesh.loops) * 2, dtype=np.float32)
        layer.data.foreach_get('uv', data)
        uvs[layer.name] = hashlib.sha256(data.tobytes()).hexdigest()
    return {
        'world': world,
        'topology': hashlib.sha256(loops.tobytes() + b'|' + totals.tobytes()).hexdigest(),
        'face_materials': hashlib.sha256(mats.tobytes()).hexdigest(),
        'uv': uvs,
        'materials': [material_identity(mat, cache) for mat in mesh.materials],
        'source_node': obj.get('source_node'),
        'projection_component': obj.get('projection_component'),
        'hide_render': obj.hide_render,
    }


def owned(asset_id, cache, collection_name=COLLECTION):
    """Key meshes by canonical identity; grouping renames meshes after the catalog part names."""
    collection = bpy.data.collections[collection_name]
    records = [(o.name, mesh_record(o, cache)) for o in collection.all_objects
               if o.type == 'MESH' and not o.hide_render and o.get('asset_group') == asset_id]
    keyed = {}
    for name, record in sorted(records, key=lambda item: (str(item[1]['source_node']),
                                                          str(item[1]['projection_component']),
                                                          item[1]['topology'], len(item[1]['world']))):
        base = f"{record['source_node']}|{record['projection_component'] or ''}"
        index = sum(1 for key in keyed if key.rsplit('#', 1)[0] == base)
        record['name'] = name
        keyed[f'{base}#{index}'] = record
    return keyed


def compare(model, scene):
    issues = []
    if set(model) != set(scene):
        issues.append({'missing_in_scene': sorted(set(model) - set(scene)),
                       'extra_in_scene': sorted(set(scene) - set(model))})
    drift = 0.0
    for name in sorted(set(model) & set(scene)):
        a, b = model[name], scene[name]
        for key in ('topology', 'face_materials', 'uv', 'materials', 'source_node', 'projection_component'):
            if a[key] != b[key]:
                issues.append({'mesh': name, 'field': key})
        if a['world'].shape != b['world'].shape:
            issues.append({'mesh': name, 'field': 'vertex_count'})
        else:
            d = float(np.abs(a['world'] - b['world']).max()) if len(a['world']) else 0.0
            drift = max(drift, d)
            if d > 1e-3:
                issues.append({'mesh': name, 'field': 'world_vertices', 'max_abs': d})
    return issues, drift


def main(progress_path, scene_path, report_path, scene_collection=COLLECTION):
    acquire()
    progress = json.loads(Path(progress_path).read_text())
    approved = [row for row in progress['assets'] if row['status'] == 'approved']
    scene_hash = sha(scene_path)
    bpy.ops.wm.open_mainfile(filepath=str(Path(scene_path).resolve()))
    cache = {}
    scene_records = {row['id']: owned(row['id'], cache, scene_collection) for row in approved}
    results = []
    for row in approved:
        model_path = Path(row['workspace']) / 'model.blend'
        model_hash = sha(model_path)
        bpy.ops.wm.open_mainfile(filepath=str(model_path))
        cache = {}
        model_records = owned(row['id'], cache)
        issues, drift = compare(model_records, scene_records[row['id']])
        results.append({'asset_id': row['id'], 'model': str(model_path), 'model_sha256': model_hash,
                        'meshes': len(model_records), 'max_world_drift': drift,
                        'mesh_names': {key: [model_records[key]['name'], scene_records[row['id']].get(key, {}).get('name')]
                                       for key in model_records},
                        'match': not issues, 'issues': issues})
        print('VERIFIED', row['id'], 'MATCH' if not issues else 'DIFF ' + json.dumps(issues)[:300], flush=True)
    report = {'version': 1, 'scene': str(Path(scene_path).resolve()), 'scene_sha256': scene_hash,
              'progress': str(Path(progress_path).resolve()), 'progress_sha256': sha(progress_path),
              'tolerance': 1e-3, 'matched': sum(r['match'] for r in results),
              'mismatched': [r['asset_id'] for r in results if not r['match']], 'assets': results}
    Path(report_path).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'matched': report['matched'], 'mismatched': report['mismatched']}), flush=True)


if __name__ == '__main__':
    main(*sys.argv[sys.argv.index('--') + 1:])
