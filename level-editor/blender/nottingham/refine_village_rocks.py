"""Replace rural rock proxy wedges with source-anchored faceted boulders."""
from pathlib import Path
import json,sys,math
ROOT=Path(__file__).resolve().parents[3];RUN=ROOT/'level-editor/work/nottingham-refinement'
TAG='nottingham_village_faceted_rocks_v1'

def hull(points):
 points=sorted(set(points))
 def cross(a,b,c):return(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
 lower=[];upper=[]
 for p in points:
  while len(lower)>1 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
  lower.append(p)
 for p in reversed(points):
  while len(upper)>1 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
  upper.append(p)
 return lower[:-1]+upper[:-1]

def rock(points,apex):
 from mathutils import Vector
 from refine_village_secondary import SIN,COS
 ring=hull([(p['x'],p['y'])for p in points]);n=len(ring);cx=sum(p[0]for p in ring)/n;cy=sum(p[1]for p in ring)/n;vertices=[]
 # Ground perimeter retains native anchors; an intermediate shoulder removes
 # the straight roof-like slope. The upper point is a source-measured crest.
 for scale,height in [(1,0),(.82,.52),(.32,.87)]:
  for x,y in ring:
   px=cx+(x-cx)*scale+(apex[0]-cx)*(1-scale);py=cy+(y-cy)*scale+(apex[1]-cy)*(1-scale)
   vertices.append(Vector((px,-py/SIN,apex[2]*height/COS)))
 vertices.append(Vector((apex[0],-apex[1]/SIN,apex[2]/COS)));faces=[tuple(reversed(range(n)))]
 for row in range(2):
  for j in range(n):a=row*n+j;b=row*n+(j+1)%n;faces.append((a,b,b+n,a+n))
 for j in range(n):faces.append((2*n+j,2*n+(j+1)%n,3*n))
 return vertices,faces

def split(vertices,faces,a,b,keep_point):
 import bpy,bmesh
 from mathutils import Vector
 from refine_village_secondary import SIN
 normal=Vector((b['y']-a['y'],SIN*(b['x']-a['x']),0));origin=Vector((a['x'],-a['y']/SIN,0));normal.normalize()
 if normal.dot(Vector((keep_point['x'],-keep_point['y']/SIN,0))-origin)<0:normal=-normal
 mesh=bpy.data.meshes.new('Rock temporary');mesh.from_pydata(vertices,[],faces);mesh.update();bm=bmesh.new();bm.from_mesh(mesh)
 bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),plane_co=origin,plane_no=normal,dist=1e-6,clear_inner=True,clear_outer=False)
 bmesh.ops.holes_fill(bm,edges=[e for e in bm.edges if e.is_boundary],sides=0);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.dissolve_degenerate(bm,dist=.0001,edges=list(bm.edges));bm.verts.ensure_lookup_table();v=[p.co.copy()for p in bm.verts];f=[tuple(p.index for p in face.verts)for face in bm.faces];bm.free();return v,f

def refine(asset):
 import bpy
 from refine_village_secondary import native,replace
 owned={int(o['source_node'].split('-')[-1]):o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')==asset and o.get('source_node') and not o.hide_render}
 if all(o.get(TAG)for o in owned.values()):return {'status':'existing'}
 changes=[]
 if asset.endswith('east-boulders'):
  p=native(310);peak=max(p,key=lambda x:x['z_top']-x['y']);v,f=rock(p,(peak['x'],peak['y'],peak['z_top']));changes.append(replace(owned[310],v,f,'Large eastern faceted boulder'))
  p=native(311);v=[];f=[]
  for sign,apex in [(-1,(1506.56,2390.59,36.44)),(1,(1550,2418.79,59.34))]:
   poly=[]
   for a,b in zip(p,p[1:]+p[:1]):
    da=sign*(a['x']-1524);db=sign*(b['x']-1524)
    if da>=0:poly.append(a)
    if da*db<0:
     t=da/(da-db);poly.append({'x':1524,'y':a['y']+(b['y']-a['y'])*t})
   rv,rf=rock(poly,apex);base=len(v);v.extend(rv);f.extend(tuple(base+i for i in face)for face in rf)
  changes.append(replace(owned[311],v,f,'Two western faceted boulders'))
 else:
  left,right=(321,322)if asset.endswith('southeast-yard-supplies')else(323,324);p=native(left);q=native(right);crest=max(p+q,key=lambda x:x['z_top']-x['y']);v,f=rock(p+q,(crest['x'],crest['y'],crest['z_top']))
  # Keep the existing two native receivers on their original crest division.
  a,b=p[0],p[1];keep=p[2]
  lv,lf=split(v,f,a,b,keep);rv,rf=split(v,f,a,b,q[0]);changes.append(replace(owned[left],lv,lf,'Faceted rock left surface'));changes.append(replace(owned[right],rv,rf,'Faceted rock right surface'))
 for obj in owned.values():obj[TAG]=True
 return {'status':'refined','asset_id':asset,'changes':changes,'inference':['Native ground perimeter and crest heights anchor the rock; intermediate shoulders and concealed backs are conservative faceted interpolation.','Small paired native surfaces remain independently selectable on their existing crest division.','No new texture is generated; native visible rock silhouettes constrain source projection.']}

def main():
 sys.path.insert(0,str(Path(__file__).resolve().parent));from render_slots import acquire
 acquire();from freeze_tooling import select_tooling
 select_tooling(RUN/'tooling/315d227e98d52a78')
 import bpy
 from refinement_workspace import modified
 from refine_village_secondary import digest
 workspaces=[Path(p).resolve()for p in sys.argv[sys.argv.index('--')+1:]]if '--'in sys.argv else [RUN/'round-1/assets'/('nottingham-village-'+short)for short in ['southeast-yard-supplies','dovecote-yard-supplies','east-boulders']]
 for workspace in workspaces:
  asset=json.loads((workspace/'workspace.json').read_text())['asset_id'];bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'));outside={o.name:digest(o)for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')!=asset};report=refine(asset)
  if outside!={o.name:digest(o)for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')!=asset}:raise ValueError('Outside geometry drift')
  before={o.name:digest(o)for o in bpy.context.scene.objects if o.type=='MESH'};refine(asset);assert before=={o.name:digest(o)for o in bpy.context.scene.objects if o.type=='MESH'};report['idempotence']='PASS'
  if report['status']=='existing':report=json.loads((workspace/'inspection/faceted-rock-refinement.json').read_text());report['idempotence']='PASS'
  (workspace/'inspection/faceted-rock-refinement.json').write_text(json.dumps(report,indent=2)+'\n');bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'));print(modified(workspace),flush=True)

if __name__=='__main__':main()
