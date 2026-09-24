"""Independently ray-check every marked known review pixel against source RGB."""
import bpy,sys,json,math,hashlib
from pathlib import Path
from mathutils import Matrix,Vector
from PIL import Image
import numpy as np
root=Path(__file__).resolve().parents[3]/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
# This opt-in audit performs only CPU ray intersections and image reads.
if '--no-render-lease' not in sys.argv:
 acquire()
from freeze_tooling import select_tooling
select_tooling(root/'tooling/94116d984f92dbae')
from refinement_review import _tree
w=Path(sys.argv[sys.argv.index('--')+1]).resolve()
bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'))
config=json.loads((w/'workspace.json').read_text());scene=bpy.data.scenes[config['scene_name']];bpy.context.window.scene=scene
packets=[w/'modified']
cache={};reports=[]
for packet in packets:
 data=json.loads((packet/'views.json').read_text());names=data.get('render_object_names') or data['object_names'];objects=[bpy.data.objects[name] for name in names];tree,owners,_=_tree(objects)
 sources={str(Path(d['source_path']).resolve()) for d in data['projection_layers']}
 for d in data['projection_layers']:
  if d.get('projection_region'):
   sources.add(str(Path(config['source_path']).resolve()))
 for p in sources:
  if p not in cache:cache[p]=np.array(Image.open(p).convert('RGB'))
 width,height=data['tile_size'];scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.resolution_percentage=100;scene.render.pixel_aspect_x=scene.render.pixel_aspect_y=1
 camera=bpy.data.cameras.new('verification-camera');camera.type='ORTHO';known_total=0;mismatch=0;missing=0
 for v in data['views']:
  camera.ortho_scale=v['ortho_scale'];frame=camera.view_frame(scene=scene);left,right=min(p.x for p in frame),max(p.x for p in frame);bottom,top=min(p.y for p in frame),max(p.y for p in frame)
  matrix=Matrix(v['camera_matrix_world']);direction=matrix.to_3x3()@Vector((0,0,-1));i=v['index'];known=np.array(Image.open(packet/'views'/f'view-{i}-known.png'))[:,:,0]>127;actual=np.array(Image.open(packet/'views'/f'view-{i}-textured.png').convert('RGB'))
  for y,x in zip(*np.where(known)):
   origin=matrix@Vector((left+(int(x)+.5)*(right-left)/width,bottom+(height-int(y)-.5)*(top-bottom)/height,0));hit,normal,index,distance=tree.ray_cast(origin,direction);known_total+=1
   if hit is None:missing+=1;continue
   sx=int(math.floor(hit.x));sy=int(math.floor(hit.dot(Vector((0,-math.sin(math.radians(data['elevation_degrees'])),-math.cos(math.radians(data['elevation_degrees'])))))))
   if not any(0<=sy<im.shape[0] and 0<=sx<im.shape[1] and np.array_equal(actual[y,x],im[sy,sx]) for p in sources for im in [cache[p]]):
    mismatch+=1
    print('MISMATCH',v['index'],int(x),int(y),list(hit),sx,sy,actual[y,x].tolist(),[(p,cache[p][sy,sx].tolist()) for p in sources],flush=True)
 bpy.data.cameras.remove(camera)
 reports.append({'packet':str(packet),'known_pixels':known_total,'source_rgb_mismatches':mismatch,'missing_geometry_hits':missing,'views_sha256':hashlib.sha256((packet/'views.json').read_bytes()).hexdigest()})
 print(reports[-1],flush=True)
 if mismatch or missing:raise ValueError('Known pixel source preservation failed')
(w/'known-rgb-validation.json').write_text(json.dumps({'status':'PASS','method':'Independent fixed-camera ray intersection and exact RGB comparison at the projected source pixel, across declared projection sources.','packets':reports},indent=2)+'\n')
