"""Compare actual remaining boundary segments against the accepted baseline."""
import bpy,bmesh,json,sys
from pathlib import Path
from mathutils import Vector
W=Path(__file__).parent;D=W/'next-zigzag-v3'
def boundary():
 o=next(o for o in bpy.data.collections['Derby Working'].all_objects if o.type=='MESH' and not o.hide_render and o.get('source_node')=='building-185')
 bm=bmesh.new();bm.from_mesh(o.data)
 result=[[o.matrix_world@v.co for v in e.verts] for e in bm.edges if e.is_boundary];bm.free();return result
bpy.ops.wm.open_mainfile(filepath=str(W/'next-casement/model.blend'));original=boundary()
candidate=Path(sys.argv[sys.argv.index('--')+1]) if '--' in sys.argv else D/'joined-candidate.blend'
bpy.ops.wm.open_mainfile(filepath=str(candidate.resolve()));current=boundary()
def distance(p,a,b):
 d=b-a;t=max(0,min(1,(p-a).dot(d)/d.length_squared)) if d.length_squared else 0
 return (p-a-t*d).length
rows=[]
for a,b in current:
 errors=[min(distance(p,c,d) for c,d in original) for p in [a,(a+b)/2,b]]
 rows.append(dict(edge=[list(a),list(b)],max_error=max(errors)))
report=dict(baseline_edges=len(original),candidate_edges=len(current),tolerance=.002,unexplained=[r for r in rows if r['max_error']>.002],all_edges=rows)
(D/'boundary-inheritance.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='all_edges'}))
