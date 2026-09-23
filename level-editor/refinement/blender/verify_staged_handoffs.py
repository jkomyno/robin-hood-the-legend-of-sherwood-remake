"""Compare staged meshes to approved sources and untouched baseline by content.

Run in Blender with -- <resolved-publication-plan.json>. Ignores display names
and parent names, which catalog reconciliation legitimately changes; checks
world geometry, visibility, UVs, material graph values and packed image bytes.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import bpy


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def snapshot(collection_name, include_values=False):
    images, materials = {}, {}
    def material(mat):
        if mat is None:
            return None
        if mat.as_pointer() in materials:
            return materials[mat.as_pointer()]
        nodes = []
        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                image = getattr(node, 'image', None)
                sha = None
                if image:
                    if image.as_pointer() not in images:
                        if not image.packed_file:
                            raise ValueError('Unpacked publication image: ' + image.name)
                        images[image.as_pointer()] = hashlib.sha256(image.packed_file.data).hexdigest()
                    sha = images[image.as_pointer()]
                values = []
                for socket in node.inputs:
                    if hasattr(socket, 'default_value'):
                        value = socket.default_value
                        if not isinstance(value, (str, float, int, bool)):
                            try:
                                value = list(value)
                            except TypeError:
                                continue
                        values.append((socket.name, value))
                nodes.append((node.name, node.type, sha, getattr(node, 'uv_map', None),
                              getattr(node, 'interpolation', None), values))
            links = sorted((l.from_node.name, l.from_socket.name, l.to_node.name, l.to_socket.name)
                           for l in mat.node_tree.links)
        else:
            links = []
        value = digest([nodes, links, list(mat.diffuse_color), mat.use_backface_culling])
        materials[mat.as_pointer()] = value
        return value
    records = []
    for obj in bpy.data.collections[collection_name].all_objects:
        if obj.type != 'MESH':
            continue
        slots = [material(mat) for mat in obj.data.materials]
        value = {'vertices': [[round(c, 5) for c in obj.matrix_world @ v.co] for v in obj.data.vertices],
                 'faces': [list(p.vertices) for p in obj.data.polygons],
                 'materials': [slots[p.material_index] if slots else None for p in obj.data.polygons],
                 'uv': {layer.name: [list(entry.uv) for entry in layer.data] for layer in obj.data.uv_layers},
                 'visibility': [obj.hide_render, obj.hide_viewport],
                 'modifiers': [(m.name, m.type, m.show_render, m.show_viewport) for m in obj.modifiers]}
        record = {'name': obj.name, 'source': obj.get('source_node'),
                  'group': obj.get('asset_group'), 'hidden': obj.hide_render, 'sha256': digest(value)}
        if include_values:
            record['value'] = value
        records.append(record)
    return records


def signatures(records):
    return Counter((r['source'], r['sha256']) for r in records)


def compare_handoff(expected, actual, tolerance=0.001):
    """Reparenting can round float32 matrices by a fraction of a source pixel."""
    if len(expected) != len(actual):
        raise ValueError('Handoff mesh count changed')
    remaining = list(actual)
    maximum = 0.0
    for before in expected:
        left = dict(before['value'])
        vertices = left.pop('vertices')
        matches = []
        for after in remaining:
            right = dict(after['value'])
            candidate = right.pop('vertices')
            if before['source'] != after['source'] or left != right or len(vertices) != len(candidate):
                continue
            drift = max((abs(a-b) for va, vb in zip(vertices, candidate) for a, b in zip(va, vb)), default=0)
            matches.append((drift, after))
        if not matches:
            raise ValueError('Handoff topology, appearance or visibility changed: ' + before['name'])
        drift, match = min(matches, key=lambda pair: pair[0])
        if drift > tolerance:
            raise ValueError('Handoff world geometry drift: ' + before['name'] + ' ' + str(drift))
        remaining.remove(match)
        maximum = max(maximum, drift)
    return maximum


def verify(plan_path):
    plan = json.loads(Path(plan_path).read_text())
    expected = {}
    for item in plan['imports']:
        bpy.ops.wm.open_mainfile(filepath=item['blend_path'])
        records = snapshot(plan['collection_name'], True)
        selected = [r for r in records if not r['hidden'] and r['source'] in item['source_nodes']
                    and r['group'] == item.get('source_asset_id', item['asset_id'])]
        if not selected:
            raise ValueError('Empty handoff: ' + item['asset_id'])
        expected[item['asset_id']] = selected
    expected_ground = None
    if plan.get('ground_texture_handoff'):
        bpy.ops.wm.open_mainfile(filepath=plan['ground_texture_handoff']['blend_path'])
        expected_ground = [r for r in snapshot(plan['collection_name'], True)
                           if r['source'] == 'ground' and not r['hidden']]
        if len(expected_ground) != 1:
            raise ValueError('Ground handoff must have exactly one visible receiver')
    scopes = {item['asset_id']: set(item['source_nodes']) for item in plan['imports']}
    imported_ground = any(nodes == {'ground'} for nodes in scopes.values())
    def selected(record):
        return not record['hidden'] and (record['source'] in scopes.get(record['group'], set())
                                        or ((expected_ground is not None or imported_ground) and record['source'] == 'ground'))
    bpy.ops.wm.open_mainfile(filepath=plan['baseline'])
    before = [r for r in snapshot(plan['collection_name']) if not selected(r)]
    bpy.ops.wm.open_mainfile(filepath=str(Path(plan['output']) / 'worker.blend'))
    records = snapshot(plan['collection_name'], True)
    after = [r for r in records if not selected(r)]
    if signatures(before) != signatures(after):
        raise ValueError('Unimported baseline mesh geometry or appearance changed')
    reports = []
    for asset_id, wanted in expected.items():
        actual = [r for r in records if selected(r) and r['group'] == asset_id]
        drift = compare_handoff(wanted, actual)
        reports.append({'asset_id': asset_id, 'meshes': len(actual), 'content_matches_handoff': True,
                        'maximum_world_coordinate_drift': drift})
    if expected_ground is not None:
        actual_ground = [r for r in records if r['source'] == 'ground' and not r['hidden']]
        drift = compare_handoff(expected_ground, actual_ground)
        reports.append({'asset_id': 'ground-cleanup', 'meshes': 1, 'content_matches_handoff': True,
                        'maximum_world_coordinate_drift': drift})
    report = {'status': 'PASS', 'outside_meshes_preserved': len(before), 'imports': reports,
              'comparison': 'World geometry within 0.001 units; exact topology, UVs, assigned material graphs, packed image bytes, visibility. Untouched mesh content exact.'}
    output = Path(plan['output']) / 'handoff-verification.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    verify(sys.argv[sys.argv.index('--') + 1])
