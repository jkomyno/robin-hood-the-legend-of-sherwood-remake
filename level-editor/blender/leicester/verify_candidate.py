"""Record effective mesh, UV and fixed-camera validation for a worker candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import bmesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from refinement_workspace import validate


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def verify(workspace):
    report = validate(workspace)
    config = json.loads((workspace / 'workspace.json').read_text())
    records = []
    for obj in bpy.data.collections[config['collection_name']].all_objects:
        if obj.type != 'MESH' or obj.get('asset_group') != config['asset_id']:
            continue
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        nonmanifold = sum(not e.is_manifold for e in bm.edges)
        degenerate = sum(f.calc_area() < 1e-8 for f in bm.faces)
        bm.free()
        records.append({'object': obj.name, 'source_node': obj['source_node'],
                        'vertices': len(obj.data.vertices), 'faces': len(obj.data.polygons),
                        'nonmanifold_edges': nonmanifold, 'degenerate_faces': degenerate,
                        'geometry_sha256': digest({'vertices': [list(v.co) for v in obj.data.vertices],
                                                  'faces': [list(f.vertices) for f in obj.data.polygons]}),
                        'uv_sha256': digest({u.name: [list(v.uv) for v in u.data] for u in obj.data.uv_layers}),
                        'transform_sha256': digest([list(row) for row in obj.matrix_world])})
    before = json.loads((workspace / 'input/views.json').read_text())
    after = json.loads((workspace / 'modified/views.json').read_text())
    if len(before['views']) != 8 or len(after['views']) != 8:
        raise ValueError('Expected eight before and after views')
    for a, b in zip(before['views'], after['views']):
        for key in ('index', 'camera_matrix_world', 'ortho_scale'):
            if a[key] != b[key]:
                raise ValueError('Frozen camera changed')
    if before['context_crop'] != after['context_crop'] or before['source_sha256'] != after['source_sha256']:
        raise ValueError('Source crop or artwork changed')
    if any(r['nonmanifold_edges'] or r['degenerate_faces'] for r in records):
        raise ValueError('Candidate still contains open or degenerate geometry')
    report.update(mesh_validation=records, fixed_cameras='PASS', source_and_crop='PASS',
                  model_sha256=hashlib.sha256((workspace / 'model.blend').read_bytes()).hexdigest())
    (workspace / 'geometry-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    verify(args.workspace.resolve(strict=True))
