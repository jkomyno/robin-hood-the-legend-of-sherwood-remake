import bpy,json,math
from pathlib import Path
W=Path(__file__).resolve().parent
rows=[]
for o in bpy.data.objects:
 if o.type=='MESH' and o.get('source_node') in ['building-153','building-158','building-160','building-161','building-162']:
  vs=[o.matrix_world@v.co for v in o.data.vertices]
  rows.append(dict(node=o.get('source_node'),name=o.name,hidden=o.hide_render,vertices=[list(v) for v in vs],projected=[[v.x,-v.y*math.sin(math.radians(35))-v.z*math.cos(math.radians(35))] for v in vs],faces=[list(f.vertices) for f in o.data.polygons],normals=[list((o.matrix_world.to_3x3()@f.normal).normalized()) for f in o.data.polygons]))
target=Path(bpy.data.filepath).parent/'mesh-inspection-v2.json'
target.write_text(json.dumps(rows,indent=2))
