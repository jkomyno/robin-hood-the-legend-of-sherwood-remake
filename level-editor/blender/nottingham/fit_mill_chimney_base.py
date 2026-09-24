"""Restore the mill chimney's source-visible flared masonry foot."""
import math,json
from pathlib import Path
import bpy
from mathutils import Vector
from refine_village_secondary import replace,native

def apply():
 s=math.sin(math.radians(35));c=math.cos(math.radians(35));o=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')=='nottingham-village-mill' and o.get('source_node')=='building-241' and not o.hide_render)
 shaft=native(241)
 # Source-ground contacts determine the flared footprint at local datum eight.
 outer=[(1718,2731),(1723,2755),(1695,2756),(1677,2734)]
 verts=[Vector((x,-y/s,z/c)) for z in [8,14] for x,y in outer]
 verts.extend(Vector((p['x'],-p['y']/s,z/c)) for z in [40,123.88901] for p in shaft)
 faces=[(3,2,1,0),(12,13,14,15)]
 for k in [0,4,8]:
  for i in range(4):j=(i+1)%4;faces.append((k+i,k+j,k+4+j,k+4+i))
 report=replace(o,verts,faces,'Mill chimney / source-traced flared masonry base')
 report.update(source_ground_contacts=[[x,y-8]for x,y in outer],local_ground_native=8,unchanged_shaft_above_native=40,inference='The concealed foot and local ground datum are inferred from the painted contact; the source-visible flare follows native155 masonry and does not borrow hay pixels.')
 return report
