"""Classify neutral atlas probes using polygon containment and nearby same-face samples."""
import sys,json,math,hashlib
from pathlib import Path
import bpy,numpy as np
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'refinement/blender'))
from occlusion_constraints import SourceMaskConstraints
from refinement_review import _tree
from source_visibility import first_source_hit
from mathutils import Vector
w=Path(sys.argv[sys.argv.index('--')+1]).resolve();report=json.loads((w/'inspection/source-material-comparison.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));S=math.sin(math.radians(35));C=math.cos(math.radians(35));tow=np.array([0,-C,S]);objects=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and not o.hide_render];targets=[o for o in objects if o.get('asset_group')=='nottingham-north-dormer-house'];tree,owners,_=_tree(objects);source_sha=hashlib.sha256((w/'reference/source.png').read_bytes()).hexdigest();domains={k:SourceMaskConstraints(w/'source-masks.json',k,source_sha,(2304,3520))for k in ['exterior','mission-custom1']};cache={};rows=[];art=Image.open(w/'reference/source.png').convert('RGB')
def weights(p,tri):
 a,b,c=tri;basis=np.array([b-a,c-a]);det=np.linalg.det(basis)
 if abs(det)<1e-14:return None
 u,v=(p-a)@np.linalg.inv(basis);return np.array([1-u-v,u,v])
for probe in report['gray_atlas_suspects']:
 point=np.array(probe['source'])+.5;best=None
 for obj in targets:
  mesh=obj.data;mesh.calc_loop_triangles();vs=np.array([list(obj.matrix_world@v.co)for v in mesh.vertices]);proj=np.column_stack([vs[:,0],-vs[:,1]*S-vs[:,2]*C])
  for tr in mesh.loop_triangles:
   ids=list(tr.vertices);bary=weights(point,proj[ids])
   if bary is None or min(bary)<-1e-7:continue
   depth=float((bary@vs[ids])@tow)
   if best is None or depth>best[0]:best=(depth,obj,tr.polygon_index,list(tr.loops),ids,bary,vs)
 if best is None:rows.append(dict(**probe,classification='numeric-source-triangle-boundary-no-isolated-triangle'));continue
 _,obj,fid,loops,ids,bary,vs=best;mesh=obj.data;mat=mesh.materials[mesh.polygons[fid].material_index];tex=next(n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE'and n.image);im=tex.image;uvnode=tex.inputs['Vector'].links[0].from_node;layer=mesh.uv_layers[uvnode.uv_map];uvs=np.array([list(layer.data[i].uv)for i in loops]);uv=bary@uvs;iw,ih=im.size;ix,iy=np.floor(uv*[iw,ih]).astype(int)
 if im.name not in cache:
  pixels=np.empty(iw*ih*4,np.float32);im.pixels.foreach_get(pixels);cache[im.name]=np.clip(pixels.reshape(ih,iw,4)*255+.5,0,255).astype('uint8')
 atlas=cache[im.name]
 def texel_world(x,y):
  q=np.array([(x+.5)/iw,(y+.5)/ih])
  for tr in mesh.loop_triangles:
   if tr.polygon_index!=fid:continue
   b=weights(q,np.array([list(layer.data[i].uv)for i in tr.loops]))
   if b is not None and min(b)>=-1e-7:return b@vs[list(tr.vertices)]
  return None
 world=texel_world(ix,iy);near=[]
 for dy in range(-4,5):
  for dx in range(-4,5):
   x,y=ix+dx,iy+dy
   if 0<=x<iw and 0<=y<ih and texel_world(x,y)is not None:
    rgb=atlas[y,x,:3]
    if int(rgb.max())-int(rgb.min())>=3:near.append((math.hypot(dx,dy),dx,dy,rgb.tolist()))
 nearest=min(near)if near else None;row=dict(**probe,face=fid,image=im.name,atlas_texel=[int(ix),int(iy)],texel_center_inside_same_polygon=world is not None,nearest_colored_same_polygon_texel=nearest)
 if world is None:row['classification']='rasterized-polygon-boundary'
 else:
  sx,sy=math.floor(world[0]),math.floor(-world[1]*S-world[2]*C);constraints=domains['mission-custom1'if obj.get('source_node')in ['building-553','building-554']else'exterior'];allowed=constraints.allowed_pixel(obj,sx,sy);origin=Vector(world)+Vector(tow)*10000;hit,_,j,_=first_source_hit(tree,owners,origin,-Vector(tow),constraints=constraints,receiver=obj,source_pixel=(sx,sy));first=owners[j]if j is not None else None;row.update(atlas_center_source=[sx,sy],atlas_center_source_domain=allowed,atlas_center_rgb=art.getpixel((sx,sy)),atlas_center_depth_error=(Vector(world)-hit).length if hit is not None else None,atlas_center_first_receiver=first.get('source_node')if first else None);row['classification']='source-domain-raster-boundary'if not allowed else 'occlusion-raster-boundary'if first!=obj or hit is None or (Vector(world)-hit).length>.01 else 'valid-neutral-source-color'if list(art.getpixel((sx,sy)))==probe['atlas'] else 'potential-material-hole'
 rows.append(row)
result=dict(model_sha256=report['model_sha256'],method='For every neutral native-source probe, inspect the sampled texel center within its exact UV polygon, its projected native mask and first-hit receiver, and closest colored texel in the same polygon within four atlas pixels.',probes=rows)
from collections import Counter
result['classification_counts']=dict(Counter(r['classification']for r in rows));(w/'inspection/atlas-boundary-classification.json').write_text(json.dumps(result,indent=2)+'\n');print(result['classification_counts'])
