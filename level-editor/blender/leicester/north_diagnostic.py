"""Inspect source-camera first-hit ownership for keep patch states."""
import sys,json,math,collections
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from asset_reference_views import state_objects
from PIL import Image
w=Path(bpy.data.filepath).parent
manifest=json.loads((w/'projection-layers.json').read_text())
objects=list(bpy.data.collections['Leicester Working'].all_objects)
si,co=math.sin(math.radians(35)),math.cos(math.radians(35))
for patch in ['patch-005','patch-006']:
 record=next(p for p in manifest['patches'] if p['id']==patch)
 alpha=Image.open(record['graphic']['alpha']).convert('L');ox,oy,_,_=record['graphic']['bbox']
 for state in ['covered','revealed']:
  selected=state_objects(objects,'leicester-great-keep',patch,manifest['projection_reviews'][patch]['render_visibility'],state)
  trees=[]
  for o in selected:
   o.data.calc_loop_triangles()
   trees.append((o,BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[list(p.vertices) for p in o.data.loop_triangles],all_triangles=True)))
  hits=collections.Counter();zs=collections.defaultdict(list)
  for yy in range(0,alpha.height,8):
   for xx in range(0,alpha.width,8):
    if alpha.getpixel((xx,yy))<128:continue
    start=Vector((ox+xx,-(oy+yy)/si-3000*co,3000*si));direction=Vector((0,co,-si))
    found=[]
    for o,tree in trees:
     location,normal,index,distance=tree.ray_cast(start,direction)
     if location is not None:found.append((distance,o.name,location.z))
    if found:
     _,name,z=min(found);hits[name]+=1;zs[name].append(z)
  print(patch,state,[(n,c,round(min(zs[n]),2),round(max(zs[n]),2)) for n,c in hits.most_common()],flush=True)
