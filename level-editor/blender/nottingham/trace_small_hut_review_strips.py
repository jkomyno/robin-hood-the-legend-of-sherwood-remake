"""Read-only mapping of two narrow review strips to their saved source receivers."""
import sys,json,math,hashlib,collections
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[3];w=ROOT/'level-editor/work/nottingham-refinement/texture-generation/projection-corrections/v4/nottingham-village-small-hut'
bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));data=json.loads((w/'modified/views.json').read_text());scene=bpy.context.scene;verts=[];faces=[];lookup=[]
for name in (data.get('render_object_names') or data['object_names']):
 o=bpy.data.objects[name];offset=len(verts);verts.extend(o.matrix_world@v.co for v in o.data.vertices);o.data.calc_loop_triangles()
 for t in o.data.loop_triangles:faces.append(tuple(offset+i for i in t.vertices));lookup.append((o,t.polygon_index))
tree=BVHTree.FromPolygons(verts,faces,all_triangles=True);width,height=data['tile_size'];scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.resolution_percentage=100;camera=bpy.data.cameras.new('Trace camera');camera.type='ORTHO';view=data['views'][1];camera.ortho_scale=view['ortho_scale'];frame=camera.view_frame(scene=scene);left,right=min(p.x for p in frame),max(p.x for p in frame);bottom,top=min(p.y for p in frame),max(p.y for p in frame);matrix=Matrix(view['camera_matrix_world']);direction=matrix.to_3x3()@Vector((0,0,-1));s,c=math.sin(math.radians(35)),math.cos(math.radians(35));tow=Vector((0,-c,s));known=Image.open(w/'modified/views/view-1-known.png').convert('L');src=Image.open(w/'reference/source.png').convert('RGB');crop=(340,2745,470,2910);overlay=src.crop(crop);points=[];rows=[]
for label,box,color in [('roof-strip',(300,130,325,230),(255,0,255)),('body-strip',(140,310,275,345),(0,255,255))]:
 groups=collections.defaultdict(list)
 for y in range(box[1],box[3]):
  for x in range(box[0],box[2]):
   if known.getpixel((x,y))<=127:continue
   origin=matrix@Vector((left+(x+.5)*(right-left)/width,bottom+(height-y-.5)*(top-bottom)/height,0));hit,n,i,_=tree.ray_cast(origin,direction)
   if hit is None:continue
   o,face=lookup[i];sx,sy=math.floor(hit.x),math.floor(-hit.y*s-hit.z*c);groups[(o.name,face,round(n.dot(tow),6))].append([x,y,sx,sy])
   if crop[0]<=sx<crop[2] and crop[1]<=sy<crop[3]:overlay.putpixel((sx-crop[0],sy-crop[1]),color)
 for (name,face,cos),hits in groups.items():rows.append(dict(region=label,object=name,face=face,source_facing_cosine=cos,review_pixels=len(hits),source_pixels=sorted({(v[2],v[3])for v in hits}),review_box=box))
ins=w/'inspection';overlay.resize((780,990),Image.Resampling.NEAREST).save(ins/'narrow-strips-source.png');report=dict(model_sha256=hashlib.sha256((w/'model.blend').read_bytes()).hexdigest(),modified_views_sha256=hashlib.sha256((w/'modified/views.json').read_bytes()).hexdigest(),view=1,regions=rows,legend='Magenta roof strip; cyan body strip. Pixel centers traced from known view pixels through the saved mesh.');(ins/'narrow-strips-source.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps([{k:v for k,v in r.items() if k!='source_pixels'}for r in rows]))
