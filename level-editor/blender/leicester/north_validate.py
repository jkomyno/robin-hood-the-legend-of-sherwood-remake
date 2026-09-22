"""Read-only geometry/UV checks for the church courtyard-contact candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import bmesh


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def capture(asset):
    result = {}
    for obj in bpy.data.collections['Leicester Working'].all_objects:
        if obj.type != 'MESH' or obj.get('asset_group') != asset:
            continue
        vertices = [list(obj.matrix_world @ v.co) for v in obj.data.vertices]
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        result[obj['source_node']] = {
            'vertices': vertices, 'matrix': [list(row) for row in obj.matrix_world],
            'geometry_sha256': digest({'vertices': vertices, 'polygons': [list(p.vertices) for p in obj.data.polygons]}),
            'uv_sha256': digest({layer.name: [list(item.uv) for item in layer.data] for layer in obj.data.uv_layers}),
            'nonmanifold_edges': sum(not edge.is_manifold for edge in bm.edges),
            'degenerate_faces': sum(face.calc_area() < 1e-7 for face in bm.faces),
            'upper_vertices': [vertices[i] for i in sorted({i for p in obj.data.polygons
                 if all(vertices[j][2] > 61.05 for j in p.vertices) for i in p.vertices})],
        }
        bm.free()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    workspace = args.workspace.resolve()
    config = json.loads((workspace / 'workspace.json').read_text())
    candidate = capture(config['asset_id'])
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'baseline.blend'), load_ui=False)
    baseline = capture(config['asset_id'])
    assert set(candidate) == set(baseline) == set(config['part_ids'])
    checks = []
    for node, after in candidate.items():
        before = baseline[node]
        drift = max((sum((a-b)**2 for a,b in zip(v,w))**.5
                     for v in before['upper_vertices']
                     for w in [min(after['upper_vertices'], key=lambda w:sum((a-b)**2 for a,b in zip(v,w)))]), default=0.)
        matrix_drift = max(abs(a-b) for left,right in zip(before['matrix'],after['matrix']) for a,b in zip(left,right))
        base_drift = abs(min(v[2] for v in after['vertices'])-61.04)
        assert not after['nonmanifold_edges'] and not after['degenerate_faces']
        assert matrix_drift == 0 and drift < .002 and base_drift < .002
        checks.append({'source_node':node,'upper_anchor_max_drift':drift,'world_transform_drift':matrix_drift,
                       'base_datum_error':base_drift,**{k:after[k] for k in ('geometry_sha256','uv_sha256','nonmanifold_edges','degenerate_faces')},
                       'baseline_geometry_sha256':before['geometry_sha256'],'baseline_uv_sha256':before['uv_sha256']})
    report={'status':'PASS','asset_id':config['asset_id'],'checks':checks,
            'scope':'Read-only mesh, UV, anchor and contact-datum validation; baseline and candidate are not saved.'}
    (workspace/'geometry-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':main()
