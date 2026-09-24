"""Read-only floor-domain witnesses for the hall revealed source."""
import sys,json,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from v15_houses_prepare import WORK,write,sha
from freeze_tooling import select_tooling
from render_slots import acquire
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy
from mathutils import Vector
from refinement_review import _tree
from asset_reference_views import state_objects
from occlusion_constraints import SourceMaskConstraints
w=WORK/'round-38/assets/nottingham-castle-main-hall';bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();cfg=json.loads((w/'workspace.json').read_text());manifest=json.loads((w/'projection-layers.json').read_text());objects=list(bpy.data.collections[cfg['collection_name']].all_objects);selected=state_objects(objects,cfg['asset_id'],'patch-008',manifest['projection_reviews']['patch-008']['render_visibility'],'revealed');tree,owners,points=_tree(selected);floor=next(o for o in selected if o.get('projection_component')=='castle-hall-floor');own,ownowners,_=_tree([floor]);mask=SourceMaskConstraints(w/'source-masks.json','interior-patch-008',sha(Path(manifest['sources']['interior'])),(2304,3520));s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));down=Vector((0,-s,-c));rows=[]
for x,y in [(475,646),(498,648),(520,660),(534,675),(544,699),(559,729),(601,742),(628,762),(646,779),(617,799),(580,820),(495,765),(438,711),(403,716),(415,730)]:
 origin=Vector((x+.5,0,0))+down*(y+.5)+toward*10000;hit,normal,i,d=tree.ray_cast(origin,-toward);fh,fn,fi,fd=own.ray_cast(origin,-toward);row=dict(pixel=[x,y],first_object=owners[i].name if i is not None else None,first_node=owners[i].get('source_node')if i is not None else None,component=owners[i].get('projection_component')if i is not None else None,floor_allowed=mask.allowed_pixel(floor,x,y),floor_hit=fh is not None,first_distance=d,floor_distance=fd);rows.append(row)
write(WORK/'castle-audit/v15-floor-independent/source-witnesses.json',dict(model_sha256=sha(w/'model.blend'),rows=rows));print(json.dumps(rows,indent=2),flush=True)

from PIL import Image,ImageDraw
from collections import Counter
proposal=json.loads((WORK/'castle-audit/v15-floor-independent/floor-domain-expansion-proposal.json').read_text());domain=Image.new('L',(2304,3520));ImageDraw.Draw(domain).polygon(proposal['polygon'],fill=255);inventory_path=Path(json.loads((w/'source-masks.json').read_text())['mask_inventory']);inventory={r['index']:r for r in json.loads(inventory_path.read_text())['masks']}
for n in proposal['native_exclusions']:
 row=inventory[n];im=Image.open(inventory_path.parent/row['png']).convert('L');domain.paste(0,tuple(row['box_top_left'])+(row['box_top_left'][0]+im.width,row['box_top_left'][1]+im.height),im)
counts=Counter();samples={};src=Image.open(manifest['sources']['interior']).convert('RGB');marked=src.copy();bbox=domain.getbbox()
for y in range(bbox[1],bbox[3]):
 for x in range(bbox[0],bbox[2]):
  if not domain.getpixel((x,y))or mask.allowed_pixel(floor,x,y):continue
  origin=Vector((x+.5,0,0))+down*(y+.5)+toward*10000;hit,normal,i,d=tree.ray_cast(origin,-toward);fh,fn,fi,fd=own.ray_cast(origin,-toward)
  key='no-floor'if fi is None else('floor-visible'if i is not None and owners[i]==floor else 'blocked:'+str(owners[i].get('source_node')if i is not None else None));counts[key]+=1
  if len(samples.setdefault(key,[]))<20:samples[key].append([x,y])
  marked.putpixel((x,y),(0,255,128)if key=='floor-visible'else(255,180,0))
write(WORK/'castle-audit/v15-floor-independent/new-domain-census.json',dict(model_sha256=sha(w/'model.blend'),counts=dict(counts),samples=samples,scope='Newly authorized source floor domain minus existing531 and all retained native furniture/parapet exclusions. First-hit against actual revealed hall meshes.'))
crop=(330,610,690,890);canvas=Image.new('RGB',(720,280));canvas.paste(src.crop(crop),(0,0));canvas.paste(marked.crop(crop),(360,0));canvas.resize((1440,560)).save(WORK/'castle-audit/v15-floor-independent/new-domain-census.png');print('NEW_DOMAIN',dict(counts),flush=True)
