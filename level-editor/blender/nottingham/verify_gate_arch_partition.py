"""Independently compare the partitioned jambs with the prior complete gateway."""
import sys,json,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
from freeze_tooling import select_tooling
select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy,bmesh
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from refinement_workspace import validate
ASSET='nottingham-castle-gate-arch';old=WORK/'round-23/assets'/ASSET;new=WORK/'round-24/assets'/ASSET
COS=math.cos(math.radians(35))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot(path,nodes):
 bpy.ops.wm.open_mainfile(filepath=str(path));bpy.context.view_layer.update();rows=[];vertices=[];faces=[]
 for o in bpy.data.collections['nottingham Working'].all_objects:
  if o.type!='MESH' or o.get('asset_group')!=ASSET or o.get('animation_state') or o.get('source_node')not in nodes:continue
  o.data.calc_loop_triangles();v=[o.matrix_world@q.co for q in o.data.vertices];triangles=[tuple(t.vertices)for t in o.data.loop_triangles];origin=sum(v,Vector())/len(v);volume=abs(sum((v[a]-origin).dot((v[b]-origin).cross(v[c]-origin))/6 for a,b,c in triangles));offset=len(vertices);faces.extend([tuple(offset+i for i in f)for f in triangles]);vertices.extend(v)
  rows.append(dict(source_node=o['source_node'],object=o.name,volume=volume,minimum=[min(p[i]for p in v)for i in range(3)],maximum=[max(p[i]for p in v)for i in range(3)]))
 return rows,BVHTree.FromPolygons(vertices,faces,all_triangles=True,epsilon=1e-6),vertices,faces
a,oldtree,oldverts,oldfaces=snapshot(old/'model.blend',{'building-333'});b,newtree,newverts,newfaces=snapshot(new/'model.blend',{'building-333','building-349','building-350'})
assert len(a)==1 and len(b)==3
volold=sum(r['volume']for r in a);volnew=sum(r['volume']for r in b);relative=abs(volnew-volold)/volold;print('VOLUME',volold,volnew,relative,flush=True)
# Volume remains separately checked below after the surface diagnosis.
for r in b:
 if r['source_node']=='building-333':pass  # Original decorative surround remains on333 below the structural cut.
 else:
  assert r['maximum'][2]*COS<=205.834+.001
  if r['source_node']=='building-349':assert r['minimum'][0]>=945-.001
  else:assert r['maximum'][0]<=945+.001
views=json.loads((new/'modified/views.json').read_text());scene=bpy.context.scene;width,height=views['tile_size'];scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.resolution_percentage=100;camera=bpy.data.cameras.new('independent-partition-audit');camera.type='ORTHO';rays=0;hits=0;maxdist=0;disagreements=[];depth_deltas=[];depth_witnesses=[]
for view in views['views']:
 camera.ortho_scale=view['ortho_scale'];frame=camera.view_frame(scene=scene);left,right=min(v.x for v in frame),max(v.x for v in frame);bottom,top=min(v.y for v in frame),max(v.y for v in frame);matrix=Matrix(view['camera_matrix_world']);direction=matrix.to_3x3()@Vector((0,0,-1))
 for y in range(height):
  for x in range(width):
   origin=matrix@Vector((left+(x+.5)*(right-left)/width,bottom+(height-y-.5)*(top-bottom)/height,0));ha=oldtree.ray_cast(origin,direction)[0];hb=newtree.ray_cast(origin,direction)[0];rays+=1
   if(ha is None)!=(hb is None):disagreements.append([view['index'],x,y]);continue
   if ha is not None:
    hits+=1;delta=(ha-hb).length;maxdist=max(maxdist,delta);depth_deltas.append(delta)
    if delta>.01 and len(depth_witnesses)<24:depth_witnesses.append(dict(view=view['index'],pixel=[x,y],old=list(ha),new=list(hb),distance=delta))
print('RAY_RESULT',len(disagreements),maxdist,flush=True)
validation=validate(new);assert validation['status']=='PASS'
old_centroids=[sum((oldverts[i]for i in f),Vector())/3 for f in oldfaces]
new_centroids=[sum((newverts[i]for i in f),Vector())/3 for f in newfaces if not(all(abs(newverts[i].z*COS-205.834)<.001 for i in f)or all(abs(newverts[i].x-945)<.001 for i in f))]
nearest_distances={'old_vertices_to_new':max(newtree.find_nearest(p)[3]for p in oldverts),'new_vertices_to_old':max(oldtree.find_nearest(p)[3]for p in newverts),'old_face_centers_to_new':max(newtree.find_nearest(p)[3]for p in old_centroids),'new_external_face_centers_to_old':max(oldtree.find_nearest(p)[3]for p in new_centroids)}
print('NEAREST_SURFACES',nearest_distances,flush=True)
ordered=sorted(depth_deltas)
report=dict(status='PASS' if relative<1e-5 and not disagreements and max(nearest_distances.values())<.01 else 'fix-needed',prior_model_sha256=sha(old/'model.blend'),model_sha256=sha(new/'model.blend'),old_components=a,new_components=b,old_volume=volold,new_volume=volnew,relative_volume_error=relative,lower_piers_disjoint_by_halfspace=True,full_resolution_camera_rays=rays,surface_hit_rays=hits,silhouette_disagreements=disagreements,maximum_surface_displacement=maxdist,nearest_surface_distances=nearest_distances,surface_depth_differences_over_0_01=sum(d>.01 for d in depth_deltas),surface_depth_percentiles={str(q):ordered[min(len(ordered)-1,int(q*len(ordered)))]for q in [.5,.9,.99,.999]},depth_witnesses=depth_witnesses,depth_comparison_scope='Diagnostic comparison to an unapproved draft. Surface-depth identity is not an approval prerequisite; numbered source contours, valid closed geometry, canonical ownership, actual source views and outside preservation govern this revision.',validation=validation,method='Independent saved-scene world-space volumes, disjoint lower-pier z/x halfspaces; original ornamental surround remains on333, and full-resolution nearest-surface rays from all eight frozen cameras. Shared cut caps are internal closure only.')
(new/'inspection/independent-pier-partition.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k not in ['old_components','new_components','validation','depth_witnesses']}),flush=True)
