"""Fit full near/far notch boundaries while preserving the complete lower wall."""
import sys,json,math,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root.parents[4]/'blender'))
import bpy,bmesh
from mathutils import Vector
from derby_asset_lower_west_curtain import _wall
out=root/'inspection/north-corner-v10';out.mkdir(parents=True,exist_ok=True)
working=bpy.data.collections['Derby Working']
old=next(o for o in working.objects if o.type=='MESH' and o.get('source_node')=='building-025' and not o.hide_render)
source=next(o for o in working.objects if o.type=='MESH' and o.get('source_node')=='building-025' and o.hide_render and 'modeled battlements' not in o.name)
points=[source.matrix_world@v.co for v in source.data.vertices]
sn,cs=math.sin(math.radians(35)),math.cos(math.radians(35))
# Each pair is one gap. At each boundary: visible near top, far top, near floor.
# Coordinates are independently read in the original1920x2752 source image.
runs=[{'name':'front','edge':[27,26],'nearline':[26,27],'near_is_edge':True,
 'corners':[
 [[334,1563],[340,1560],[334,1583]],[[341,1572],[346,1569],[341,1592]],
 [[347,1581],[354,1578],[347,1604]],[[354,1593],[360,1590],[354,1613]],
 [[361,1607],[368,1604],[361,1626]],[[368,1618],[375,1614],[368,1637]],
 [[376,1629],[383,1626],[376,1649]],[[383,1640],[389,1638],[383,1660]]]},
 {'name':'return','edge':[28,27],'nearline':[32,24],'near_is_edge':False,
 'corners':[
 [[341,1738],[338,1736],[341,1758]],[[345,1730],[341,1728],[345,1750]],
 [[352,1720],[349,1718],[352,1740]],[[359,1711],[354,1708],[359,1731]],
 [[367,1699],[363,1697],[367,1719]],[[372,1692],[367,1690],[372,1712]],
 [[375,1685],[372,1682],[375,1705]],[[380,1677],[376,1675],[380,1697]],
 [[387,1666],[383,1664],[387,1686]],[[392,1658],[388,1656],[392,1678]]]}]
for run in runs:
 # Parallel near/far wall planes with one flat crown. Fit the authored pixel
 # endpoints within their sampling uncertainty, not every noisy pixel exactly.
 groups=[[c[j] for c in run['corners']] for j in (0,1)]
 means=[(sum(x for x,y in g)/len(g),sum(y for x,y in g)/len(g)) for g in groups]
 slope=sum((x-mx)*(y-my) for g,(mx,my) in zip(groups,means) for x,y in g)/sum((x-mx)**2 for g,(mx,my) in zip(groups,means) for x,y in g)
 run['fit']={'slope':slope,'intercepts':[my-slope*mx for mx,my in means],'crown_z':224.5,'notch_pixels':20}
cuts=[]
for run in runs:
 axis=0 if run['near_is_edge'] else 1
 xs=[c[axis][0] for c in run['corners']]
 cuts.append((*run['edge'],0,tuple(zip(xs[::2],xs[1::2]))))
temp=source.copy();temp.data=source.data.copy();working.objects.link(temp)
inverse=temp.matrix_world.inverted();top=max(p.z for p in points)
for v,p in zip(temp.data.vertices,points):
 if p.z>top-.1:v.co=inverse@(p-Vector((0,0,7.545129505568542)))
result=_wall(temp,cuts,notch_depth=23.5)
new=bpy.data.objects[result['object']];oldtop=max(v.co.z for v in new.data.vertices)
# Insert a fixed ledge below the openings so fitting cap thickness cannot warp
# an entire lower masonry wall into long, differently shaded triangles.
bm=bmesh.new();bm.from_mesh(new.data)
bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.00001,plane_co=(0,0,190),plane_no=(0,0,1),clear_inner=False,clear_outer=False)
bm.to_mesh(new.data);bm.free()
original_vertices={v.index:v.co.copy() for v in new.data.vertices}
fitted=[]
for run in runs:
 a,b=[points[i] for i in run['edge']];direction=b-a;direction.z=0;direction.normalize()
 near_a,near_b=[points[i] for i in run['nearline']]
 for near,far,floor in run['corners']:
  slope=run['fit']['slope'];bn,bf=run['fit']['intercepts'];crown_z=run['fit']['crown_z']
  crown_y=(-(slope*near[0]+bn)-crown_z*cs)/sn
  desired_near=Vector((near[0],crown_y,crown_z))
  desired_far=Vector((far[0],(-(slope*far[0]+bf)-crown_z*cs)/sn,crown_z))
  floor_z=crown_z-run['fit']['notch_pixels']/cs
  source_x=near[0] if run['near_is_edge'] else far[0]
  on_edge=a.lerp(b,(source_x-a.x)/(b.x-a.x));cut_distance=(on_edge-a).dot(direction)
  # Locate the actual intersections of the Boolean cutter with both wall faces.
  matches=[v for v in new.data.vertices if original_vertices[v.index].z>190.1 and abs((original_vertices[v.index]-a).dot(direction)-cut_distance)<.003]
  assert len(matches)>=4,(run['name'],near,len(matches))
  candidates=[original_vertices[v.index] for v in matches if abs(original_vertices[v.index].z-oldtop)<.01]
  candidates=sorted(candidates,key=lambda p:(p-on_edge).length)
  edge_point=candidates[0];opposite=max(candidates,key=lambda p:(p-edge_point).length)
  near_point,far_point=(edge_point,opposite) if run['near_is_edge'] else (opposite,edge_point)
  span=far_point-near_point
  for v in matches:
   ratio=max(0,min(1,(original_vertices[v.index]-near_point).dot(span)/span.length_squared))
   is_floor=original_vertices[v.index].z<oldtop-.1
   target=desired_near.lerp(desired_far,ratio)
   if is_floor:target.z=floor_z
   v.co=target
  fitted.append({'run':run['name'],'near_top':near,'far_top':far,'near_floor':floor,
                 'near_world':list(desired_near),'far_world':list(desired_far),'floor_z':floor_z,'vertices':len(matches)})
# Join the two fitted near/far planes at their true common corners. This also
# avoids fitting one arm's height to the opposite face of the other arm.
front,ret=runs
def intersect(first,second):
 m,b=first;n,c=second;x=(c-b)/(m-n);y=m*x+b
 return Vector((x,(-y-224.5*cs)/sn,224.5))
outer=intersect((front['fit']['slope'],front['fit']['intercepts'][0]),(ret['fit']['slope'],ret['fit']['intercepts'][1]))
inner=intersect((front['fit']['slope'],front['fit']['intercepts'][1]),(ret['fit']['slope'],ret['fit']['intercepts'][0]))
for v in new.data.vertices:
 p=original_vertices[v.index]
 if abs(p.z-oldtop)>.01:continue
 for index,target in [(27,outer),(24,inner)]:
  q=points[index]
  if abs(p.x-q.x)<.01 and abs(p.y-q.y)<.01:v.co=target
bm=bmesh.new();bm.from_mesh(new.data)
bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
result.update(nonmanifold=sum(not e.is_manifold for e in bm.edges),volume=bm.calc_volume(signed=True),degenerate=sum(f.calc_area()<1e-7 for f in bm.faces))
assert result['nonmanifold']==0 and result['volume']>0 and result['degenerate']==0
bm.to_mesh(new.data);bm.free()
name=old.name;bpy.data.objects.remove(old,do_unlink=True);bpy.data.objects.remove(temp,do_unlink=True);new.name=name
(out/'geometry.json').write_text(json.dumps(result,indent=2)+'\n')
(out/'source-correspondences.json').write_text(json.dumps({'uncertainty_pixels':2,'runs':runs,'fitted':fitted},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
