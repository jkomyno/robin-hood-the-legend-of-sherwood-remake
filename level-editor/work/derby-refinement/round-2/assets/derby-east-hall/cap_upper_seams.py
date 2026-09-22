"""Close only upper connected boundary loops; never fill doors or lower openings."""
import bpy,bmesh,json
from pathlib import Path
W=Path(__file__).parent;D=W/'next-zigzag-v3'
report={}
for o in bpy.data.collections['Derby Working'].all_objects:
    if o.type!='MESH' or o.hide_render or o.get('source_node') not in ['building-183','building-185']:continue
    bm=bmesh.new();bm.from_mesh(o.data)
    floor=375.99 if o.get('source_node')=='building-185' else 364.99
    edges=[e for e in bm.edges if e.is_boundary and all((o.matrix_world@v.co).z>=floor for v in e.verts)]
    before=sum(e.is_boundary for e in bm.edges)
    created=bmesh.ops.holes_fill(bm,edges=edges,sides=0)['faces']
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    report[o.get('source_node')]=dict(before_boundary=before,after_boundary=sum(e.is_boundary for e in bm.edges),new_faces=len(created),nonmanifold=sum(not e.is_manifold for e in bm.edges))
    bm.to_mesh(o.data);bm.free()
bpy.ops.wm.save_as_mainfile(filepath=str(D/'seam-cap-test.blend'))
(D/'seam-cap-test.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
