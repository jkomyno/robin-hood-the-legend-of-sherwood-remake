"""Replace rural rock proxy wedges with source-anchored faceted boulders."""
from pathlib import Path
import json,sys,math
ROOT=Path(__file__).resolve().parents[3];RUN=ROOT/'level-editor/work/nottingham-refinement'
TAG='nottingham_village_source_contour_rocks_v2'

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

def contour(mask_index):
 from PIL import Image
 inventory=RUN/'mask-review/inventory-v6';rows=json.loads((inventory/'manifest.json').read_text())['masks'];row=next(p for p in rows if p['index']==mask_index);im=Image.open(inventory/row['png']).convert('L');x,y=row['box_top_left']
 return hull([(x+u,y+v)for v in range(im.height)for u in range(im.width)if im.getpixel((u,v))>0])


def rock(outline):
 from mathutils import Vector
 from refine_village_secondary import SIN,COS
 n=len(outline);cx=sum(p[0]for p in outline)/n;cy=sum(p[1]for p in outline)/n;vmax=max(p[1]for p in outline);spanx=max(p[0]for p in outline)-min(p[0]for p in outline);spany=vmax-min(p[1]for p in outline)
 depth=min(.28*min(spanx,spany),(vmax-cy)*COS*.45/(.84*SIN)*.9);d0=-vmax*COS/SIN
 def world(u,v,d):return Vector((u,-v*SIN+d*COS,-v*COS-d*SIN))
 vertices=[world(u,v,d0)for u,v in outline];faces=[]
 for sign in [-1,1]:
  base=len(vertices)
  for u,v in outline:vertices.append(world(cx+(u-cx)*.55,cy+(v-cy)*.55,d0+sign*.84*depth))
  center=len(vertices);vertices.append(world(cx,cy,d0+sign*depth))
  for j in range(n):
   k=(j+1)%n;faces.extend([(j,k,base+k,base+j),(base+j,base+k,center)])
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
  outlines=[[(1595,2342),(1602,2344),(1609,2354),(1614,2371),(1622,2384),(1632,2404),(1623,2415),(1608,2420),(1591,2418),(1570,2410),(1562,2397),(1564,2379),(1575,2360),(1586,2350)],[(1498,2360),(1507,2357),(1519,2357),(1527,2361),(1529,2365),(1524,2371),(1518,2377),(1509,2381),(1497,2375),(1495,2368)],[(1540,2359),(1553,2357),(1561,2361),(1568,2369),(1564,2385),(1556,2400),(1541,2409),(1526,2404),(1516,2389),(1519,2372),(1529,2364)]]
  v,f=rock(outlines[0]);changes.append(replace(owned[310],v,f,'Large eastern source-contour boulder'));v=[];f=[]
  for outline in outlines[1:]:
   rv,rf=rock(outline);base=len(v);v.extend(rv);f.extend(tuple(base+i for i in face)for face in rf)
  changes.append(replace(owned[311],v,f,'Two rounded source-contour boulders'))
 else:
  left,right,mask=(321,322,264)if asset.endswith('southeast-yard-supplies')else(323,324,266);p=native(left);q=native(right);outlines=[contour(mask)];v,f=rock(outlines[0]);a,b=p[0],p[1]
  lv,lf=split(v,f,a,b,p[2]);rv,rf=split(v,f,a,b,q[0]);assert lv and rv and lf and rf
  changes.append(replace(owned[left],lv,lf,'Measured source-contour rock left'));changes.append(replace(owned[right],rv,rf,'Measured source-contour rock right'))
 for obj in owned.values():obj[TAG]=True
 return {'status':'refined','asset_id':asset,'changes':changes,'source_contours':outlines,'inference':['The visible source contour replaces inaccurate native obstacle proxy silhouettes. Native264/266 outlines and individually measured271 boulder landmarks constrain the front projection.','Closed front/back shoulders use compact inferred depth, limited to keep all geometry above the observed ground contact. Hidden depth is not established by the single source image.','Paired native receivers retain their dividing plane; no new texture or foreign source pixels are generated.']}

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
