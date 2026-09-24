"""Read-only connected physical UV gap measurements for ray-proven visible receivers."""
import sys,json,hashlib,argparse
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import bpy,numpy as np
from scipy.ndimage import label,binary_dilation
from scipy.spatial import cKDTree
from texture_experiment_paths import selected_experiment
cross=lambda a,b:a[...,0]*b[...,1]-a[...,1]*b[...,0]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('--ray',default='actual-gray-ray-attribution.json');parser.add_argument('--output',default='visible-gap-components.json');parser.add_argument('assets',nargs='+');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
if any(Path(v).name!=v for v in (args.ray,args.output)):raise ValueError('Local evidence filenames required')
for asset in args.assets:
 b=selected_experiment(asset)/'bake-background-support-001';ray=b/args.ray;r=json.loads(ray.read_text())
 if r['model_sha256']!=sha(b/'worker.blend'):raise ValueError('Ray evidence stale')
 targets={}
 for row in r['samples']:
  for s in row['samples']:
   if s.get('provenance')==0:targets.setdefault((s['object'],s['face']),[]).append(s['atlas_pixel'])
 v=json.loads((b/'validation.json').read_text());proofs={e['object']:e['texel_provenance'] for l in v['layers'] for e in l['objects']}
 bpy.ops.wm.open_mainfile(filepath=str(b/'worker.blend'));results=[]
 for (name,face),witnesses in targets.items():
  obj=bpy.data.objects[name];mesh=obj.data;mesh.calc_loop_triangles();proof=proofs[name]
  if sha(proof['path'])!=proof['sha256']:raise ValueError('Provenance drift')
  own=np.load(proof['path'])['ownership'];height,width=own.shape
  mat=obj.data.materials[mesh.polygons[face].material_index];node=next(n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image)
  if hashlib.sha256(node.image.packed_file.data).hexdigest()!=proof['packed_image_sha256']:raise ValueError('Packed atlas drift')
  uv=mesh.uv_layers[node.inputs['Vector'].links[0].from_node.uv_map].data
  positions=np.array([tuple(obj.matrix_world@v.co) for v in mesh.vertices]);samples=[]
  for tri in mesh.loop_triangles:
   if tri.polygon_index!=face:continue
   coords=np.array([tuple(uv[i].uv) for i in tri.loops])*[width,height];lo=np.maximum(np.floor(coords.min(0)).astype(int),0);hi=np.minimum(np.ceil(coords.max(0)).astype(int),[width,height])
   yy,xx=np.mgrid[lo[1]:hi[1],lo[0]:hi[0]];points=np.stack((xx+.5,yy+.5),axis=-1);a,c,d=coords;den=cross(c-a,d-a)
   if abs(den)<1e-10:continue
   u=cross(points-a,d-a)/den;w=cross(c-a,points-a)/den;inside=(u>=-1e-7)&(w>=-1e-7)&(u+w<=1+1e-7)
   world=(1-u[inside]-w[inside])[:,None]*positions[tri.vertices[0]]+u[inside,None]*positions[tri.vertices[1]]+w[inside,None]*positions[tri.vertices[2]]
   samples.append((np.column_stack((xx[inside],yy[inside])),world))
  pixel=np.concatenate([p[0] for p in samples]);world=np.concatenate([p[1] for p in samples]);pixel,indices=np.unique(pixel,axis=0,return_index=True);world=world[indices]
  lo=pixel.min(0);hi=pixel.max(0)+1;shape=(hi[1]-lo[1],hi[0]-lo[0]);inside=np.zeros(shape,bool);inside[pixel[:,1]-lo[1],pixel[:,0]-lo[0]]=True
  classes=own[pixel[:,1],pixel[:,0]];missing=np.zeros(shape,bool);unknown=classes==0;missing[pixel[unknown,1]-lo[1],pixel[unknown,0]-lo[0]]=True
  components,count=label(missing);ids=components[pixel[:,1]-lo[1],pixel[:,0]-lo[0]];donors=classes==2;tree=cKDTree(pixel[donors]) if donors.any() else None
  visible={}
  outside=0
  for x,y in witnesses:
   if lo[0]<=x<hi[0] and lo[1]<=y<hi[1] and components[y-lo[1],x-lo[0]]:visible[int(components[y-lo[1],x-lo[0]])]=visible.get(int(components[y-lo[1],x-lo[0]]),0)+1
   else:outside+=1
  for cid,hits in visible.items():
   selection=ids==cid;pp=pixel[selection];ww=world[selection];component=components==cid
   record=dict(component=cid,texels=int(selection.sum()),face_texels=len(pixel),face_fraction=float(selection.mean()),visible_gray_witnesses=hits,atlas_bbox=[*pp.min(0).tolist(),*(pp.max(0)+1).tolist()],world_min=ww.min(0).tolist(),world_max=ww.max(0).tolist(),touches_face_edge=bool((binary_dilation(component)&~inside).any()))
   if tree:
    distances,nearest=tree.query(pp);wd=np.linalg.norm(ww-world[donors][nearest],axis=1)
    record.update(max_donor_texels=float(distances.max()),p95_donor_texels=float(np.percentile(distances,95)),max_donor_world=float(wd.max()),within16texel8world=int(((distances<=16)&(wd<=8)).sum()))
   results.append(dict(object=name,face=face,component=record))
  if outside:results.append(dict(object=name,face=face,ray_samples_outside_physical_texel_centers=outside))
 report=dict(status='DIAGNOSTIC-ONLY',model_sha256=sha(b/'worker.blend'),ray_evidence_sha256=sha(ray),components=results)
 (b/args.output).write_text(json.dumps(report,indent=2)+'\n');print(asset,len(results),flush=True)
