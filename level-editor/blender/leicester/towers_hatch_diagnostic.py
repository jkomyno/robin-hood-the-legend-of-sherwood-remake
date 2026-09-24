import bpy,math,json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
angle=math.radians(35);toward=Vector((0,-math.cos(angle),math.sin(angle)));objects=[]
for o in bpy.data.objects:
 if o.type!='MESH' or o.get('asset_group')!='leicester-northwest-tower' or o.get('projection_component')=='tower-cover':continue
 verts=[o.matrix_world@v.co for v in o.data.vertices];o.data.calc_loop_triangles();tree=BVHTree.FromPolygons(verts,[tuple(f.vertices) for f in o.data.loop_triangles],all_triangles=True);objects.append((o,tree))
for x,y in [(802,240),(795,251),(789,262),(804,233)]:
 origin=Vector((x,-y/math.sin(angle),0))+toward*10000;hits=[]
 for o,t in objects:
  hit,normal,index,distance=t.ray_cast(origin,-toward)
  if hit is not None:hits.append((round(distance,3),o['source_node'],o.get('projection_component'),list(hit)))
 print('RAY',x,y,sorted(hits)[:5],flush=True)
