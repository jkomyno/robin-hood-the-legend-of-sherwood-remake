"""Classify every native hall source pixel, including rejected receiver pixels."""
import json,sys,math,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy
from mathutils import Vector
from PIL import Image,ImageChops,ImageDraw
from refinement_workspace import _review_layers
from refinement_review import _tree
from reveal_components import filter_receivers,filter_occluders
from source_visibility import first_source_hit
from occlusion_constraints import SourceMaskConstraints
w=Path(sys.argv[sys.argv.index('--')+1]).resolve();cfg=json.loads((w/'workspace.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();objects=[o for o in bpy.data.collections[cfg['collection_name']].all_objects if o.type=='MESH'and not o.hide_render];definitions=_review_layers(cfg);layers={};receiver_layer={}
for d in definitions:
 if d['projection_label']not in ['exterior','interior-patch-008']:continue
 rec=filter_receivers([o for o in objects if o.get('source_node')in d['receiver_nodes']],d.get('receiver_components'),available_objects=objects);occ=filter_occluders([o for o in objects if o.get('source_node')in d['occluder_nodes']],d.get('exclude_occluder_components'),projection_label=d['projection_label'],available_objects=objects);tree,owners,_=_tree(occ);source=Image.open(d['source_path']).convert('RGB');con=SourceMaskConstraints(w/'source-masks.json',d['projection_label'],hashlib.sha256(Path(d['source_path']).read_bytes()).hexdigest(),source.size);layers[d['projection_label']]=(tree,owners,con)
 for o in rec:receiver_layer[o]=d['projection_label']
m=json.loads((w/'source-masks.json').read_text());ip=Path(m['mask_inventory']);meta={r['index']:r for r in json.loads(ip.read_text())['masks']}
def native(n):
 e=meta[n];im=Image.new('L',source.size);im.paste(Image.open(ip.parent/e['png']).convert('L'),tuple(e['box_top_left']));return im
roof_domain=native(453);native_owned=ImageChops.lighter(native(449),roof_domain)
foreign=native(442)
for n in [444,445,451]:foreign=ImageChops.lighter(foreign,native(n))
projection=json.loads((w/'projection-layers.json').read_text());patch=next(p for p in projection['patches']if p['id']=='patch-008')['graphic'];alpha=Image.new('L',source.size);alpha.paste(Image.open(patch['alpha']).convert('L'),tuple(patch['bbox'][:2]))
covered_domain=ImageChops.subtract(native_owned,foreign);revealed_domain=ImageChops.subtract(ImageChops.lighter(native_owned,alpha),ImageChops.subtract(foreign,alpha))
s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));folder=w/'inspection/source-domain';folder.mkdir(parents=True,exist_ok=True)
state_root=Path(json.loads((w/'state-packet.json').read_text())['directory'])
state_layers=json.loads((w/'projection-state-layers.json').read_text())if(w/'projection-state-layers.json').exists()else None
for state in json.loads((state_root/'states.json').read_text())['states']:
 owned=covered_domain if state['state']=='covered'else revealed_domain;box=owned.getbbox()
 if state_layers:
  layers={};receiver_layer={}
  for d in state_layers[state['state']]:
   if d['projection_label']not in ['exterior','interior-patch-008']:continue
   rec=filter_receivers([o for o in objects if o.get('source_node')in d['receiver_nodes']],d.get('receiver_components'),available_objects=objects);occ=filter_occluders([o for o in objects if o.get('source_node')in d['occluder_nodes']],d.get('exclude_occluder_components'),projection_label=d['projection_label'],available_objects=objects);st,so,_=_tree(occ);con=SourceMaskConstraints(w/'source-masks.json',d['projection_label'],hashlib.sha256(Path(d['source_path']).read_bytes()).hexdigest(),source.size);layers[d['projection_label']]=(st,so,con)
   for o in rec:receiver_layer[o]=d['projection_label']
 names=set(state['object_names']);display=[o for o in objects if o.name in names];tree,owners,_=_tree(display);frame=json.loads((Path(state['path'])/'views.json').read_text());source=Image.open(cfg['source_path']if state['state']=='covered'else json.loads((w/'projection-layers.json').read_text())['sources']['interior']).convert('RGB');out=source.crop(box);counts=collections.Counter();roof_counts=collections.Counter();records=collections.defaultdict(list)
 for y in range(box[1],box[3]):
  for x in range(box[0],box[2]):
   if not owned.getpixel((x,y)):continue
   origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,n,i,_=tree.ray_cast(origin,-toward)
   if i is None:key='no_receiver';color=(255,0,0)
   else:
    obj=owners[i];label=receiver_layer.get(obj);identity=obj.get('source_node')+'|'+obj.get('projection_component','')
    if label is None:key='no_projection_layer:'+identity;color=(255,0,0)
    else:
     scene,occ,con=layers[label]
     if not con.allowed_pixel(obj,x,y):key='mask_rejected:'+identity;color=(255,150,0)
     else:
      _,_,j,_=first_source_hit(scene,occ,origin,-toward,constraints=con,receiver=obj,source_pixel=(x,y));first=occ[j]if j is not None else None
      if first!=obj:key='blocked:'+identity+':by:'+str(first.get('source_node')if first else None);color=(255,0,200)
      elif n.dot(toward)<float(obj.get('projection_min_cosine',.05)):key='facing_rejected:'+identity;color=(255,255,0)
      else:key='accepted:'+identity;color=(0,220,80)
   counts[key]+=1
   if roof_domain.getpixel((x,y)):roof_counts[key]+=1
   records[key].append([x,y]);out.putpixel((x-box[0],y-box[1]),color)
 sheet=Image.new('RGB',(out.width*2,out.height+22));sheet.paste(source.crop(box),(0,22));sheet.paste(out,(out.width,22));ImageDraw.Draw(sheet).text((5,4),state['state']+' original / green accepted; orange mask; pink blocker; yellow facing; red no receiver',fill='white');sheet.save(folder/(state['state']+'.png'))
 (folder/(state['state']+'.json')).write_text(json.dumps({'model_sha256':hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),'modified_views_sha256':hashlib.sha256((w/'modified/views.json').read_bytes()).hexdigest(),'state_views_sha256':hashlib.sha256((Path(state['path'])/'views.json').read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(Path(cfg['source_path']if state['state']=='covered'else projection['sources']['interior']).read_bytes()).hexdigest(),'state':state['state'],'domain':('native449 union453 minus separate spires442444445451'if state['state']=='covered'else'(native449 union453 union full patch008alpha) minus (separate spires442444445451 outside patch008alpha)'),'domain_pixels':sum(owned.histogram()[1:]),'full_patch_alpha_pixels':sum(alpha.histogram()[1:]),'crop':box,'counts':dict(counts),'native453_roof_counts':dict(roof_counts),'pixels':dict(records)},indent=2)+'\n');print(state['state'],dict(counts),flush=True)
