"""Show every accepted and rejected source ray beside untouched tower artwork."""
import sys,json,math,hashlib,collections
from pathlib import Path
import bpy
from mathutils import Vector
from PIL import Image,ImageDraw,ImageChops
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
from refinement_review import _tree
from occlusion_constraints import SourceMaskConstraints
from source_visibility import first_source_hit
s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s))
for rd,name,box in [(28,'watchtower',(560,60,810,1200)),(27,'northeast-spire',(450,180,555,475))]:
 w=WORK/f'round-{rd}/assets/nottingham-castle-{name}';cfg=json.loads((w/'workspace.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();objects=[o for o in bpy.data.collections[cfg['collection_name']].all_objects if o.type=='MESH' and not o.hide_render];targets=[o for o in objects if o.get('source_node')in cfg['part_ids']];tree,owners,_=_tree(objects);own,ownowners,_=_tree(targets);src=Image.open(w/'reference/source.png').convert('RGB');con=SourceMaskConstraints(w/'source-masks.json','exterior',hashlib.sha256((w/'reference/source.png').read_bytes()).hexdigest(),src.size);orig=src.crop(box);domains=orig.copy();visible=orig.copy();blocked=orig.copy();excluded=orig.copy();counts=collections.Counter();pixels=collections.defaultdict(list)
 for y in range(box[1],box[3]):
  for x in range(box[0],box[2]):
   origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,normal,i,_=own.ray_cast(origin,-toward)
   if i is None:continue
   obj=ownowners[i];p=(x-box[0],y-box[1])
   if not con.allowed_pixel(obj,x,y):key='outside-owned-domain';excluded.putpixel(p,(255,100,0))
   else:
    domains.putpixel(p,(0,180,255));_,_,j,_=first_source_hit(tree,owners,origin,-toward,constraints=con,receiver=obj,source_pixel=(x,y));first=owners[j]if j is not None else None
    if first==obj:key='visible';visible.putpixel(p,(0,255,100))
    else:key='blocked:'+str(first.get('source_node')if first else None);blocked.putpixel(p,(255,0,150))
   counts[key]+=1;pixels[key].append([x,y])
 canvas=Image.new('RGB',(orig.width*5,orig.height+20))
 for k,(label,im)in enumerate([('Original',orig),('Owned domain',domains),('Source visible',visible),('Blocked foreign',blocked),('Mask excluded',excluded)]):canvas.paste(im,(orig.width*k,20));ImageDraw.Draw(canvas).text((orig.width*k+3,3),label,fill='white')
 out=w/'inspection/source-coverage-domain.png';out.parent.mkdir(exist_ok=True);canvas.save(out);(w/'inspection/source-coverage-domain.json').write_text(json.dumps(dict(asset_id=cfg['asset_id'],model_sha256=hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),crop=box,counts=dict(counts),pixels=dict(pixels)),indent=2)+'\n');print(name,dict(counts),flush=True)
