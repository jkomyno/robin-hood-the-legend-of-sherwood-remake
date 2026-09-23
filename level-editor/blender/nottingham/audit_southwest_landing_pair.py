"""Independently classify every disputed source ray in the composed wall/stair."""
import json,sys,math,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
args=sys.argv[sys.argv.index('--')+1:]if '--'in sys.argv else [];wall_round=int(args[0])if args else 31;stair_round=int(args[1])if len(args)>1 else wall_round
wall=WORK/f'round-{wall_round}/assets/nottingham-southwest-curtain-wall-north';stair=WORK/f'round-{stair_round}/assets/nottingham-southwest-wall-stair';pair=wall/'inspection'/(args[2] if len(args)>2 else 'composite')
sys.path.insert(0,str(Path(__file__).parent));from render_slots import acquire
acquire();from freeze_tooling import select_tooling
select_tooling(WORK/'tooling/58744eeaf71a21e9')
import bpy
from mathutils import Vector
from refinement_review import _tree
from PIL import Image,ImageDraw
bpy.ops.wm.open_mainfile(filepath=str(pair/'model.blend'));bpy.context.view_layer.update();cfg=json.load(open(pair/'workspace.json'));objs=[o for o in bpy.data.collections[cfg['collection_name']].all_objects if o.type=='MESH'and not o.hide_render and o.get('asset_group')==cfg['asset_id'] and o.get('source_node')in ['building-219','building-220','building-221']];assert len(objs)==3,[(o.name,o.get('source_node'))for o in objs];tree,owners,_=_tree(objs)
s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));old=json.load(open(pair/'source-rays.json'));assert old['wall_model_sha256']==hashlib.sha256((wall/'model.blend').read_bytes()).hexdigest();assert old['stair_model_sha256']==hashlib.sha256((stair/'model.blend').read_bytes()).hexdigest();assert old['composite_model_sha256']==hashlib.sha256((pair/'model.blend').read_bytes()).hexdigest();rows=[];counts=collections.Counter();im=Image.open(stair/'reference/source.png').convert('RGB');crop=(665,1495,755,1600);view=im.crop(crop).resize((540,630),Image.Resampling.NEAREST);draw=ImageDraw.Draw(view)
for r in old['rows']:
 x,y=r['pixel'];origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,n,i,d=tree.ray_cast(origin,-toward);o=owners[i]if i is not None else None;key=o.get('source_node')if o else 'no_hit';counts[key]+=1
 if not r['stair_strictly_front']:
  rows.append(dict(source_pixel=[x,y],first_hit_node=key,first_hit_component=o.get('projection_component')if o else None,first_hit_name=o.name if o else None,source_rgb=im.getpixel((x,y)),world_hit=list(hit)if hit else None));px=(x-crop[0])*6;py=(y-crop[1])*6;draw.ellipse((px-2,py-2,px+2,py+2),fill='red');draw.text((px+3,py),str(len(rows)),fill='cyan')
view.save(pair/'independent-fringe-source.png');report=dict(composite_model_sha256=hashlib.sha256((pair/'model.blend').read_bytes()).hexdigest(),stair_model_sha256=hashlib.sha256((stair/'model.blend').read_bytes()).hexdigest(),wall_model_sha256=hashlib.sha256((wall/'model.blend').read_bytes()).hexdigest(),method='Independent nearest-triangle ray through all three composed saved meshes; no depth tolerance or mask skip.',whole_domain_first_hit_counts=dict(counts),fringe_rows=rows);(pair/'independent-fringe-rays.json').write_text(json.dumps(report,indent=2)+'\n');print(dict(counts));print([(r['source_pixel'],r['first_hit_node'])for r in rows])
