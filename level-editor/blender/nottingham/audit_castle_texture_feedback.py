"""Trace native-owned pixels for the three reviewed castle projection defects."""
import json,math,sys,collections
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
from refinement_review import _tree
from PIL import Image,ImageChops
inv=WORK/'mask-review/inventory-v11';metadata=json.loads((inv/'manifest.json').read_text())['masks']
def mask(indices):
 out=Image.new('L',(2304,3520))
 for i in indices:
  m=metadata[i];layer=Image.new('L',out.size);layer.paste(Image.open(inv/m['png']).convert('L'),tuple(m['box_top_left']));out=ImageChops.lighter(out,layer)
 return out
s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));out=WORK/'castle-audit/review4-texture';out.mkdir(exist_ok=True)
for name,rd,includes,excludes in [('castle-east-courtyard-wall',1,[291,292,296,298,300,318],[65,61,63,99,312]),('castle-gate-west-tower',1,[284,285,286],[65,67]),('castle-east-round-tower',5,[293],[])]:
 p=WORK/f'round-{rd}/assets/nottingham-{name}';config=json.loads((p/'workspace.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(p/'model.blend'));bpy.context.view_layer.update();objects=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH' and not o.hide_render];targets=[o for o in objects if o.get('source_node') in config['part_ids']];tree,owners,_=_tree(objects);own,ownowners,_=_tree(targets);allowed=ImageChops.subtract(mask(includes),mask(excludes));allowed.save(out/f'{name}-proposed-mask.png');box=allowed.getbbox();counts=collections.Counter();witnesses=collections.defaultdict(list)
 for y in range(box[1],box[3]):
  for x in range(box[0],box[2]):
   if not allowed.getpixel((x,y)):continue
   origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000
   hit,normal,i,_=own.ray_cast(origin,-toward)
   if i is None:key='no_receiver'
   else:
    hit2,normal2,i2,_=tree.ray_cast(origin,-toward);o=ownowners[i];first=owners[i2] if i2 is not None else None
    key=(o.get('source_node')+':visible' if first==o else o.get('source_node')+':blocked:'+str(first.get('source_node') if first else None))
    if first==o and normal.dot(toward)<float(o.get('projection_min_cosine',.05)):key+=':facing'
   counts[key]+=1
   if len(witnesses[key])<40:witnesses[key].append([x,y])
 report={'asset':config['asset_id'],'counts':dict(counts),'witnesses':dict(witnesses),'properties':{o.get('source_node'):{k:str(v) for k,v in o.items() if 'projection' in k} for o in targets}}
 (out/f'{name}-rays.json').write_text(json.dumps(report,indent=2));print(config['asset_id'],dict(counts),flush=True)
