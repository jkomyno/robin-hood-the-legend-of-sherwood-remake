"""Independent source-camera first-hit coverage for one native wall component."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
from freeze_tooling import select_tooling
select_tooling(WORK/'tooling/58744eeaf71a21e9')
from refinement_review import _tree
args=sys.argv[sys.argv.index('--')+1:];w=Path(args[0]).resolve();node=args[1];bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();c=json.loads((w/'workspace.json').read_text());objects=[o for o in bpy.data.collections[c['collection_name']].all_objects if o.type=='MESH' and not o.hide_render];target=[o for o in objects if o.get('source_node')==node and o.get('asset_group')==c['asset_id']];tree,owners,_=_tree(objects);own_tree,own_owners,_=_tree(target);s=math.sin(math.radians(35));co=math.cos(math.radians(35));toward=Vector((0,-co,s));points=[o.matrix_world@v.co for o in target for v in o.data.vertices];xs=[p.x for p in points];ys=[-p.y*s-p.z*co for p in points];box=[math.floor(min(xs)),math.floor(min(ys)),math.ceil(max(xs)),math.ceil(max(ys))];counts={};own=0;visible=[];source_hits=[];second_counts={};second_tree,second_owners,_=_tree([o for o in objects if o.get('source_node')!=node])
for y in range(box[1],box[3]+1):
 for x in range(box[0],box[2]+1):
  origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*co))+toward*10000
  a,_,_,_=own_tree.ray_cast(origin,-toward)
  if a is None:continue
  own+=1;hit,_,index,_=tree.ray_cast(origin,-toward);owner=owners[index].get('source_node') if hit is not None else 'none';counts[owner]=counts.get(owner,0)+1;source_hits.append((x,y,owner))
  if owner==node:
   visible.append([x,y]);behind,_,other_index,_=second_tree.ray_cast(origin,-toward);other=second_owners[other_index].get('source_node') if behind is not None else 'none';second_counts[other]=second_counts.get(other,0)+1
native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][int(node.split('-')[-1])]['points'];expected=[Vector((p['x'],-p['y']/s,p[z]/co))for p in native for z in ('z_bottom','z_top')];profile_error=None if any(o.get('projection_component')for o in target)else max(min((a-b).length for b in points)for a in expected)
report={'native_profile_maximum_corner_distance_world':profile_error,'node':node,'model_sha256':hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),'source_box':box,'target_footprint_pixels':own,'first_hit_source_counts':counts,'visible_source_pixels':visible,'first_hit_excluding_target_for_visible_pixels':second_counts,'method':'Every source-pixel center over the target projected bounds; independent target-only hit then full visible Working scene first hit.'};(w/'inspection').mkdir(exist_ok=True);(w/'inspection'/f'independent-{node}-visibility.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items()if k!='visible_source_pixels'},flush=True)

if node=='building-201':
 from PIL import Image,ImageDraw
 crop=(box[0]-12,box[1]-12,box[2]+12,box[3]+12)
 source=Image.open(c['source_path']).convert('RGB').crop(crop);ownership=source.copy()
 colors={'building-200':(0,220,220),'building-201':(255,225,0),'building-206':(255,80,180)}
 for x,y,owner in source_hits:ownership.putpixel((x-crop[0],y-crop[1]),colors.get(owner,(255,255,255)))
 width=source.width*3;canvas=Image.new('RGB',(width*2,source.height*3+54),(22,24,30));canvas.paste(source.resize((width,source.height*3),Image.Resampling.NEAREST),(0,54));canvas.paste(ownership.resize((width,source.height*3),Image.Resampling.NEAREST),(width,54));draw=ImageDraw.Draw(canvas);draw.text((8,6),'Original source | first-hit ownership over tower platform201 footprint',fill='white');draw.text((8,24),'Cyan: curved wall200 (section1). Yellow: platform201. Pink: turret206.',fill='white');canvas.save(w/'inspection/independent-lower-tower-ownership.png')
