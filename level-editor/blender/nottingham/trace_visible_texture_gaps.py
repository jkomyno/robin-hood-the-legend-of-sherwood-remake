"""Read-only camera ray attribution of visible provenance-red samples."""
import sys,json,hashlib,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]/'refinement/blender'))
import bpy,numpy as np
from PIL import Image
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
from texture_camera import orthographic_extents
from reviewed_texture_scope import displayed_objects
args=sys.argv[sys.argv.index('--')+1:];actual_mode=args[:1]==['--actual-gray']
if actual_mode:args=args[1:]
manifest,bake,coverage=map(Path,args);m=json.loads(manifest.read_text())
generated=None;known=None
if actual_mode:
 diagnosis=json.loads((manifest.parent/'diagnosis.json').read_text())
 generation=Path(diagnosis.get('generation_directory',manifest.parent.parent/'generation-short-no-mask-with-lighting-openrouter'))
 if diagnosis.get('generated_sha256') and hashlib.sha256((generation/'generated-preserved.png').read_bytes()).hexdigest()!=diagnosis['generated_sha256']:raise ValueError('Generated evidence drift')
 generated=np.array(Image.open(generation/'generated-preserved.png').convert('RGBA'))
 known=np.array(Image.open(manifest.parent/'mask.png').convert('RGBA'))[:,:,3]
bpy.ops.wm.open_mainfile(filepath=str(bake/'worker.blend'));scene=bpy.data.scenes[m['scene_name']]
objects=displayed_objects(m,[o for o in scene.objects if not o.hide_render and o.get('asset_group')==m['asset_id']])
vertices=[];triangles=[];metadata=[];cache={}
validation=json.loads((bake/'validation.json').read_text());proofs={o['object']:o['texel_provenance'] for l in validation['layers'] for o in l['objects']}
for obj in objects:
 if obj.type!='MESH':continue
 mesh=obj.data;mesh.calc_loop_triangles();base=len(vertices);vertices.extend(obj.matrix_world@v.co for v in mesh.vertices)
 for tri in mesh.loop_triangles:triangles.append(tuple(base+i for i in tri.vertices));metadata.append((obj,tri.polygon_index,tuple(tri.loops)))
 for idx,mat in enumerate(mesh.materials):
  if idx not in {p.material_index for p in mesh.polygons}:continue
  ns=[n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
  if len(ns)!=1:continue
  n=ns[0];proof=proofs[obj.name]
  if hashlib.sha256(n.image.packed_file.data).hexdigest()!=proof['packed_image_sha256']:raise ValueError('Atlas mismatch')
  uv=n.inputs['Vector'].links[0].from_node.uv_map
  cache[(obj.name,idx)]=(np.load(proof['path'])['ownership'],mesh.uv_layers[uv].data)
tree=BVHTree.FromPolygons(vertices,triangles,all_triangles=True);rows=[]
for view in m['views']:
 a=np.array(Image.open(coverage/f"view-{view['index']}-textured.png").convert('RGBA'));rgb=a[:,:,:3].astype(float)
 red=((a[:,:,3]==255)&np.all(rgb==41,axis=2)) if actual_mode else ((a[:,:,3]>127)&(rgb[:,:,0]>80)&(rgb[:,:,0]>2*rgb[:,:,1])&(rgb[:,:,0]>2*rgb[:,:,2]));height,width=red.shape
 matrix=Matrix(view['camera_matrix_world']);right=matrix.to_3x3()@Vector((1,0,0));up=matrix.to_3x3()@Vector((0,1,0));direction=matrix.to_3x3()@Vector((0,0,1));horizontal,vertical=orthographic_extents(view)
 for y,x in zip(*np.where(red)):
  hits=[]
  offsets=[(0,0)] if actual_mode else [(0,0),(-.33,-.33),(0,-.33),(.33,-.33),(-.33,0),(.33,0),(-.33,.33),(0,.33),(.33,.33)]
  for dx,dy in offsets:
   origin=matrix.translation+right*((x+.5+dx)/width-.5)*horizontal+up*(.5-(y+.5+dy)/height)*vertical
   hit,normal,index,_=tree.ray_cast(origin,-direction)
   if index is None:hits.append(dict(offset=[dx,dy],miss=True));continue
   obj,face,loops=metadata[index];own,uvdata=cache[(obj.name,obj.data.polygons[face].material_index)]
   coords=[Vector((*uvdata[i].uv,0)) for i in loops]
   uv=barycentric_transform(hit,*[vertices[i] for i in triangles[index]],*coords)
   h,w=own.shape;ix=max(0,min(w-1,int(math.floor(uv.x*w))));iy=max(0,min(h-1,int(math.floor(uv.y*h))))
   record=dict(offset=[dx,dy],object=obj.name,face=face,world=list(hit),uv=list(uv)[:2],atlas_pixel=[ix,iy],provenance=int(own[iy,ix]),view_facing=float(normal.dot(direction)))
   if actual_mode:
    crop=view['crop'];gx=int(crop['left']+x);gy=int(crop['top']+y)
    record.update(generated_rgba=generated[gy,gx].tolist(),review_known_alpha=int(known[gy,gx]))
   hits.append(record)
  rows.append(dict(view=view['index'],pixel=[int(x),int(y)],samples=hits))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=dict(status='DIAGNOSTIC',model_sha256=sha(bake/'worker.blend'),manifest_sha256=sha(manifest),evidence_sheet_sha256=sha(coverage/('textured.png' if actual_mode else 'coverage.png')),samples=rows,limitations=['Exact-gray actual filtering is diagnostic only; provenance and facing classify each sampled point.' if actual_mode else 'Nine deterministic rays per flagged pixel sample centers and subpixels; rendering antialiasing can include further samples.'])
(bake/('actual-gray-ray-attribution.json' if actual_mode else 'visible-gap-ray-attribution.json')).write_text(json.dumps(r,indent=2)+'\n')
from collections import Counter
print('center',dict(Counter('miss' if row['samples'][0].get('miss') else str(row['samples'][0]['provenance']) for row in rows)))
print('class0faces',dict(Counter((h['object'],h['face']) for row in rows for h in row['samples'] if h.get('provenance')==0)))
