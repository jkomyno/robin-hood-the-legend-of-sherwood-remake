"""Bind the eastern crown's actual saved corner fits and connected topology."""
import json,sys,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'level-editor/work/nottingham-refinement';W=R/'round-43/assets/nottingham-castle-gate-east-tower';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
import bpy,bmesh
from PIL import Image,ImageDraw
from refine_east_gate_crown_complete import CAPS
bpy.ops.wm.open_mainfile(filepath=str(W/'model.blend'));objects=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('asset_group')==W.name and(o.get('projection_component')=='mechanism-upper'or o.get('source_node')=='building-338')];s,c=math.sin(math.radians(35)),math.cos(math.radians(35));points=[];records=[]
for obj in objects:
 bm=bmesh.new();bm.from_mesh(obj.data);assert all(e.is_manifold for e in bm.edges);assert all(f.calc_area()>1e-8 for f in bm.faces);assert bm.calc_volume(signed=True)>0;bm.free();ps=[obj.matrix_world@v.co for v in obj.data.vertices];pixels=[[p.x,-p.y*s-p.z*c]for p in ps];points.extend(pixels);records.append(dict(name=obj.name,source_node=obj.get('source_node'),projection_component=obj.get('projection_component'),vertices=pixels,native_heights=[p.z*c for p in ps],edges=[list(e.vertices)for e in obj.data.edges]))
rows=[]
for name,outer,inner in CAPS:
 for role,ps in [('outer',outer),('inner',inner)]:
  for pixel in ps:
   error=min(math.dist(pixel,p)for p in points);assert error<.002,(name,pixel,error);rows.append(dict(cap=name,role=role,source_pixel=pixel,construction_residual_pixels=error))
report=dict(status='PASS',model_sha256=hashlib.sha256((W/'model.blend').read_bytes()).hexdigest(),measured_cap_count=8,actual_meshes=records,corner_construction_checks=rows,nonmanifold_edges=0,degenerate_faces=0);(W/'inspection/crown-geometry-proof.json').write_text(json.dumps(report,indent=2)+'\n')
box=(945,1120,1110,1255);scale=5;source=Image.open(W/'reference/source.png').convert('RGB').crop(box).resize((825,675),Image.Resampling.NEAREST);overlay=source.copy();draw=ImageDraw.Draw(overlay)
def xy(p):return((p[0]-box[0])*scale,(p[1]-box[1])*scale)
for obj in records:
 for a,b in obj['edges']:
  if min(obj['native_heights'][a],obj['native_heights'][b])>=315:draw.line((xy(obj['vertices'][a]),xy(obj['vertices'][b])),fill='cyan',width=1)
trace=Image.open(R/'castle-audit/east43-crown/numbered-corners.png').resize((825,675));canvas=Image.new('RGB',(2475,702),'white')
for i,im in enumerate([source,trace,overlay]):canvas.paste(im,(i*825,27))
draw=ImageDraw.Draw(canvas)
for i,label in enumerate(['Untouched source','Eight independently traced caps','Actual saved crown edges']):draw.text((i*825+4,8),label,fill='black')
canvas.save(W/'inspection/crown-source-comparison.png');print('PASS32 measured cap corners and watertight positive-volume crown meshes')
