"""Prove that tree fold-in workspaces keep the approved owned geometry (Blender, render slot).

    /usr/bin/blender --background --threads 2 --python-exit-code 1 \
        --python level-editor/blender/lincoln/terrain_foldin_geometry.py -- <out.json> <old-ws> <new-ws> [...]

For each (old, new) workspace pair, hashes every owned mesh (asset_group == asset id) by
source node: world-space vertices, faces, UV-free. Writes one JSON record per pair.
"""
import hashlib
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_slots import acquire  # noqa: E402


def owned(workspace):
    config = json.loads((Path(workspace) / 'workspace.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(Path(workspace) / 'model.blend'))
    result = {}
    for obj in bpy.data.collections[config['collection_name']].all_objects:
        if obj.type != 'MESH' or obj.get('asset_group') != config['asset_id']:
            continue
        payload = {'vertices': [[round(c, 4) for c in obj.matrix_world @ v.co] for v in obj.data.vertices],
                   'faces': [list(p.vertices) for p in obj.data.polygons], 'hide_render': obj.hide_render}
        key = f"{obj.get('source_node')}|{obj.get('projection_component')}|{obj.name}"
        result[key] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return config['asset_id'], result


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    acquire()
    out, pairs = Path(args[0]), args[1:]
    records = []
    for old, new in zip(pairs[::2], pairs[1::2]):
        asset_old, before = owned(old)
        asset_new, after = owned(new)
        records.append({'asset_id': asset_new, 'old_workspace': old, 'new_workspace': new,
                        'same_asset': asset_old == asset_new, 'owned_meshes': len(after),
                        'geometry_identical': before == after,
                        'differences': sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))})
    out.write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps([(r['asset_id'], r['geometry_identical']) for r in records]))


if __name__ == '__main__':
    main()
