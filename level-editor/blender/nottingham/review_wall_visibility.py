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
args=sys.argv[sys.argv.index('--')+1:];w=Path(args[0]).resolve();node=args[1];bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();c=json.loads((w/'workspace.json').read_text());objects=[o for o in bpy.data.collections[c['collection_name']].all_objects if o.type=='MESH' and not o.hide_render];target=[o for o in objects if o.get('source_node')==node];tree,owners,_=_tree(objects);own_tree,own_owners,_=_tree(target);s=math.sin(math.radians(35));co=math.cos(math.radians(35));toward=Vector((0,-co,s));points=[o.matrix_world@v.co for o in target for v in o.data.vertices];xs=[p.x for p in points];ys=[-p.y*s-p.z*co for p in points];box=[math.floor(min(xs)),math.floor(min(ys)),math.ceil(max(xs)),math.ceil(max(ys))];counts={};own=0;visible=[];second_counts={};second_tree,second_owners,_=_tree([o for o in objects if o.get('source_node')!=node])
for y in range(box[1],box[3]+1):
 for x in range(box[0],box[2]+1):
  origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*co))+toward*10000
  a,_,_,_=own_tree.ray_cast(origin,-toward)
  if a is None:continue
  own+=1;hit,_,index,_=tree.ray_cast(origin,-toward);owner=owners[index].get('source_node') if hit is not None else 'none';counts[owner]=counts.get(owner,0)+1
  if owner==node:
   visible.append([x,y]);behind,_,other_index,_=second_tree.ray_cast(origin,-toward);other=second_owners[other_index].get('source_node') if behind is not None else 'none';second_counts[other]=second_counts.get(other,0)+1
report={'node':node,'model_sha256':hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),'source_box':box,'target_footprint_pixels':own,'first_hit_source_counts':counts,'visible_source_pixels':visible,'first_hit_excluding_target_for_visible_pixels':second_counts,'method':'Every source-pixel center over the target projected bounds; independent target-only hit then full visible Working scene first hit.'};(w/'inspection').mkdir(exist_ok=True);(w/'inspection'/f'independent-{node}-visibility.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items()if k!='visible_source_pixels'},flush=True)
