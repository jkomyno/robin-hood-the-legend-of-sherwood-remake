"""Check first-hit ownership independently inside each observed cap polygon."""
import json,sys,math,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'level-editor/work/nottingham-refinement';W=R/'round-38/assets/nottingham-castle-gate-west-tower';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(R/'tooling/58744eeaf71a21e9')
import bpy
from PIL import Image,ImageDraw,ImageFilter
from mathutils import Vector
from refinement_review import _tree
from occlusion_constraints import SourceMaskConstraints
from source_visibility import first_source_hit
from trace_west_gate_crown import CAPS
bpy.ops.wm.open_mainfile(filepath=str(W/'model.blend'));bpy.context.view_layer.update();objects=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and not o.hide_render];tree,owners,_=_tree(objects);targets=[o for o in objects if o.get('asset_group')==W.name];own,oo,_=_tree(targets);sha=hashlib.sha256((W/'reference/source.png').read_bytes()).hexdigest();constraints=SourceMaskConstraints(W/'source-masks.json','exterior',sha,(2304,3520));s,c=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-c,s));reports=[]
for name,outer,inner in CAPS:
 poly=outer+list(reversed(inner));x0=min(x for x,y in poly)-2;y0=min(y for x,y in poly)-2;x1=max(x for x,y in poly)+3;y1=max(y for x,y in poly)+3;im=Image.new('L',(x1-x0,y1-y0));ImageDraw.Draw(im).polygon([(x-x0,y-y0)for x,y in poly],fill=255);im=im.filter(ImageFilter.MinFilter(5));counts=collections.Counter();witnesses=[]
 for ly in range(im.height):
  for lx in range(im.width):
   if im.getpixel((lx,ly))<255:continue
   x,y=x0+lx,y0+ly;origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*c))+toward*10000;hit,n,i,_=own.ray_cast(origin,-toward)
   if i is None:key='no_receiver'
   else:
    receiver=oo[i];h,nn,j,_=first_source_hit(tree,owners,origin,-toward,constraints=constraints,receiver=receiver,source_pixel=(x,y));first=owners[j]if j is not None else None
    key=('accepted:'+receiver.get('source_node'))if first==receiver and constraints.allowed_pixel(receiver,x,y)else('blocked:'+str(first.get('source_node')if first else None))
   counts[key]+=1
   if not key.startswith('accepted:building-33')and len(witnesses)<20:witnesses.append(dict(pixel=[x,y],result=key))
 reports.append(dict(cap=name,pixel_counts=dict(counts),rejected_witnesses=witnesses))
report=dict(model_sha256=hashlib.sha256((W/'model.blend').read_bytes()).hexdigest(),source_sha256=sha,method='Ray-test every pixel center in the measured cap polygon after two-pixel erosion (declared observation uncertainty). Boundary uncertainty is excluded; every interior ray independently checks exact receiver native mask and full-scene first hit.',caps=reports)
(W/'inspection/cap-source-coverage.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(reports))
