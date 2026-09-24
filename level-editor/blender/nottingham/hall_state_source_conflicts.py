"""Find source-visible retained surfaces requiring state-specific appearance."""
import sys,json,math,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from freeze_tooling import select_tooling
select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy
from mathutils import Vector
from PIL import Image,ImageChops
from refinement_review import _tree
from refinement_workspace import _review_layers
from reveal_components import filter_receivers
w=WORK/'round-40/assets/nottingham-castle-main-hall';bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));cfg=json.loads((w/'workspace.json').read_text());ls=json.loads((w/'projection-layers.json').read_text());objects=[o for o in bpy.data.collections[cfg['collection_name']].all_objects if o.type=='MESH'and not o.hide_render];r=next(x for x in _review_layers(cfg)if x['projection_label']=='interior-patch-008');rec=set(filter_receivers([o for o in objects if o.get('source_node')in r['receiver_nodes']],r.get('receiver_components'),available_objects=objects));state=next(x for x in json.loads((w/'states-room/states.json').read_text())['states']if x['state']=='covered');tree,owners,_=_tree([o for o in objects if o.name in state['object_names']]);a=Image.open(ls['sources']['exterior']).convert('RGB');b=Image.open(ls['sources']['interior']).convert('RGB');s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));counts=collections.Counter();points=collections.defaultdict(list);scene_tree,scene_owners,_=_tree(objects)
m=json.loads((w/'source-masks.json').read_text());ip=Path(m['mask_inventory']);meta={x['index']:x for x in json.loads(ip.read_text())['masks']}
def mask(n):
 e=meta[n];im=Image.new('L',a.size);im.paste(Image.open(ip.parent/e['png']).convert('L'),tuple(e['box_top_left']));return im
domain=ImageChops.lighter(mask(449),mask(453))
for n in [442,444,445,451]:domain=ImageChops.subtract(domain,mask(n))
for y in range(185,1254):
 for x in range(227,766):
  if not domain.getpixel((x,y)):continue
  origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;_,_,i,_=tree.ray_cast(origin,-toward)
  if i is not None and owners[i]in rec:
   obj=owners[i];_,_,si,_=scene_tree.ray_cast(origin,-toward)
   if si is None or scene_owners[si]!=obj:continue
   k=obj.get('source_node')+'|'+obj.get('projection_component','');different=a.getpixel((x,y))!=b.getpixel((x,y));counts[k+(':different'if different else':same')]+=1
   if different:points[k].append([x,y])
out=w/'inspection';out.mkdir(exist_ok=True);(out/'state-source-conflicts-visible.json').write_text(json.dumps({'counts':dict(counts),'different_pixels':dict(points)},indent=2)+'\n');print(dict(counts))
