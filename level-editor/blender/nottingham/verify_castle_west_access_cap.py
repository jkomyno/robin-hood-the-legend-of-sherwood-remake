"""Reopen the revised cap and compare actual top corners with source evidence."""
import json,sys,math,hashlib
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
w=WORK/'round-25/assets/nottingham-castle-gate-west-tower';bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));bpy.context.view_layer.update();obj=next(o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('source_node')=='building-330');s,c=math.sin(math.radians(35)),math.cos(math.radians(35));actual=[obj.matrix_world@v.co for v in obj.data.vertices];points=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][330]['points'];rows=[]
for p in points:
 expected=Vector((p['x'],-p['y']/s,p['z_top']/c));v=min(actual,key=lambda v:(v-expected).length);rows.append(dict(expected_source=[p['x'],p['y']-p['z_top']],actual_source=[v.x,-v.y*s-v.z*c],world_corner_error=(v-expected).length))
bm=bmesh.new();bm.from_mesh(obj.data);bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-8 for f in bm.faces);volume=bm.calc_volume(signed=True);bm.free();assert bad==deg==0 and volume>0;assert max(r['world_corner_error']for r in rows)<.001
report=dict(status='PASS',model_sha256=hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),source_node='building-330',vertices=len(actual),faces=len(obj.data.polygons),nonmanifold_edges=bad,degenerate_faces=deg,signed_volume=volume,source_top_corner_rows=rows,minimum_native_height=min(v.z*c for v in actual),maximum_native_height=max(v.z*c for v in actual),inferred_closed_slab_thickness=4)
(w/'inspection/access-cap-actual-mesh.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
from PIL import Image,ImageDraw
crop=(713,1315,811,1440);source=Image.open(w/'reference/source.png').convert('RGB').crop(crop);marked=source.copy();d=ImageDraw.Draw(marked);pts=[(r['actual_source'][0]-crop[0],r['actual_source'][1]-crop[1])for r in rows];d.line(pts+[pts[0]],fill='cyan',width=1)
for i,(x,y)in enumerate(pts):d.ellipse((x-1,y-1,x+1,y+1),fill='yellow');d.text((x+2,y),str(i+1),fill='yellow')
canvas=Image.new('RGB',(source.width*6,source.height*3));canvas.paste(source.resize((source.width*3,source.height*3)),(0,0));canvas.paste(marked.resize((source.width*3,source.height*3)),(source.width*3,0));canvas.save(w/'inspection/access-cap-source-fit.png')
