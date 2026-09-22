"""Continuous roof/wall contacts for two measured town-house envelopes."""
import copy,json,math,hashlib
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3]
TAG='nottingham-continuous-town-envelope-v1'
SIN=math.sin(math.radians(35));COS=math.cos(math.radians(35))
def height(points,key,x,y):
 a,b,c=[Vector((p['x'],p['y'],p[key]))for p in points[:3]]
 n=(b-a).cross(c-a)
 return a.z-(n.x*(x-a.x)+n.y*(y-a.y))/n.z

def prism(obj,points):
 verts=[Vector((p['x'],-p['y']/SIN,p[k]/COS))for k in ['z_bottom','z_top']for p in points]
 faces=[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
 mesh=bpy.data.meshes.new(obj.name+' / continuous envelope');inv=obj.matrix_world.inverted();mesh.from_pydata([inv@v for v in verts],[],faces);mesh.update()
 bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces))
 defects={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)}
 if any(defects.values()):raise ValueError(defects)
 bm.to_mesh(mesh);bm.free();mesh.uv_layers.new(name='UVMap')
 for mat in obj.data.materials:mesh.materials.append(mat)
 obj.data=mesh
 return {'source_node':obj['source_node'],'vertices':len(mesh.vertices),'faces':len(mesh.polygons),**defects}

def refine(asset_id):
 sets={'nottingham-east-blue-house':[70,71,72],'nottingham-north-dormer-house':[122,123,124,125]}
 nodes=sets[asset_id];objects={int(o['source_node'].split('-')[-1]):o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==asset_id}
 if set(objects)!=set(nodes):raise ValueError('Unexpected canonical part ownership')
 for obj in objects.values():obj['projection_min_cosine']=.18
 if objects[nodes[0]].get(TAG):
  report=json.loads(objects[nodes[0]][TAG]);report['projection_min_cosine']=.18;note='Near-edge-on faces below0.18 source-facing cosine remain neutral because their pixels stretch into misleading facade slivers.'
  if note not in report['inference']:report['inference'].append(note)
  return report
 path=ROOT/'level-editor/work/nottingham-refinement/baseline/nottingham.rhp.json';src=json.load(open(path))['sight_obstacles'];p={n:copy.deepcopy(src[n]['points'])for n in nodes};contacts=[]
 if nodes[0]==70:
  # The raised duplicate receiver represented a roof as a deep hanging skirt.
  # Retain its source top silhouette and replace it with a finite roof slab.
  for q in p[71]:q['z_bottom']=q['z_top']-2.2
  p[70]=copy.deepcopy(p[71])
  for q in p[70]:q['z_top']=q['z_bottom'];q['z_bottom']=0
  contacts.append({'parts':[70,71],'contact':'four eave anchors and continuous roof underside','max_native_gap':max(abs(a['z_top']-b['z_bottom'])for a,b in zip(p[70],p[71]))})
  changes=['Replaced deep raised roof skirt with a 2.2-pixel vertical-thickness roof slab preserving its top source silhouette.','Extended the continuous ground-to-eave wall envelope beneath the complete slab; rebuilt rear boarded volume with closed walls.']
  inference=['Concealed wall footprint follows the roof footprint to support the previously unsupported western extension. Roof slab thickness and closed backs are conservative inferred construction.']
 else:
  # Roof123 is the independently selectable forward slope. Its underside is
  # the exact support datum, rather than the mismatched old wall roof plane.
  for q in p[122]:q['z_top']=height(p[123],'z_bottom',q['x'],q['y'])
  p[124][1].update(x=p[122][0]['x'],y=p[122][0]['y'],z_top=p[122][0]['z_top'])
  q=p[124][2];a,b=p[122][0],p[122][3];t=(q['x']-a['x'])/(b['x']-a['x']);q['y']=a['y']+t*(b['y']-a['y']);q['z_top']=height(p[123],'z_bottom',q['x'],q['y'])
  for i,j in [(0,3),(1,2)]:p[125][i].update(x=p[124][j]['x'],y=p[124][j]['y'],z_top=p[124][j]['z_top'])
  contacts=[{'parts':[122,123],'contact':'wall top fitted to roof underside plane','max_native_gap':max(abs(q['z_top']-height(p[123],'z_bottom',q['x'],q['y']))for q in p[122])},{'parts':[124,125],'contact':'both rear ridge endpoints shared exactly','max_native_gap':max(abs(p[125][i][k]-p[124][j][k])for i,j in [(0,3),(1,2)]for k in ['x','y','z_top'])},{'parts':[122,124],'contact':'front roof section meets rear volume along shared boundary','max_native_gap':0.0}]
  changes=['Rebuilt four closed envelope parts with continuous wall support below the forward roof slab.','Aligned both rear gable ridge endpoints and the forward/rear roof junction; removed disconnected corner sheets and unsupported open backs.']
  inference=['Hidden backs and underside caps are inferred closed construction; the selectable roof retains its measured source eaves. Subpixel rear ridge discrepancies resolve to a shared anchor.']
 before={n:objects[n].matrix_world.copy()for n in nodes};reports=[prism(objects[n],p[n])for n in nodes]
 assert all(objects[n].matrix_world==before[n]for n in nodes)
 report={'status':'refined','asset_id':asset_id,'objects':reports,'contacts':contacts,'changes':changes,'inference':inference,'projection_min_cosine':.18,'transform_drift':0,'source_native_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
 report['inference'].append('Near-edge-on faces below0.18 source-facing cosine remain neutral because their pixels stretch into misleading facade slivers.')
 objects[nodes[0]][TAG]=json.dumps(report);return report
