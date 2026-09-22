"""Replace only the rear seam band, retaining all lower facades and upper caps."""
import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
W=Path(__file__).parent;D=W/'next-zigzag-v3'
o=next(o for o in bpy.data.collections['Derby Working'].all_objects if o.type=='MESH' and not o.hide_render and o.get('source_node')=='building-185')
bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.transform(bm,matrix=o.matrix_world,verts=list(bm.verts))
for co,no in [((0,0,365.01),(0,0,1)),((0,0,376),(0,0,1)),((1359,0,0),(1,0,0)),((1567,0,0),(1,0,0))]:
 bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.0001,plane_co=Vector(co),plane_no=Vector(no))
remove=[f for f in bm.faces if all(365.009<=v.co.z<=376.001 and 1358.999<=v.co.x<=1567.001 for v in f.verts)]
bmesh.ops.delete(bm,geom=remove,context='FACES_ONLY')
for row in json.loads((D/'rear-band-faces.json').read_text())['faces']:
 f=bm.faces.new([bm.verts.new(p) for p in row['points']]);f.normal_update()
 if row['normal'] and f.normal.z*row['normal']<0:f.normal_flip()
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.002)
for edge in list(bm.edges):
 if not edge.is_boundary:continue
 first,last=edge.verts;delta=last.co-first.co
 if delta.length_squared<1e-10:continue
 fractions=[]
 for v in list(bm.verts):
  if v in edge.verts:continue
  t=(v.co-first.co).dot(delta)/delta.length_squared
  if 1e-6<t<1-1e-6 and (first.co+delta*t-v.co).length<.002:fractions.append(t)
 previous=0;current=first
 for t in sorted(set(round(t,8) for t in fractions)):
  _,current=bmesh.utils.edge_split(edge,current,(t-previous)/(1-previous));previous=t
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.002)
bmesh.ops.delete(bm,geom=[e for e in bm.edges if not e.link_faces],context='EDGES')
for x in (1359,1567):
 cut_edges=[e for e in bm.edges if e.is_boundary and all(abs(v.co.x-x)<.002 and 365.009<=v.co.z<=376.001 for v in e.verts)]
 bmesh.ops.holes_fill(bm,edges=cut_edges,sides=0)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
report=dict(boundary=sum(e.is_boundary for e in bm.edges),nonmanifold=sum(not e.is_manifold for e in bm.edges),faces=len(bm.faces))
bm.to_mesh(o.data);bm.free();o.matrix_world.identity()
bpy.ops.wm.save_as_mainfile(filepath=str(D/'band-candidate.blend'))
(D/'band-topology.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
