"""Check every authored ground texel against the saved receiver and scene occluders."""
import sys,json,hashlib,math,collections
from pathlib import Path
import bpy,numpy as np
from PIL import Image
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
from refinement_review import _tree
from source_visibility import first_source_hit
from occlusion_constraints import SourceMaskConstraints
w=WORK/'round-27/assets/nottingham-terrain-ground';c=json.loads((w/'workspace.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.window.scene=bpy.data.scenes[c['scene_name']];objects=[o for o in bpy.data.collections[c['collection_name']].all_objects if o.type=='MESH' and not o.hide_render];g=next(o for o in objects if o.get('source_node')=='ground');tree,owners,_=_tree(objects);own,_,_=_tree([g]);source=Image.open(c['source_path']).convert('RGB');sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();constraints=SourceMaskConstraints(w/'source-masks.json','exterior',sha(c['source_path']),source.size);mask=np.array(Image.open(WORK/'mask-review/inventory-terrain-complete-v7/ground-source-domain.png').convert('L'))>127;s,co=math.sin(math.radians(35)),math.cos(math.radians(35));toward=Vector((0,-co,s));counts=collections.Counter();witness=collections.defaultdict(list);missing=Image.new('RGB',source.size,(0,0,0))
for y,x in zip(*np.where(mask)):
 x=int(x);y=int(y);origin=Vector((x+.5,-(y+.5)*s,-(y+.5)*co))+toward*10000;hit,n,idx,d=own.ray_cast(origin,-toward)
 if idx is None:key='missing-ground-receiver'
 else:
  hit,n,idx,d=first_source_hit(tree,owners,origin,-toward,constraints=constraints,receiver=g,source_pixel=(x,y));other=owners[idx] if idx is not None else None;key='ground-visible' if other==g else 'blocked:'+str(other.get('source_node') if other else None)
 counts[key]+=1
 if key!='ground-visible':
  missing.putpixel((x,y),source.getpixel((x,y)))
  if len(witness[key])<30:witness[key].append([x,y])
report=dict(model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),mask_sha256=sha(WORK/'mask-review/inventory-terrain-complete-v7/ground-source-domain.png'),counts=dict(counts),witnesses=dict(witness),method='All authored positive ground pixel centers intersect the actual saved ground and then the complete scene with receiver-specific mask eligibility. This checks the expected positive domain independently of known-render output.')
out=w/'inspection';out.mkdir(exist_ok=True);(out/'complete-ground-ray-audit.json').write_text(json.dumps(report,indent=2)+'\n');missing.save(out/'unexpected-ground-occlusion.png');print({'expected_source_pixels':sum(counts.values()),'visible_source_pixels':counts['ground-visible'],'unexpected_blocked_pixels':sum(v for k,v in counts.items() if k!='ground-visible')},flush=True)
