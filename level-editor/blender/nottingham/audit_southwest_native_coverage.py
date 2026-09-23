"""Audit all native135 pixels, including those missed by the stair receiver."""
import sys,json,math,hashlib,collections
from pathlib import Path
import bpy
from mathutils import Vector
from PIL import Image
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from freeze_tooling import select_tooling
select_tooling(WORK/'tooling/58744eeaf71a21e9')
from refinement_review import _tree
from occlusion_constraints import SourceMaskConstraints
from source_visibility import first_source_hit
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=int(sys.argv[sys.argv.index('--')+1]);w=WORK/f'round-{r}/assets/nottingham-southwest-wall-stair';cfg=json.load(open(w/'workspace.json'));bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.window.scene=bpy.data.scenes[cfg['scene_name']];bpy.context.view_layer.update()
obs=[o for o in bpy.data.collections[cfg['collection_name']].all_objects if o.type=='MESH'and not o.hide_render];targets=[o for o in obs if o.get('source_node')=='building-221'];assert len(targets)==1
alltree,owners,_=_tree(obs);own,_,_=_tree(targets);receiver=targets[0];source=Image.open(cfg['source_path']).convert('RGB');con=SourceMaskConstraints(w/'source-masks.json','exterior',sha(cfg['source_path']),source.size)
manpath=Path(json.load(open(w/'source-masks.json'))['mask_inventory']);rec=next(m for m in json.load(open(manpath))['masks']if m['index']==135);mask=Image.open(manpath.parent/rec['png']).convert('L');ox,oy=rec['box_top_left'][:2];crop=(ox-3,oy-3,ox+mask.width+3,oy+mask.height+3);overlay=source.crop(crop);counts=collections.Counter();rows=[]
s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s))
for v in range(mask.height):
 for u in range(mask.width):
  if not mask.getpixel((u,v)):continue
  x,y=ox+u,oy+v;origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,n,i,d=own.ray_cast(origin,-toward);h,n,j,d=first_source_hit(alltree,owners,origin,-toward,constraints=con,receiver=receiver,source_pixel=(x,y));first=owners[j]if j is not None else None;node=first.get('source_node')if first else None;key=('receiver-hit'if i is not None else 'no-receiver')+':'+str(node);counts[key]+=1
  if first==receiver:color=(40,220,40)
  elif node in ['building-219','building-220']:color=(255,190,0)
  else:color=(255,0,255)
  overlay.putpixel((x-crop[0],y-crop[1]),color);rows.append(dict(pixel=[x,y],receiver_hit=i is not None,first_node=node,first_name=first.name if first else None,first_native_allowed=con.allowed_pixel(first,x,y)if first else False))
out=w/'inspection/independent-native135';out.mkdir(exist_ok=True);im=Image.new('RGB',(overlay.width*2,overlay.height));im.paste(source.crop(crop),(0,0));im.paste(overlay,(overlay.width,0));im.resize((im.width*3,im.height*3),Image.Resampling.NEAREST).save(out/'source-vs-full-native.png');report=dict(model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),source_masks_sha256=sha(w/'source-masks.json'),native_mask_sha256=sha(manpath.parent/rec['png']),counts=dict(counts),rows=rows);(out/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(dict(counts))
