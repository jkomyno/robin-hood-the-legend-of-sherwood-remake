"""Project the actual narrow merlon shoulders and classify their occlusion."""
import json,sys,math,collections,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'level-editor/work/nottingham-refinement';W=R/'round-38/assets/nottingham-castle-gate-west-tower';sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
acquire()
import bpy
from PIL import Image,ImageDraw
from mathutils import Vector,Matrix
bpy.ops.wm.open_mainfile(filepath=str(W/'model.blend'));cfg=json.loads((W/'workspace.json').read_text());objects=[o for o in bpy.data.collections[cfg['collection_name']].all_objects if o.type=='MESH'and o.get('asset_group')==W.name];co=math.cos(math.radians(35));si=math.sin(math.radians(35));points=[o.matrix_world@v.co for o in objects for v in o.data.vertices if (o.matrix_world@v.co).z*co>=330];target=sum(points,Vector())/len(points);f=json.loads((W/'modified/views.json').read_text())['views'][7];mat=Matrix(f['camera_matrix_world']);direction=mat.to_3x3()@Vector((0,0,-1));mat.translation=target-direction*10000;screen=[mat.inverted()@p for p in points];cx=(max(p.x for p in screen)+min(p.x for p in screen))/2;cy=(max(p.y for p in screen)+min(p.y for p in screen))/2;mat.translation+=mat.to_3x3()@Vector((cx,cy,0));scale=max(max(p.x for p in screen)-min(p.x for p in screen),max(p.y for p in screen)-min(p.y for p in screen))*1.16
im=Image.open(W/'inspection/crown-closeup/view-7-solid.png').convert('RGB');overlay=im.copy();draw=ImageDraw.Draw(overlay);reports=[]
for node,index in [('building-331',30),('building-332',74)]:
 o=next(o for o in objects if o.get('source_node')==node);face=o.data.polygons[index];world=[o.matrix_world@o.data.vertices[i].co for i in face.vertices];local=[mat.inverted()@p for p in world];projected=[(192+p.x/scale*384,192-p.y/scale*384)for p in local];mask=Image.new('L',(384,384));ImageDraw.Draw(mask).polygon(projected,fill=255);counts=collections.Counter();normal=(world[1]-world[0]).cross(world[2]-world[0]).normalized();planarity=max(abs((p-world[0]).dot(normal))for p in world);assert planarity<.001;draw.line(projected+[projected[0]],fill='yellow',width=1)
 for py in range(384):
  for px in range(384):
   if not mask.getpixel((px,py)):continue
   origin=mat@Vector(((px+.5-192)/384*scale,(192-py-.5)/384*scale,0));hits=[]
   for other in objects:
    inv=other.matrix_world.inverted();ok,p,n,idx=other.ray_cast(inv@origin,(inv.to_3x3()@direction).normalized())
    if ok:hits.append(((other.matrix_world@p-origin).length,other,idx))
   if not hits:continue
   _,first,idx=min(hits,key=lambda r:r[0]);key='visible-shoulder'if first==o and idx==index else first.get('source_node')+':face'+str(idx);counts[key]+=1
   if key=='visible-shoulder':overlay.putpixel((px,py),(255,0,255))
 reports.append(dict(node=node,face=index,polygon_vertices=len(world),world_area=face.area,world_planarity_error=planarity,projected_corners=projected,normal_view_cosine=abs(normal.dot(direction)),pixel_first_hits=dict(counts),native_vertices=[[p.x,-p.y*si,p.z*co]for p in world]))
canvas=Image.new('RGB',(768,384));canvas.paste(im,(0,0));canvas.paste(overlay,(384,0));canvas.resize((1536,768),Image.Resampling.NEAREST).save(W/'inspection/shoulder-visibility.png');(W/'inspection/shoulder-visibility.json').write_text(json.dumps(dict(model_sha256=hashlib.sha256((W/'model.blend').read_bytes()).hexdigest(),faces=reports,method='Yellow outlines project complete actual saved rectangular shoulders. Magenta pixels ray-hit those faces first; other first hits classify silhouette overlap, not detached geometry.'),indent=2)+'\n');print(json.dumps(reports))
