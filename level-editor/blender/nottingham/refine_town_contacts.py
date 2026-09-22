"""Measured terrace contacts, south roof connector and timber stair structure."""
import copy,json,math
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
from refine_town import native_point
ROOT=Path(__file__).resolve().parents[3]
SIN=math.sin(math.radians(35));COS=math.cos(math.radians(35))
TAG='nottingham_town_contacts_v3'

def install(obj,vertices,faces):
 mesh=bpy.data.meshes.new(obj.name+' / coherent contacts');inv=obj.matrix_world.inverted();mesh.from_pydata([inv@p for p in vertices],[],faces);mesh.update()
 bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces))
 defects={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
 if any(defects.values()):raise ValueError((obj.name,defects))
 bm.to_mesh(mesh);bm.free();mesh.uv_layers.new(name='UVMap')
 for material in obj.data.materials:mesh.materials.append(material)
 obj.data=mesh;return {'source_node':obj['source_node'],'vertices':len(mesh.vertices),'faces':len(mesh.polygons),**defects}

def prism(obj,points):
 return install(obj,[native_point(p,p[k])for k in ['z_bottom','z_top']for p in points],[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])

def terrace_supports(objs,src):
 obj=objs[12];tag='market_masonry_contacts_v1'
 if obj.get(tag):return
 bm=bmesh.new();bm.from_mesh(obj.data);inverse=obj.matrix_world.inverted()
 for index in (6,14,9,10):
  pts=src[index]['points'];world=[native_point(v,0)for v in pts];center=sum(world,Vector())/len(world);low=[];high=[]
  for pt,v in zip(world,pts):
   direction=center-pt;direction.z=0;direction.normalize();pt+=direction*1.5
   low.append(bm.verts.new(inverse@pt));high.append(bm.verts.new(inverse@(pt+Vector((0,0,(v['z_bottom']+1)/COS)))))
  bm.faces.new(tuple(reversed(low)));bm.faces.new(tuple(high))
  for i in range(len(low)):
   j=(i+1)%len(low);bm.faces.new((low[i],low[j],high[j],high[i]))
 bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free();obj.data.update();obj[tag]=True

def refine(asset):
 src=json.loads((ROOT/'level-editor/work/nottingham-refinement/baseline/nottingham.rhp.json').read_text())['sight_obstacles']
 objs={int(o['source_node'][-3:]):o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==asset}
 first=objs[min(objs)];tag=TAG+('_no_railing' if asset=='nottingham-south-stair-house' else '')
 if first.get(tag):return json.loads(first[tag])
 p={n:copy.deepcopy(src[n]['points'])for n in objs};reports=[];changes=[];inference=[]
 if asset=='nottingham-south-gate-house':
  # Move the rear edge back along source rays to contact the rear block.
  # This preserves each measured source pixel while resolving hidden depth.
  for i,target_y in [(0,1959.2498),(3,1956.4249)]:
   delta=target_y-p[23][i]['y'];p[23][i]['y']+=delta;p[23][i]['z_top']+=delta
  for n in [24,25]:
   for q in p[n]:q['y']-=10;q['z_top']-=10
  # Central orange slope is a continuous roof, not disconnected side ribbons.
  # Native top planes retain all visible roof and dormer anchors.
  for n in objs:
   for q in p[n]:q['z_bottom']=0
   reports.append(prism(objs[n],p[n]))
  changes=['Rebuilt ten closed selectable components, preserving measured top planes; the broad orange connector now has a continuous roof surface and both raised window-bank volumes have closed backing.','Closed the rear roof and front gable envelopes, eliminating open reverse-view sheets.']
  inference=['Rear connector edge is moved20–24 native units along the source camera rays to contact the rear block, preserving its visible silhouette; dormer banks use10 units of the same concealed-depth adjustment. Hidden wall thickness and roof-volume interiors are closed structural hypotheses; the two window-bank faces retain source texture and are not traversable openings.']
 elif asset=='nottingham-south-stair-house':
  # Lower support follows the actual upper wall footprint. Keep the roof eaves.
  p[26]=copy.deepcopy(p[29])
  for q in p[26]:q.update(z_bottom=0,z_top=68.57201)
  for q in p[29]:q.update(z_bottom=68.57201,z_top=132.858)
  for i,j in [(0,3),(1,2)]:
   for k in ['x','y','z_top']:p[28][j][k]=p[27][i][k]
  for n in [26,27,28,29,31,32]:reports.append(prism(objs[n],p[n]))
  verts=[];faces=[]
  def box(q):
   off=len(verts);verts.extend(q);faces.extend(tuple(off+i for i in f)for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
  def beam(a,b,w):
   axis=(b-a).normalized();side=axis.cross(Vector((0,0,1)))
   if side.length<.01:side=axis.cross(Vector((1,0,0)))
   side.normalize();up=axis.cross(side).normalized();ring=[side*x*w/2+up*y*w/2 for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]];box([v+d for v in [a,b]for d in ring])
  low=[native_point(p[30][i],0)for i in [3,2]];high=[native_point(p[30][i],75.00101)for i in [0,1]]
  for i in range(10):
   q=[low[0].lerp(high[0],i/10),low[1].lerp(high[1],i/10),low[1].lerp(high[1],(i+1)/10),low[0].lerp(high[0],(i+1)/10)]
   for v in q:v.z=high[0].z*(i+1)/10
   box([v-Vector((0,0,2.5))for v in q]+q)
  for a,b in zip(low,high):
   beam(a,b,3.5)
  for v in [native_point(p[31][i],75.00101)for i in [1,2]]:beam(Vector((v.x,v.y,0)),v,4)
  reports.append(install(objs[30],verts,faces));changes=['Replaced smooth stair ramp with ten timber treads, two stringers and landing support legs; retained measured stair and landing endpoints. Removed all handrails and railing uprights following the explicit user correction.','Aligned both gable ridge ends and extended the lower masonry support to the upper timber wall footprint, closing reverse-view gaps.']
  inference=['Ten tread intervals are an inferred regular continuation between the measured stair endpoints; tread count is not asserted as recovered architectural fact.','Timber widths and underside depth are inferred; no rail or railing upright is modeled.']
 elif asset=='nottingham-market-terrace':
  terrace_supports(objs,src)
  # Roof16/17 share a ridge; native wall15 only differs by subpixel height.
  for q in p[15]:q['z_top']=138.07701
  for i,j in [(2,1),(3,0)]:
   for k in ['x','y','z_top']:p[17][j][k]=p[16][i][k]
  for n in [15,16,17]:reports.append(prism(objs[n],p[n]))
  changes=['Extended shared masonry beneath the red and right green bays, retaining the open left portico.', 'Closed the rear large-roof envelopes and shared both ridge endpoints; raised its wall support by0.076 source pixels to meet the eave datum.']
  inference=['Closed rear and underside surfaces are inferred construction; the left front portico remains intentionally open on columns.']
 else:raise ValueError(asset)
 for obj in objs.values():obj['projection_min_cosine']=.18
 inference.append('Faces below0.18 source-facing cosine remain neutral to prevent stretched edge-on source bands in reverse views.')
 report={'status':'refined','asset_id':asset,'objects':reports,'changes':changes,'inference':inference,'transform_drift':0};first[tag]=json.dumps(report);return report
