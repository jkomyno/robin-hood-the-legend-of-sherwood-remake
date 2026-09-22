"""Audit retained facades and seam locations in the actual recovery checkpoint."""
import bpy, bmesh, json, hashlib
from pathlib import Path
W = Path(__file__).parent
D = W / 'next-zigzag-v3'
def capture():
    result = {}
    for o in bpy.data.collections['Derby Working'].all_objects:
        if o.type != 'MESH' or o.hide_render: continue
        node = o.get('source_node')
        if node not in {f'building-{n}' for n in [183,184,185,189,191,192,194,198]}: continue
        bm = bmesh.new(); bm.from_mesh(o.data)
        edges = [[list(o.matrix_world @ v.co) for v in e.verts] for e in bm.edges if e.is_boundary]
        result[node] = dict(name=o.name, boundary_edges=edges,
                           lower_vertices=[list(o.matrix_world @ v.co) for v in bm.verts if (o.matrix_world @ v.co).z < 364.99])
        bm.free()
    return result
native = capture()
if any(tag in bpy.data.filepath for tag in ['front-runs-trial','seam-cap-test']):
    filename='latest-front-seams.json' if 'front-runs-trial' in bpy.data.filepath else 'cap-seams.json'
    (D/filename).write_text(json.dumps(native, indent=2))
    raise SystemExit(0)
bpy.ops.wm.open_mainfile(filepath=str(D/'traced-runs-candidate.blend'))
source = capture()
assert native == source, 'Reprojection changed visible geometry'
(D/'recovery-geometry-audit.json').write_text(json.dumps(native, indent=2))
print('Recovered model matches traced candidate geometry exactly')
