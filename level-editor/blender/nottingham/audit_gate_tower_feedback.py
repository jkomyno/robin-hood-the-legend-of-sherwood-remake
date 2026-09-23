"""Audit the saved tower crown against numbered source pixels and fixed packets."""
import sys,json,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'level-editor/work/nottingham-refinement/round-23/assets/nottingham-castle-gate-east-tower'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
from freeze_tooling import select_tooling
select_tooling(ROOT/'level-editor/work/nottingham-refinement/tooling/58744eeaf71a21e9')
import bpy
from mathutils import Vector
from PIL import Image,ImageDraw
bpy.ops.wm.open_mainfile(filepath=str(W/'model.blend'));bpy.context.view_layer.update()
from refine_church import SIN,COS,fingerprint
from refine_gate_tower_crown_feedback import refine
owned=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==W.name]
objects=[o for o in owned if o.get('projection_component')=='mechanism-upper' or o.get('source_node')=='building-338']
report=json.loads((W/'geometry-report.json').read_text());crop=(940,1110,1110,1280);im=Image.open(W/'reference/source.png').crop(crop).resize((1020,1020));draw=ImageDraw.Draw(im)
def screen(p):return (p.x,-p.y*SIN-p.z*COS)
points=[o.matrix_world@v.co for o in objects for v in o.data.vertices];rows=[]
for row in report['corners']:
 target=Vector((row['native_xyz'][0],-row['native_xyz'][1]/SIN,row['native_xyz'][2]/COS));p=min(points,key=lambda p:(p-target).length);sx,sy=screen(p);x,y=row['source_pixel'];rows.append(dict(index=row['index'],target=[x,y],actual=[sx,sy],residual=math.hypot(sx-x,sy-y)))
 draw.line(((x-crop[0])*6,(y-crop[1])*6,(sx-crop[0])*6,(sy-crop[1])*6),fill='cyan',width=2)
for o in objects:
 for e in o.data.edges:
  a,b=[o.matrix_world@o.data.vertices[i].co for i in e.vertices]
  if min(a.z,b.z)*COS<344:continue
  a,b=screen(a),screen(b);draw.line(tuple((q[0]-crop[0])*6 if k%2==0 else (q[1]-crop[1])*6 for q in [a,b] for k in [0,1]),fill=(255,80,60),width=1)
im.save(W/'inspection/crown-actual-mesh-overlay.png')
before={o.name:fingerprint(o) for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'};refine();after={o.name:fingerprint(o) for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'}
# Projection adds UV data; recipe replaces its own two meshes, so compare the
# generated geometry on successive calls and guard every foreign object.
refine();second={o.name:fingerprint(o) for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'}
assert after==second,'Non-idempotent geometry recipe'
outside=[name for name in before if before[name]!=after[name] and bpy.data.objects[name].get('asset_group')!=W.name];assert not outside,outside
assert max(r['residual'] for r in rows)<.01,rows
out=dict(status='PASS',corners=rows,maximum_construction_residual=max(r['residual'] for r in rows),source_trace_uncertainty_pixels=2,scope='Construction check of actual saved vertices against chosen artwork corners; this is not independent validation of the trace.',geometry_idempotence='PASS',outside_changes=outside,model_sha256=hashlib.sha256((W/'model.blend').read_bytes()).hexdigest());(W/'inspection/crown-mesh-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(out['maximum_construction_residual'],flush=True)
# Reuse the independent ray checker, expanding its packet scope for this audit.
code=(Path(__file__).parent/'verify_workspace_known_rgb.py').read_text().replace("select_tooling(root/'tooling/94116d984f92dbae')","select_tooling(root/'tooling/58744eeaf71a21e9')")
code=code.replace("packets=[w/'modified']","packets=[w/'modified']+[p.parent for p in sorted((w/'inspection').glob('*feedback-v2/**/views.json'))]")
sys.argv=['verify_workspace_known_rgb.py','--',str(W)];exec(compile(code,str(Path(__file__).parent/'verify_workspace_known_rgb.py'),'exec'))
