"""Classify rendered red pixels using exact camera-center mesh/UV intersections."""
import sys,json,hashlib,collections
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
from PIL import Image
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def slot_provenance(evidence, objects):
 """Keep distinct image ownership for each proved material slot on an object."""
 result={}
 for entry in evidence:
  proof=entry['provenance']
  if sha(proof['path'])!=proof['sha256']:raise ValueError('Provenance changed')
  with np.load(proof['path'],allow_pickle=False) as data:ownership=data['ownership'].copy()
  if ownership.ndim!=2 or not np.isin(ownership,[0,1,2,3]).all():raise ValueError('Invalid atlas ownership')
  slots=entry['slots']
  if not slots or any(type(slot)is not int or slot<0 for slot in slots):raise ValueError('Invalid material slot evidence')
  obj=objects[entry['object']]
  for slot in slots:
   mat=obj.data.materials[slot]
   textures=[n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
   uv_nodes=[n for n in mat.node_tree.nodes if n.type=='UVMAP']
   if len(textures)!=1 or len(uv_nodes)!=1:raise ValueError('Ambiguous material atlas binding')
   image=textures[0].image;uv_name=uv_nodes[0].uv_map
   if not image.packed_file or hashlib.sha256(image.packed_file.data).hexdigest()!=proof['packed_image_sha256']:raise ValueError('Material slot image differs from provenance')
   coordinates=[list(v.uv)for v in obj.data.uv_layers[uv_name].data]
   if hashlib.sha256(json.dumps(coordinates).encode()).hexdigest()!=proof['uv_sha256']:raise ValueError('Material slot UV differs from provenance')
   if ownership.shape!=(image.size[1],image.size[0]):raise ValueError('Material slot atlas shape differs')
   key=(entry['object'],slot,uv_name)
   if key in result:raise ValueError('Ambiguous material slot provenance: '+str(key))
   result[key]=ownership
 return result

def run(folder,subrays=False,bake=None):
 folder=Path(folder);report=json.loads((folder/'coverage.json').read_text());model=None
 # Every provenance evidence binds its saved model independently in coverage.json.
 jobroot=Path(__file__).resolve().parents[3]/'level-editor/work/nottingham-refinement/coordinator-audit/final-texture-coverage'
 if bake is not None:bake=Path(bake).resolve()
 elif (folder.parent/'worker.blend').exists():bake=folder.parent
 elif (folder.parent/'depth-review.json').exists():bake=Path(json.loads((folder.parent/'depth-review.json').read_text())['bake'])
 else:
  jobs=json.loads((jobroot/'jobs.json').read_text());rows=jobs['jobs']+jobs['skips'];row=next(r for r in rows if r.get('model_sha256')==report['model_sha256']);bake=Path(row['bake'])
 validation=json.loads((bake/'validation.json').read_text());manifest=next(Path(p)for p in validation['evidence_sha256'] if Path(p).name=='views.json')
 if sha(bake/'worker.blend')!=report['model_sha256'] or sha(manifest)!=report['manifest_sha256']:raise ValueError('Stale coverage')
 data=json.loads(manifest.read_text());bpy.ops.wm.open_mainfile(filepath=str(bake/'worker.blend'));scene=bpy.data.scenes[data['scene_name']];bpy.context.window.scene=scene
 names=data.get('render_object_names')or data['object_names'];vertices=[];triangles=[];refs=[];proofs=slot_provenance(report['atlas_evidence'],scene.objects)
 for name in names:
  o=scene.objects[name];m=o.data;m.calc_loop_triangles();offset=len(vertices);vertices.extend(o.matrix_world@v.co for v in m.vertices)
  for t in m.loop_triangles:triangles.append(tuple(offset+i for i in t.vertices));refs.append((o,t))
 tree=BVHTree.FromPolygons(vertices,triangles,all_triangles=True);w,h=data['tile_size'];scene.render.resolution_x=w;scene.render.resolution_y=h;scene.render.resolution_percentage=100;scene.render.pixel_aspect_x=scene.render.pixel_aspect_y=1
 camera=bpy.data.cameras.new('read-only coverage ray');camera.type='ORTHO';output=[]
 for view in data['views']:
  i=view['index'];im=np.asarray(Image.open(folder/f'view-{i}-textured.png').convert('RGBA'));rgb=im[:,:,:3].astype(float);red=(im[:,:,3]>127)&(rgb[:,:,0]>80)&(rgb[:,:,0]>2*rgb[:,:,1])&(rgb[:,:,0]>2*rgb[:,:,2]);counts=collections.Counter();hits=[];subcounts=collections.Counter();subhits=[]
  expected=next(v['sha256'] for v in report['views'] if v['index']==i);assert sha(folder/f'view-{i}-textured.png')==expected
  camera.ortho_scale=view['ortho_scale'];frame=camera.view_frame(scene=scene);left,right=min(p.x for p in frame),max(p.x for p in frame);bottom,top=min(p.y for p in frame),max(p.y for p in frame);matrix=Matrix(view['camera_matrix_world']);direction=matrix.to_3x3()@Vector((0,0,-1))
  for y,x in zip(*np.where(red)):
   offsets=[(0,0)]+([(dx,dy)for dx in (-.33,0,.33)for dy in (-.33,0,.33)if dx or dy]if subrays else[])
   for dx,dy in offsets:
    counter=counts if (dx,dy)==(0,0)else subcounts;witnesses=hits if (dx,dy)==(0,0)else subhits
    origin=matrix@Vector((left+(int(x)+.5+dx)*(right-left)/w,bottom+(h-int(y)-.5-dy)*(top-bottom)/h,0));hit,normal,index,_=tree.ray_cast(origin,direction)
    if index is None:counter['no-center-surface-hit']+=1;continue
    o,t=refs[index];mat=o.data.materials[t.material_index];node=next(n for n in mat.node_tree.nodes if n.type=='UVMAP');uv=o.data.uv_layers[node.uv_map];vs=np.array([vertices[k]for k in triangles[index]]);basis=np.array([vs[1]-vs[0],vs[2]-vs[0]]).T;b=np.linalg.lstsq(basis,np.array(hit)-vs[0],rcond=None)[0];weights=np.array([1-b.sum(),b[0],b[1]]);q=weights@np.array([uv.data[k].uv[:]for k in t.loops]);a=proofs[(o.name,t.material_index,node.uv_map)];iy,ix=np.clip((q[::-1]*a.shape).astype(int),0,np.array(a.shape)-1);cls=int(a[iy,ix]);counter['center-class-'+str(cls)]+=1
    if cls==0:witnesses.append(dict(offset=[dx,dy],view_facing=float(-normal.dot(direction)),pixel=[int(x),int(y)],object=o.name,material_slot=t.material_index,uv_layer=node.uv_map,face=t.polygon_index,world=list(hit),uv=q.tolist(),atlas_pixel=[int(ix),int(iy)],triangle_barycentrics=weights.tolist()))
  output.append(dict(index=i,red_pixels=int(red.sum()),counts=dict(counts),unfilled_center_hits=hits,subray_counts=dict(subcounts),unfilled_subray_hits=subhits))
 result=dict(status='DIAGNOSTIC',model_sha256=report['model_sha256'],manifest_sha256=sha(manifest),coverage_report_sha256=sha(folder/'coverage.json'),views=output,method='Every rendered red pixel tested at the exact orthographic camera pixel center. Class0 hit is genuine unfilled sampled atlas on the surface; no-center-hit is raster silhouette only. Triangle barycentrics retained for boundary ambiguity. Optional eight additional rays sample a deterministic 3x3 pixel grid; boundary distance alone does not establish an artifact.')
 if sha(bake/'worker.blend')!=report['model_sha256']:raise ValueError('Model changed during read-only trace')
 filename='subray-classification.json' if subrays else 'center-ray-classification.json'
 (folder/filename).write_text(json.dumps(result,indent=2)+'\n');print([(r['index'],r['counts'])for r in output],flush=True)
if __name__=='__main__':
 args=sys.argv[sys.argv.index('--')+1:];subrays='--subrays' in args
 for folder in args:
  if folder!='--subrays':run(folder,subrays=subrays)
