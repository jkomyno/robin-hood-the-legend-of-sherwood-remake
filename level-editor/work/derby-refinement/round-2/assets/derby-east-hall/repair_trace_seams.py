"""Weld serialization seams and split collinear T junctions at rebuilt wall joins."""
import bpy, bmesh, json
from pathlib import Path
W = Path(__file__).parent
D = W / 'next-zigzag-v3'
report = {}
for o in bpy.data.collections['Derby Working'].all_objects:
    if o.type != 'MESH' or o.hide_render: continue
    node = o.get('source_node')
    if node not in {f'building-{n}' for n in [183,184,185,189,191,192,194]}: continue
    bm = bmesh.new(); bm.from_mesh(o.data)
    before = sum(e.is_boundary for e in bm.edges)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.001)
    base = 376 if node == 'building-185' else 365
    # Exact collinear splits preserve contour coordinates and the lower walls.
    for edge in list(bm.edges):
        if not all(abs((o.matrix_world @ v.co).z-base)<.002 for v in edge.verts): continue
        first, last = edge.verts
        delta = last.co-first.co
        if delta.length_squared < 1e-10: continue
        fractions = []
        for v in list(bm.verts):
            if v in edge.verts: continue
            t = (v.co-first.co).dot(delta)/delta.length_squared
            if 1e-6<t<1-1e-6 and (first.co+delta*t-v.co).length<.001:
                fractions.append(t)
        previous = 0; current = first
        for t in sorted(set(round(t,8) for t in fractions)):
            _, inserted = bmesh.utils.edge_split(edge, current, (t-previous)/(1-previous))
            previous = t; current = inserted
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.001)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    report[node] = dict(before_boundary=before, after_boundary=sum(e.is_boundary for e in bm.edges),
                        nonmanifold=sum(not e.is_manifold for e in bm.edges))
    bm.to_mesh(o.data); bm.free()
bpy.ops.wm.save_as_mainfile(filepath=str(D/'repaired-candidate.blend'))
(D/'seam-repair.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report), flush=True)
