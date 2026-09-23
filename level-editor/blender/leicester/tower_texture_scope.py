"""Derive exterior write scope and guard untouched tower interior face materials."""
import hashlib
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'refinement/blender'))
from verify_staged_handoffs import snapshot


def capture(manifest, labels=('exterior',), displayed_names=None):
    records = {r['name']: r['value'] for r in snapshot(manifest['collection_name'], True)}
    labels = set(labels)
    if not labels:
        raise ValueError('Receiver labels cannot be empty')
    displayed = set(displayed_names) if displayed_names is not None else None
    exterior, interior = {}, {}
    for name in manifest['object_names']:
        obj = bpy.data.objects[name]
        if obj.type != 'MESH':
            continue
        for face in obj.data.polygons:
            mat = obj.data.materials[face.material_index]
            label = mat.get('source_ownership_label') if mat else None
            if label in labels and (displayed is None or name in displayed):
                exterior.setdefault(name, []).append(face.index)
            elif label:
                record = records[name]
                interior.setdefault(name, {})[str(face.index)] = {
                    'label': label, 'material': record['materials'][face.index],
                    'vertices': list(face.vertices),
                    'uv': {uv: [coords[i] for i in face.loop_indices]
                           for uv, coords in record['uv'].items()}}
            else:
                raise ValueError(f'Unexpected receiver material label: {name} face {face.index}: {label}')
    return exterior, interior


def verify(manifest, before):
    records = {r['name']: r['value'] for r in snapshot(manifest['collection_name'], True)}
    count = 0
    for name, faces in before.items():
        obj = bpy.data.objects[name]
        for index, expected in faces.items():
            face = obj.data.polygons[int(index)]
            actual = records[name]
            if actual['materials'][int(index)] != expected['material']:
                raise ValueError(f'Interior material changed: {name} face {index}')
            if list(face.vertices) != expected['vertices']:
                raise ValueError(f'Interior topology changed: {name} face {index}')
            for layer, coords in expected['uv'].items():
                if layer not in actual['uv'] or [actual['uv'][layer][i] for i in face.loop_indices] != coords:
                    raise ValueError(f'Interior UV changed: {name} face {index} / {layer}')
            count += 1
    return {'materials_preserved': True, 'interior_faces_verified': count,
            'method': 'Original per-face material graph and packed atlas hashes, polygon vertices, and all existing UV coordinates compared exactly.'}


def prepare(experiment):
    experiment = Path(experiment)
    path = experiment/'views.json'
    manifest = json.loads(path.read_text())
    bpy.ops.wm.open_mainfile(filepath=str(experiment/'approved-model.blend'))
    exterior, interior = capture(manifest)
    manifest['texture_receiver_object_names'] = sorted(exterior)
    manifest['texture_receiver_face_indices'] = exterior
    manifest['texture_projection_labels'] = ['exterior']
    manifest['texture_material_suffix'] = 'wave2-generated-exterior'
    path.write_text(json.dumps(manifest, indent=2)+'\n')
    report = {'source_blend_sha256': hashlib.sha256((experiment/'approved-model.blend').read_bytes()).hexdigest(),
              'exterior_faces': sum(map(len, exterior.values())), 'interior_faces': interior}
    (experiment/'interior-preservation-before.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'experiment': str(experiment), 'exterior_faces': report['exterior_faces'],
                      'interior_faces': sum(map(len, interior.values()))}), flush=True)


if __name__ == '__main__':
    for argument in sys.argv[sys.argv.index('--')+1:]:
        prepare(argument)
