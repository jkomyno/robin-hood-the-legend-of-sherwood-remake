"""Check narrow merlon shoulder planarity and penetration by other crown faces."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'level-editor/work/nottingham-refinement/round-38/assets/nottingham-castle-gate-west-tower';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
import bpy
from mathutils.geometry import intersect_ray_tri
bpy.ops.wm.open_mainfile(filepath=str(W/'model.blend'));objects=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==W.name];triangles=[]
for o in objects:
 o.data.calc_loop_triangles()
 triangles.extend((o,tri.polygon_index,[o.matrix_world@o.data.vertices[i].co for i in tri.vertices])for tri in o.data.loop_triangles)
rows=[]
for node,faceindex in [('building-331',30),('building-332',74)]:
 obj=next(o for o in objects if o.get('source_node')==node);poly=obj.data.polygons[faceindex];points=[obj.matrix_world@obj.data.vertices[i].co for i in poly.vertices];normal=(points[1]-points[0]).cross(points[2]-points[0]).normalized();owntris=[v for o,i,v in triangles if o==obj and i==faceindex];penetrations=[]
 for other,index,vs in triangles:
  if other==obj and index==faceindex:continue
  # Only proper edge/face crossings count; shared endpoints/edges are contacts.
  for a,b in zip(vs,vs[1:]+vs[:1]):
   if (a-points[0]).dot(normal)*(b-points[0]).dot(normal)>=-1e-6:continue
   direction=b-a
   for tri in owntris:
    hit=intersect_ray_tri(*tri,direction,a,True)
    if hit is not None and 1e-5<(hit-a).dot(direction)/direction.length_squared<1-1e-5:penetrations.append(dict(other=other['source_node'],face=index,point=list(hit)))
  for a,b in zip(points,points[1:]+points[:1]):
   othernormal=(vs[1]-vs[0]).cross(vs[2]-vs[0]).normalized()
   if (a-vs[0]).dot(othernormal)*(b-vs[0]).dot(othernormal)>=-1e-6:continue
   direction=b-a;hit=intersect_ray_tri(*vs,direction,a,True)
   if hit is not None and 1e-5<(hit-a).dot(direction)/direction.length_squared<1-1e-5:penetrations.append(dict(other=other['source_node'],face=index,point=list(hit)))
 rows.append(dict(node=node,face=faceindex,planarity_error=max(abs((p-points[0]).dot(normal))for p in points),proper_face_penetrations=penetrations))
report=dict(status='PASS'if not any(r['proper_face_penetrations']for r in rows)else'FAIL',model_sha256=hashlib.sha256((W/'model.blend').read_bytes()).hexdigest(),method='Bidirectional triangle edge/face crossing tests against all asset triangles; plane crossings must be strict and segment intersections interior. Shared boundary contacts excluded.',faces=rows);(W/'inspection/shoulder-intersections.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
