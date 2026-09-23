"""Trace the seven crown merlons and preserve the independent winch states."""
import json,hashlib,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';ASSET='nottingham-castle-gate-east-tower'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
# Ordered outer cap endpoints in native x/y. Heights are 375 / 362. The
# seventh merlon crosses the separate rear closure338. Top-facing cap edges
# are traced, not the lower moulding line. Uncertainty: two source pixels.
STATIONS=[(1029,1516),(1007,1517),(978,1526),(975,1536),(958,1554),(958,1565),(962,1580),(983,1594),(998,1595),(1027,1595),(1049,1590),(1075,1579),(1084,1572),(1097,1545),(1090,1543),(1068,1528),(1056,1518)]
RAISED={1,3,5,6,8,10,11,14}
def refine():
 import bpy,bmesh
 from mathutils import Vector
 from refine_church import replace_native,SIN,COS
 owned=[o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==ASSET]
 upper=next(o for o in owned if o.get('projection_component')=='mechanism-upper')
 rear=next(o for o in owned if o.get('source_node')=='building-338')
 native=json.loads((WORK/'source-states/level.json').read_text())['sight_obstacles'][337]['points']
 pairs=[(5,6),(4,7),(3,8),(2,9),(1,10),(0,11),(17,12),(16,13),(15,14)]
 cumulative=[0.0]
 for (a,b),(c,d) in zip(pairs,pairs[1:]):cumulative.append(cumulative[-1]+math.hypot(native[c]["x"]-native[a]["x"],native[c]["y"]-native[a]["y"]))
 def nearest(x,y):
  best=None
  for seg,((a,b),(c,d)) in enumerate(zip(pairs,pairs[1:])):
   A=native[a];B=native[c];vx=B['x']-A['x'];vy=B['y']-A['y'];t=max(0,min(1,((x-A['x'])*vx+(y-A['y'])*vy)/(vx*vx+vy*vy)));q=(A['x']+t*vx,A['y']+t*vy);dist=(q[0]-x)**2+(q[1]-y)**2
   inner=(native[b]['x']+t*(native[d]['x']-native[b]['x']),native[b]['y']+t*(native[d]['y']-native[b]['y']))
   if best is None or dist<best[0]:best=(dist,q,inner,cumulative[seg]+t*(cumulative[seg+1]-cumulative[seg]))
  return best[1:]
 sections=[]
 for x,y in STATIONS:
  outer,inner,parameter=nearest(x,y);dx,dy=inner[0]-outer[0],inner[1]-outer[1]
  sections.append((outer,inner,(x,y),(x+dx,y+dy),parameter))
 original=list(sections)
 inserted=[]
 for j,(a,b) in enumerate(pairs[1:-1],1):
  parameter=cumulative[j]
  for i,(left,right) in enumerate(zip(original,original[1:])):
   if left[4]+1e-5<parameter<right[4]-1e-5:
    t=(parameter-left[4])/(right[4]-left[4]);top=tuple(left[2][k]+t*(right[2][k]-left[2][k]) for k in range(2));inside=tuple(left[3][k]+t*(right[3][k]-left[3][k]) for k in range(2));inserted.append(((native[a]["x"],native[a]["y"]),(native[b]["x"],native[b]["y"]),top,inside,parameter));break
 sections=sorted(sections+inserted,key=lambda s:s[4])
 verts=[];idx={};faces={}
 def v(p):
  p=tuple(round(float(q),5) for q in p)
  if p not in idx:idx[p]=len(verts);verts.append(p)
  return idx[p]
 def face(ps):
  f=tuple(v(p) for p in ps);key=tuple(sorted(f))
  if key in faces:del faces[key]
  else:faces[key]=f
 def point(s,inner,z):
  xy=s[inner] if z<=345 else s[2+inner];return (*xy,z)
 def cell(a,b,z0,z1):
  p=[point(a,0,z0),point(b,0,z0),point(b,1,z0),point(a,1,z0),point(a,0,z1),point(b,0,z1),point(b,1,z1),point(a,1,z1)]
  for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:face([p[i] for i in f])
 for i,(a,b) in enumerate(zip(sections,sections[1:])):
  cell(a,b,235,345);cell(a,b,345,362)
  middle=(a[4]+b[4])/2
  original_index=next(j for j,(left,right) in enumerate(zip(original,original[1:])) if left[4]-1e-5<=middle<=right[4]+1e-5)
  if original_index in RAISED:cell(a,b,362,375)
 replace_native(upper,verts,list(faces.values()))
 # Rear merlon closes the C-shaped upper shell; its lower room wall keeps
 # the former footprint and blends to the measured cap just above the floor.
 a,b=sections[0],sections[-1]
 rv=[(*p,110) for p in [a[0],b[0],b[1],a[1]]]+[(*p,345) for p in [a[0],b[0],b[1],a[1]]]+[(*p,375) for p in [a[2],b[2],b[3],a[3]]]
 rf=[(3,2,1,0),(8,9,10,11)]
 for base in [0,4]:
  for i in range(4):j=(i+1)%4;rf.append((base+i,base+j,base+4+j,base+4+i))
 replace_native(rear,rv,rf)
 report={}
 for obj in [upper,rear]:
  bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-8 for f in bm.faces);bm.to_mesh(obj.data);bm.free();assert not bad and not deg,(obj.name,bad,deg)
  obj['projection_min_cosine']=.05;obj['measured_merlon_count']=7;report[obj.name]={'nonmanifold_edges':bad,'degenerate_faces':deg}
 rows=[]
 for i,(x,y) in enumerate(STATIONS):
  for height in sorted({362,375} if i and ((i-1 in RAISED)!=(i in RAISED)) else {375 if i in RAISED else 362}):rows.append({'index':len(rows)+1,'source_pixel':[x,y-height],'native_xyz':[x,y,height],'role':'outer cap shoulder','uncertainty_pixels':2})
 return {'measured_merlon_count':7,'corners':rows,'topology':report,'changes':['Replaced eight uniformly spaced crown crenels with seven source-traced merlons.','Raised the separate rear closure to form the seventh merlon and aligned its endpoints.','Retained the lower room cutaway, floor and independent winch endpoint meshes.'],'limitations':['Rear concealment and crown thickness are constrained by the retained native annulus; cap observations have about two pixels uncertainty.','The crown footprint blends into the old upper tower wall below the parapet.']}
def main():
 sys.path.insert(0,str(Path(__file__).parent));from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 tooling=select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy,refinement_workspace as rw
 old=WORK/'round-3/assets'/ASSET;new=WORK/'round-23/assets'/ASSET;c=json.loads((old/'workspace.json').read_text())
 if not new.exists():
  bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
  rw.prepare(new,asset_id=ASSET,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',projection_manifest=old/'projection-layers.json',source_mask_manifest=old/'source-masks.json',width=384,height=512,context_padding=48,framing_padding=1.15)
 bpy.ops.wm.open_mainfile(filepath=str(new/'model.blend'));report=refine();report.update(tooling=tooling,source_sha256=sha(old/'reference/source.png'));write(new/'geometry-report.json',report)
 from PIL import Image,ImageDraw
 (new/'inspection').mkdir(exist_ok=True)
 crop=(940,1110,1110,1280);image=Image.open(old/'reference/source.png').crop(crop).resize((1020,1020));draw=ImageDraw.Draw(image)
 for row in report['corners']:
  x,y=row['source_pixel'];px=(x-crop[0])*6;py=(y-crop[1])*6;draw.ellipse((px-3,py-3,px+3,py+3),fill='red');draw.text((px+4,py),str(row['index']),fill='yellow')
 image.save(new/'inspection/crown-numbered-corners.png')
 Image.open(old/'reference/source.png').crop(crop).resize((1020,1020)).save(new/'inspection/crown-source-unmarked.png')
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(new/'model.blend'));rw.modified(new)
 write(new/'candidate.json',dict(version=1,asset_id=ASSET,status='refinement-in-progress',geometry_refined=True,geometry_reviewed=False,recipe=str(Path(__file__).resolve()),model_sha256=sha(new/'model.blend'),modified_views_sha256=sha(new/'modified/views.json'),changes=report['changes'],limitations=report['limitations']))
if __name__=='__main__':main()
