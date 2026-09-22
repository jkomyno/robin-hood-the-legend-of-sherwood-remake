import bpy,json,math,sys
from pathlib import Path
W=Path(__file__).parent; out=W/'next-zigzag-v3';out.mkdir(exist_ok=True)
S=math.sin(math.radians(35)); C=math.cos(math.radians(35))
rows=[]
for o in bpy.data.collections['Derby Working'].all_objects:
 if o.type!='MESH' or o.hide_render or o.get('asset_group')!='derby-east-hall':continue
 vs=[o.matrix_world@v.co for v in o.data.vertices]
 edges=[]
 for e in o.data.edges:
  a,b=[vs[i] for i in e.vertices]
  if min(a.z,b.z)<365: continue
  edges.append({'indices':list(e.vertices),'world':[list(a),list(b)],'source':[[p.x,-p.y*S-p.z*C] for p in (a,b)]})
 if edges:rows.append({'name':o.name,'node':o.get('source_node'),'edges':edges})
name=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'top-edges.json'
(out/name).write_text(json.dumps(rows,indent=2))
