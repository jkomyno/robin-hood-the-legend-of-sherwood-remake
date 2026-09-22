"""Replace overlapping seam faces with a two-footprint planar surface difference."""
import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
W=Path(__file__).parent;D=W/'next-zigzag-v3'
patches=json.loads((D/'join-triangles.json').read_text());report={}
for o in bpy.data.collections['Derby Working'].all_objects:
 if o.type!='MESH' or o.hide_render or o.get('source_node') not in patches:continue
 node=o.get('source_node');base=376 if node=='building-185' else 365
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.transform(bm,matrix=o.matrix_world,verts=list(bm.verts))
 bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.001,plane_co=Vector((0,0,base)),plane_no=Vector((0,0,1)))
 flat=[f for f in bm.faces if all(abs(v.co.z-base)<.002 for v in f.verts)]
 bmesh.ops.delete(bm,geom=flat,context='FACES_ONLY')
 for v in bm.verts:
  if abs(v.co.z-base)<.002:v.co=Vector((round(v.co.x,3),round(v.co.y,3),base))
 for triangle in patches[node]['triangles']:
  vs=[bm.verts.new((x,y,base)) for x,y in triangle['points']]
  f=bm.faces.new(vs);f.normal_update()
  if f.normal.z*triangle['normal']<0:f.normal_flip()
 bmesh.ops.remove_doubles(bm,verts=[v for v in bm.verts if abs(v.co.z-base)<.002],dist=.002)
 for edge in list(bm.edges):
  if not all(abs(v.co.z-base)<.002 for v in edge.verts):continue
  first,last=edge.verts;delta=last.co-first.co
  if delta.length_squared<1e-10:continue
  fractions=[]
  for v in list(bm.verts):
   if v in edge.verts or abs(v.co.z-base)>.002:continue
   t=(v.co-first.co).dot(delta)/delta.length_squared
   if 1e-6<t<1-1e-6 and (first.co+delta*t-v.co).length<.002:fractions.append(t)
  previous=0;current=first
  for t in sorted(set(round(t,8) for t in fractions)):
   _,current=bmesh.utils.edge_split(edge,current,(t-previous)/(1-previous));previous=t
 bmesh.ops.remove_doubles(bm,verts=[v for v in bm.verts if abs(v.co.z-base)<.002],dist=.002)
 loose=[e for e in bm.edges if not e.link_faces]
 bmesh.ops.delete(bm,geom=loose,context='EDGES')
 # The two southwest arms share an internal end cap. Its three triple-face
 # edges and its sole open bottom edge identify the redundant separator.
 if node=='building-183':
  internal=[f for f in bm.faces if sum(len(e.link_faces)==3 for e in f.edges)>=3 and any(len(e.link_faces)==1 for e in f.edges)]
  assert len(internal)==1, 'Expected exactly one internal southwest separator'
  bmesh.ops.delete(bm,geom=internal,context='FACES_ONLY')
  bmesh.ops.delete(bm,geom=[e for e in bm.edges if not e.link_faces],context='EDGES')
 if node=='building-185':
  # Close the two deliberately cut ends of the old upper strip. These loops
  # lie on known cut planes, above the preserved facade, not arbitrary holes.
  for x in (1359,1567):
   ends=[e for e in bm.edges if e.is_boundary and all(abs(v.co.x-x)<.002 and v.co.z>=base-.002 for v in e.verts)]
   made=bmesh.ops.holes_fill(bm,edges=ends,sides=0)['faces']
   assert len(made)==1, f'Expected one closed end cut at x={x}'
 bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
 report[node]=dict(boundary=sum(e.is_boundary for e in bm.edges),nonmanifold=sum(not e.is_manifold for e in bm.edges),faces=len(bm.faces))
 bm.to_mesh(o.data);bm.free();o.matrix_world.identity()
bpy.ops.wm.save_as_mainfile(filepath=str(D/'joined-candidate.blend'))
(D/'joined-topology.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
