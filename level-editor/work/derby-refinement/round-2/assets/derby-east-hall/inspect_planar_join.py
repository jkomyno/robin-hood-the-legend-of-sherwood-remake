"""Extract the two cross-section contours before constructing a planar join."""
import bpy,bmesh,json,sys
from pathlib import Path
from mathutils import Vector
W=Path(__file__).parent; D=W/'next-zigzag-v3'
result={}
for o in bpy.data.collections['Derby Working'].all_objects:
 if o.type!='MESH' or o.hide_render or o.get('source_node') not in ['building-183','building-185']:continue
 base=float(sys.argv[sys.argv.index('--')+1]) if '--' in sys.argv else (376 if o.get('source_node')=='building-185' else 365)
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.transform(bm,matrix=o.matrix_world,verts=list(bm.verts))
 bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.001,plane_co=Vector((0,0,base)),plane_no=Vector((0,0,1)))
 flat=[f for f in bm.faces if all(abs(v.co.z-base)<.002 for v in f.verts)]
 bmesh.ops.delete(bm,geom=flat,context='FACES_ONLY')
 sides={'lower':[],'upper':[]}
 for e in bm.edges:
  if not all(abs(v.co.z-base)<.002 for v in e.verts):continue
  for side,sign in [('lower',-1),('upper',1)]:
   if any(any((v.co.z-base)*sign>.002 for v in f.verts) for f in e.link_faces):
    sides[side].append([[v.co.x,v.co.y] for v in e.verts])
 result[o.get('source_node')]=sides
 bm.free()
name='join-sections-bottom.json' if '--' in sys.argv else 'join-sections.json'
(D/name).write_text(json.dumps(result,indent=2))
