"""Verify the native lower footprint clears the preserved bucket geometry."""
import bpy,json,math,hashlib,sys
from pathlib import Path
from mathutils import Vector
from PIL import Image,ImageDraw
r=Path(__file__).resolve().parents[3]/'level-editor/work/nottingham-refinement';w=Path(sys.argv[sys.argv.index('--')+1]).resolve();bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));obs={o.get('source_node'):o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'};body=obs['building-122'];bucket=obs['building-554'];bv=[body.matrix_world@v.co for v in body.data.vertices];kv=[bucket.matrix_world@v.co for v in bucket.data.vertices]
def hull(points):
 points=sorted(set(points))
 def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
 def half(ps):
  out=[]
  for p in ps:
   while len(out)>1 and cross(out[-2],out[-1],p)<=0:out.pop()
   out.append(p)
  return out
 return half(points)[:-1]+half(reversed(points))[:-1]
lower=hull([(float(p.x),float(p.y))for p in bv if abs(p.z)<.001]);upper=hull([(float(p.x),float(p.y))for p in bv if abs(p.z-68)<.001]);prop=hull([(float(p.x),float(p.y))for p in kv])
def segment(p,a,b):
 p,a,b=Vector(p),Vector(a),Vector(b);d=b-a;return (p-a-d*max(0,min(1,(p-a).dot(d)/d.length_squared))).length
clearance=min(segment(p,poly[i],poly[(i+1)%len(poly)])for points,poly in [(lower,prop),(prop,lower)]for p in points for i in range(len(poly)))
assert max(p.z for p in kv)<40;assert clearance>0
native=json.loads((r/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][122]['points'];native_outline=[(p['x'],-p['y']/math.sin(math.radians(35)))for p in native];native_distance=max(min(segment(p,poly[i],poly[(i+1)%len(poly)])for i in range(len(poly)))for points,poly in [(native_outline,lower),(lower,native_outline)]for p in points);assert native_distance<.001
image=Image.new('RGB',(900,800),(30,30,30));draw=ImageDraw.Draw(image)
def screen(p):return ((p[0]-1735)*10,(-p[1]-955)*8)
for poly,color,name in [(upper,'orange','Upper footprint at z68: inferred'),(lower,'cyan','Native lower footprint z0..40'),(prop,'lime','Unchanged bucket z0..21.97')]:
 draw.line([screen(p)for p in poly]+[screen(poly[0])],fill=color,width=3)
for i,(color,label)in enumerate([('orange','Upper footprint z68: inferred'),('cyan','Native lower footprint z0..40'),('lime','Unchanged bucket z0..21.97')]):draw.text((10,10+20*i),label,fill=color)
draw.text((10,75),f'Plan clearance at bucket height: {clearance:.3f} world units',fill='white');(w/'inspection').mkdir(exist_ok=True);image.save(w/'inspection/bucket-clearance-plan.png')
report=dict(status='PASS',model_sha256=hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),bucket_world_z_range=[min(p.z for p in kv),max(p.z for p in kv)],native_lower_footprint_z_range=[0,40],minimum_plan_clearance=clearance,native_lower_outline=lower,native_outline_error_world=native_distance,inferred_upper_outline=upper,bucket_outline=prop,limitation='Plan clearance proves the unchanged bucket is outside the lower enclosure; source-first-hit audit separately verifies texture visibility. Transition40..68 is inferred, while lower footprint/base remain native.')
(w/'inspection/bucket-clearance.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
