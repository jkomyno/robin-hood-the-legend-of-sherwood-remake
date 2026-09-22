"""Find colored atlas texels on triangles facing away from the source camera."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector
from array import array
direction=Vector((0,-math.cos(math.radians(35)),math.sin(math.radians(35))))
cache={};rows=[]
for o in bpy.data.collections['Leicester Working'].all_objects:
 if o.type!='MESH' or o.hide_render or o.get('asset_group')!='leicester-great-keep':continue
 o.data.calc_loop_triangles()
 for t in o.data.loop_triangles:
  f=o.data.polygons[t.polygon_index];n=(o.matrix_world.to_3x3().inverted().transposed()@f.normal).normalized()
  if n.dot(direction)>.05:continue
  m=o.data.materials[f.material_index]
  if not m or not m.use_nodes:continue
  tex=next((x for x in m.node_tree.nodes if x.type=='TEX_IMAGE'),None);uv=next((x for x in m.node_tree.nodes if x.type=='UVMAP'),None)
  if not tex or not uv:continue
  img=tex.image
  if img.name not in cache:
   pixels=array('f',[0])*len(img.pixels);img.pixels.foreach_get(pixels);cache[img.name]=pixels
  layer=o.data.uv_layers[uv.uv_map];p=sum((layer.data[i].uv for i in t.loops),Vector((0,0)))/3
  x=min(img.size[0]-1,max(0,int(p.x*img.size[0])));y=min(img.size[1]-1,max(0,int(p.y*img.size[1])));ix=(y*img.size[0]+x)*4;rgb=cache[img.name][ix:ix+3]
  if max(rgb)-min(rgb)>.02:rows.append(dict(object=o.name,face=f.index,dot=n.dot(direction),rgb=list(rgb),uv=list(p)))
w=Path(bpy.data.filepath).parent;(w/'inspection/backface-atlas-probe.json').write_text(json.dumps(rows,indent=2)+'\n');print('COLORED BACKFACE TRIANGLES',len(rows));print(rows[:10])
