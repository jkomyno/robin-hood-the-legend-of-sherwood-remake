"""Measured window/door recesses and ten visible chandelier candles."""
import math,json
from pathlib import Path

def refine(workspace):
 import bpy,bmesh
 from mathutils import Vector
 from refine_castle_secondary import replace_mesh
 R=Path(__file__).resolve().parents[2]/'work/nottingham-refinement';native=json.loads((R/'baseline/nottingham.rhp.json').read_text())['sight_obstacles']
 objects=list(bpy.data.collections['nottingham Working'].all_objects)
 wall=next(o for o in objects if o.get('asset_group')=='nottingham-castle-main-hall' and o.get('source_node')=='building-504' and not o.get('castle_hall_generated'))
 s,c=math.sin(math.radians(35)),math.cos(math.radians(35))
 def world(x,y,z):return Vector((x,-y/s,z/c))
 rows=[]
 if wall.get('hall_windows_recipe')!='window-door-recess-v1':
  outlines=[('western pointed window',[(519,606),(519,547),(522,536),(529,530),(537,535),(542,548),(542,616)]),('eastern narrow window',[(550,621),(550,557),(555,551),(562,557),(564,566),(564,630)]),('closed eastern door',[(628,726),(628,659),(631,651),(637,649),(644,654),(648,662),(648,745)])]
  for name,outline in outlines:
   verts=[]
   for depth in [2,-3]:
    for x,source_y in outline:
     # Measured inner wall segments meet at source node504 point4.
     a,b=(native[504]['points'][5],native[504]['points'][4]) if x<534.20984 else (native[504]['points'][4],native[504]['points'][3])
     y=a['y']+(x-a['x'])*(b['y']-a['y'])/(b['x']-a['x'])+depth
     verts.append(world(x,y,y-source_y))
   n=len(outline);faces=[tuple(range(n)),tuple(reversed(range(n,2*n)))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
   mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);cut=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(cut);replace_mesh(cut,verts,faces)
   bpy.context.view_layer.objects.active=wall;mod=wall.modifiers.new(name,'BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cut;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cut,do_unlink=True)
   rows.append({'change':name,'source_outline':outline,'inferred_native_depth':3})
  wall['hall_windows_recipe']='window-door-recess-v1'
 chandelier=next(o for o in objects if o.get('projection_component')=='castle-hall-chandelier')
 if chandelier.get('hall_candles_recipe')!='ten-measured-candles-v1':
  verts=[chandelier.matrix_world@v.co for v in chandelier.data.vertices];faces=[tuple(p.vertices) for p in chandelier.data.polygons]
  measurements=[(477.7,565,False),(481.4,557,True),(491.3,553,True),(508.5,552,True),(520.4,557,True),(526.2,564,False),(522.9,572,False),(512.1,576,False),(497.7,577,False),(484.1,573,False)]
  def cylinder(x,y,low,high,rx,ry):
   offset=len(verts);n=10
   for z in [low,high]:verts.extend(world(x+rx*math.cos(i*math.tau/n),y+ry*math.sin(i*math.tau/n),z) for i in range(n))
   faces.extend([tuple(reversed(range(offset,offset+n))),tuple(range(offset+n,offset+2*n))]);faces.extend((offset+i,offset+(i+1)%n,offset+(i+1)%n+n,offset+i+n) for i in range(n))
  for x,source_base,back in measurements:
   y=1124+(-1 if back else 1)*12*math.sqrt(max(0,1-((x-503)/28)**2));z=y-source_base
   if z>552:cylinder(x,y,552,z,.5,.3)
   cylinder(x,y,z,z+7.5,.72,.46)
  inv=chandelier.matrix_world.inverted();replace_mesh(chandelier,[inv@v for v in verts],faces);chandelier['hall_candles_recipe']='ten-measured-candles-v1'
  rows.append({'change':'Ten independently measured candle stems and support rods','count':10,'source_bases':measurements,'evidence':'castle-audit/hall-candles-measure.png','inference':'Depth lies on the measured ring ellipse; candle back faces and support elevations are inferred.'})
 for obj in [wall,chandelier]:
  bm=bmesh.new();bm.from_mesh(obj.data);bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-8 for f in bm.faces);bm.free();assert bad==deg==0,(obj.name,bad,deg)
 if rows:(Path(workspace)/'hall-fine-details.json').write_text(json.dumps({'changes':rows,'source_evidence':'castle-audit/hall-window-measure.png','topology':'closed, manifold and nondegenerate'},indent=2)+'\n')
 return rows
