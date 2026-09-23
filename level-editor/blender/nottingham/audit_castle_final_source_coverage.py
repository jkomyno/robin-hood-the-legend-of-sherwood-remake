"""Classify every candidate-owned source pixel by exact saved-mesh ray visibility."""
import sys,json,math,collections,hashlib
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
from refinement_review import _tree
from occlusion_constraints import SourceMaskConstraints
from source_visibility import first_source_hit
w=Path(sys.argv[sys.argv.index('--')+1]).resolve();config=json.loads((w/'workspace.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();objects=[o for o in bpy.data.collections[config['collection_name']].all_objects if o.type=='MESH'and not o.hide_render];targets=[o for o in objects if o.get('source_node')in config['part_ids']and o.get('asset_group')==config['asset_id']];tree,owners,_=_tree(objects);own,ownowners,points=_tree(targets);s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));constraints=SourceMaskConstraints(w/'source-masks.json','exterior',hashlib.sha256((w/'reference/source.png').read_bytes()).hexdigest(),(2304,3520));counts=collections.Counter();witnesses=collections.defaultdict(list);recovered=[]
box=[max(0,int(min(p.x for p in points))),max(0,int(min(-p.y*s-p.z*c for p in points))),min(2304,math.ceil(max(p.x for p in points))),min(3520,math.ceil(max(-p.y*s-p.z*c for p in points)))]
for y in range(box[1],box[3]):
 for x in range(box[0],box[2]):
  if not any(constraints.allowed_pixel(o,x,y)for o in targets):continue
  origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,normal,i,_=own.ray_cast(origin,-toward)
  if i is None:key='no_receiver';details={}
  else:
   obj=ownowners[i];other,n,j,_=first_source_hit(tree,owners,origin,-toward,constraints=constraints,receiver=obj,source_pixel=(x,y));first=owners[j]if j is not None else None;key=obj.get('source_node')+(':visible'if first==obj else ':blocked:'+str(first.get('source_node')if first else None));details=dict(receiver_hit=list(hit),first_hit=list(other)if other else None,depth_gap=(hit-other).length if other else None,cosine=normal.dot(toward))
  if i is not None and first==obj:
   raw,_,ri,_=tree.ray_cast(origin,-toward)
   if ri is not None and owners[ri]!=obj:recovered.append([x,y])
  if i is not None and not constraints.allowed_pixel(ownowners[i],x,y):key='hit_outside_receiver_assignment'
  counts[key]+=1
  if len(witnesses[key])<40:witnesses[key].append(dict(pixel=[x,y],**details))
(w/'inspection').mkdir(exist_ok=True);report=dict(version=1,model_sha256=hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),counts=dict(counts),witnesses=dict(witnesses),method='All pixel centers in the asset bounding rectangle admitted by any receiver source domain; receiver-only intersection then complete-scene reviewed first hit. Hits outside that exact receiver assignment are separately rejected. No_receiver includes broad native masks outside their receiver silhouette and is not an expected-geometry coverage count.');(w/'inspection/final-source-ray-coverage.json').write_text(json.dumps(report,indent=2)+'\n');print(report['counts'],flush=True)

from PIL import Image
source=Image.open(w/'reference/source.png').convert('RGB');crop=tuple(box);left=source.crop(crop);right=left.copy()
for x,y in recovered:right.putpixel((x-box[0],y-box[1]),(0,255,255))
canvas=Image.new('RGB',(left.width*2,left.height));canvas.paste(left,(0,0));canvas.paste(right,(left.width,0));canvas.save(w/'inspection/recovered-source-pixels.png')
(w/'inspection/recovered-source-pixels.json').write_text(json.dumps(dict(model_sha256=report['model_sha256'],count=len(recovered),pixels=recovered),indent=2)+'\n')
print('Recovered exact source pixels:',len(recovered),flush=True)
