"""Trace suspicious review regions back to their exact native source receivers."""
import sys,json,math,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).parent))
sys.path.insert(0,str(ROOT/'level-editor/refinement/blender'))
import bpy
from mathutils import Matrix,Vector
from PIL import Image,ImageDraw
from refinement_review import _tree
from texture_camera import orthographic_extents
from source_visibility import first_source_hit
from occlusion_constraints import SourceMaskConstraints
p=ROOT/'level-editor/work/nottingham-refinement/texture-generation/experiments/nottingham-ramp-road-props'
m=json.loads((p/'views.json').read_text());diagnosis=json.loads((p/'source-streak-diagnosis.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(p/'approved-model.blend'));bpy.context.window.scene=bpy.data.scenes[m['scene_name']];bpy.context.view_layer.update()
allobs=[o for o in bpy.data.collections[m['collection_name']].all_objects if o.type=='MESH' and not o.hide_render]
targets=[bpy.data.objects[n] for n in m['object_names']];tree,owners,_=_tree(targets);alltree,allowners,_=_tree(allobs)
source=Image.open(m['source_image']).convert('RGB');sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
con=SourceMaskConstraints(m['source_mask_manifest'],'exterior',sha(m['source_image']),source.size)
s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));out=p/'projection-diagnosis';out.mkdir(exist_ok=True)
regions=[]
for region in diagnosis['regions']:
 view=m['views'][region['view']];matrix=Matrix(view['camera_matrix_world']);right=matrix.to_3x3()@Vector((1,0,0));up=matrix.to_3x3()@Vector((0,1,0));direction=matrix.to_3x3()@Vector((0,0,1));horizontal,vertical=orthographic_extents(view);width,height=m['tile_size'];counts=collections.Counter();pixels=collections.Counter();normals=collections.Counter();witnesses=[]
 x0,y0,x1,y1=region['tile_rectangle']
 for y in range(y0,y1):
  for x in range(x0,x1):
   origin=matrix.translation+right*((x+.5)/width-.5)*horizontal+up*(.5-(y+.5)/height)*vertical;hit,normal,index,_=tree.ray_cast(origin,-direction)
   if index is None:counts['no_target_hit']+=1;continue
   obj=owners[index];sx,sy=math.floor(hit.x),math.floor(-hit.y*s-hit.z*c);pixels[(sx,sy)]+=1;dot=normal.dot(toward);normals[(obj.name,tuple(round(v,5) for v in normal),round(dot,6))]+=1
   allowed=con.allowed_pixel(obj,sx,sy);o=Vector((sx+.5,-(sy+.5)*s,-(sy+.5)*c))+toward*10000;h,n,idx,_=first_source_hit(alltree,allowners,o,-toward,constraints=con,receiver=obj,source_pixel=(sx,sy));first=allowners[idx] if idx is not None else None
   counts['mask_allowed' if allowed else 'mask_rejected']+=1;counts['native_first_receiver' if first==obj else 'native_other_receiver']+=1
   if len(witnesses)<12:witnesses.append(dict(review_pixel=[x,y],source_pixel=[sx,sy],receiver=obj.name,first_receiver=first.name if first else None,normal=list(normal),source_facing=dot,world_hit=list(hit)))
 box=(min(x for x,y in pixels)-4,min(y for x,y in pixels)-4,max(x for x,y in pixels)+5,max(y for x,y in pixels)+5);crop=source.crop(box);overlay=crop.copy();draw=ImageDraw.Draw(overlay)
 for x,y in pixels:draw.point((x-box[0],y-box[1]),fill=(255,0,255))
 paired=Image.new('RGB',(crop.width*2,crop.height));paired.paste(crop);paired.paste(overlay,(crop.width,0));paired.resize((paired.width*6,paired.height*6),Image.Resampling.NEAREST).save(out/(region['feature']+'.png'))
 regions.append(dict(feature=region['feature'],view=region['view'],roi=region['tile_rectangle'],counts=dict(counts),source_pixel_count=len(pixels),source_bbox=list(box),source_pixels=[dict(xy=list(k),review_samples=v) for k,v in sorted(pixels.items())],receivers=[dict(name=k[0],normal=list(k[1]),source_facing=k[2],review_samples=v) for k,v in normals.items()],witnesses=witnesses))
context=m['context_crop'];box=tuple(context[k] for k in ['left','top','right','bottom']);crop=source.crop(box);overlay=crop.copy();draw=ImageDraw.Draw(overlay)
for region,color in zip(regions,[(255,0,255),(0,255,255),(255,30,30)]):
 for sample in region['source_pixels']:
  x,y=sample['xy'];draw.point((x-box[0],y-box[1]),fill=color)
canvas=Image.new('RGB',(crop.width*2,crop.height));canvas.paste(crop);canvas.paste(overlay,(crop.width,0));canvas.resize((canvas.width*5,canvas.height*5),Image.Resampling.NEAREST).save(out/'context-source-ownership.png')
report=dict(asset_id=m['asset_id'],model_sha256=sha(p/'approved-model.blend'),views_sha256=sha(p/'views.json'),source_sha256=sha(m['source_image']),regions=regions)
(out/'native-ray-trace.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps([{k:r[k] for k in ['feature','counts','source_pixel_count','receivers']} for r in regions],indent=2))
