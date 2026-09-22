"""Build complete vertical wall planes; no incompatible lower-footprint ledge."""
import sys,json,math,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root.parents[4]/'blender'))
import bpy,bmesh
from mathutils import Vector
out=root/'inspection/north-corner-v14';out.mkdir(parents=True,exist_ok=True)
data={'runs':[{'name':'front'},{'name':'return'}]}
data['runs'][0]['corners']=[
 [[334,1563],[340,1560],[334,1583]],[[341,1572],[346,1569],[341,1592]],
 [[347,1581],[354,1578],[347,1601]],[[354,1589],[359,1587],[354,1609]],
 [[361,1598],[366,1595],[361,1618]],[[366,1607],[372,1604],[366,1627]],
 [[373,1617],[379,1614],[373,1637]],[[379,1625],[385,1622],[379,1645]],
 [[386,1635],[392,1632],[386,1655]],[[391,1647],[397,1644],[391,1667]]]
# Re-picked with external pixel axes on individual, unmodified source crops.
# The former opening3 annotations were offset into the masonry beside the cap.
data['runs'][1]['corners']=[
 [[340,1738],[337,1736],[340,1759]],[[345,1730],[341,1728],[345,1751]],
 [[353,1720],[348,1717],[353,1742]],[[358,1709],[354,1706],[358,1732]],
 [[364,1702],[361,1699],[364,1725]],[[370,1692],[366,1690],[370,1716]],
 [[375,1684],[371,1681],[375,1705]],[[379,1676],[375,1674],[379,1697]],
 [[386,1666],[382,1663],[386,1687]],[[391,1658],[386,1655],[391,1679]]]
for run in data['runs']:
 groups=[[c[j] for c in run['corners']] for j in (0,1)]
 means=[(sum(x for x,y in g)/len(g),sum(y for x,y in g)/len(g)) for g in groups]
 slope=sum((x-mx)*(y-my) for g,(mx,my) in zip(groups,means) for x,y in g)/sum((x-mx)**2 for g,(mx,my) in zip(groups,means) for x,y in g)
 run['fit']={'slope':slope,'intercepts':[my-slope*mx for mx,my in means]}
working=bpy.data.collections['Derby Working']
old=next(o for o in working.objects if o.type=='MESH' and o.get('source_node')=='building-025' and not o.hide_render)
def digest(o):return hashlib.sha256(repr(([tuple(o.matrix_world@v.co) for v in o.data.vertices],[tuple(p.vertices) for p in o.data.polygons])).encode()).hexdigest()
others={o.name:digest(o) for o in working.objects if o.type=='MESH' and o!=old}
sn,cs=math.sin(math.radians(35)),math.cos(math.radians(35));z0=224.5
def world(x,m,b,z):return Vector((x,(-(m*x+b)-z0*cs)/sn,z))
front,ret=data['runs'];mf=front['fit']['slope'];mn=ret['fit']['slope']
bf0,bf1=front['fit']['intercepts'];bn0,bn1=ret['fit']['intercepts']
def intersect(m,b,n,c):
 x=(c-b)/(m-n);return world(x,m,b,z0)
outer=intersect(mf,bf0,mn,bn1);inner=intersect(mf,bf1,mn,bn0)
vertices=[];faces=[];lookup={};records=[];all_profiles=[]
def vertex(p):
 key=tuple(round(v,5) for v in p)
 if key not in lookup:lookup[key]=len(vertices);vertices.append(tuple(p))
 return lookup[key]
def face(points):
 ids=[vertex(p) for p in points]
 if len(set(ids))>=3:faces.append(ids)
for run in data['runs']:
 m=run['fit']['slope'];bn,bf=run['fit']['intercepts'];name=run['name']
 if name=='front':
  start=(world(318.9380798339844,m,bn,z0),world(327.15234375,m,bf,z0));end=(outer,inner)
 else:
  start=(world(335.3738708496094,m,bn,z0),world(326.9123229980469,m,bf,z0));end=(inner,outer)
 profiles=[start]
 for index,(near,far,floor) in enumerate(run['corners']):
  pn=world(near[0],m,bn,z0+(m*near[0]+bn-near[1])/cs)
  pf=world(far[0],m,bf,z0+(m*far[0]+bf-far[1])/cs)
  actual_y=-pn.y*sn-pn.z*cs
  floor_z=pn.z+(actual_y-floor[1])/cs
  low_near=pn.copy();low_far=pf.copy();low_near.z=low_far.z=floor_z
  if index%2==0:profiles.extend([(pn,pf),(low_near,low_far)])
  else:profiles.extend([(low_near,low_far),(pn,pf)])
  records.append({'run':name,'boundary':index+1,'near_top':near,'far_top':far,'near_floor':floor,'near_vector':pn,'far_vector':pf,'floor_vector':low_near})
 profiles.append(end)
 all_profiles.append((name,profiles))

# Each merlon cap is one actual plane, independently fitted to its four observed
# corners. This permits authored slope without hidden diagonal triangulation folds.
from mathutils import Matrix
def cap_plane(points,observed=None):
 selected=observed or points;center=sum(selected,Vector())/len(selected)
 rows=[Vector((p.x-center.x,p.y-center.y,1)) for p in selected]
 matrix=Matrix([[sum(r[i]*r[j] for r in rows) for j in range(3)] for i in range(3)])
 rhs=Vector(tuple(sum(r[i]*(p.z-center.z) for r,p in zip(rows,selected)) for i in range(3)))
 coefficients=matrix.inverted()@rhs
 for p in points:p.z=center.z+coefficients.x*(p.x-center.x)+coefficients.y*(p.y-center.y)+coefficients.z
for name,profiles in all_profiles:
 # The terminal cap has only one visible cross-edge. Continue that edge's
 # cross-wall slope longitudinally, rather than invent a diagonal fan.
 cap_plane([*profiles[0],*profiles[1]],observed=[*profiles[1],Vector((profiles[0][0].x,profiles[0][0].y,profiles[1][0].z))])
 for index in range(4,len(profiles)-2,4):cap_plane([*profiles[index],*profiles[index+1]])
 for index in range(2,len(profiles)-2,4):
  near_a,far_a=profiles[index];near_b,far_b=profiles[index+1]
  tangent=near_b-near_a;tangent.z=0
  gradient=(near_b.z-near_a.z)/tangent.length_squared
  far_a.z=near_a.z+(far_a-near_a).dot(tangent)*gradient
  far_b.z=near_a.z+(far_b-near_a).dot(tangent)*gradient
corner_observed=[p for _,profiles in all_profiles for p in profiles[-2]]
cap_plane(corner_observed+[outer,inner],observed=corner_observed)

for name,profiles in all_profiles:
 start=profiles[0];end=profiles[-1]
 near_bottom_start=start[0].copy();near_bottom_start.z=0
 far_bottom_start=start[1].copy();far_bottom_start.z=0
 near_bottom_end=end[0].copy();near_bottom_end.z=0
 far_bottom_end=end[1].copy();far_bottom_end.z=0
 face([near_bottom_start,near_bottom_end]+[p[0] for p in reversed(profiles)])
 face([far_bottom_end,far_bottom_start]+[p[1] for p in profiles])
 for a,b in zip(profiles,profiles[1:]):face([a[0],b[0],b[1],a[1]])
 face([near_bottom_start,far_bottom_start,far_bottom_end,near_bottom_end])
 face([near_bottom_start,start[0],start[1],far_bottom_start])
mesh=bpy.data.meshes.new('North wall full vertical planes and source profiles')
mesh.from_pydata(vertices,[],faces);mesh.update()
bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
report={'source_node':'building-025','openings':10,'front_openings':5,'return_openings':5,'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces),'signed_volume':bm.calc_volume(signed=True),'outside_meshes_preserved':len(others),'footprint_changed':True,'explanation':'The entire wall uses the same vertical side planes as its cap profiles. This replaces the old footprint and removes the spurious z190 transition wedges.'}
assert report['nonmanifold_edges']==0 and report['degenerate_faces']==0 and report['signed_volume']>0
bm.to_mesh(mesh);bm.free()
# Projection immediately replaces these placeholder UV coordinates/materials.
mesh.uv_layers.new(name='UVMap')
for mat in old.data.materials:mesh.materials.append(mat)
mesh.attributes.new('reprojection_fallback_material','INT','FACE')
old_mesh=old.data;old.data=mesh
assert all(digest(bpy.data.objects[n])==h for n,h in others.items())
(out/'geometry.json').write_text(json.dumps(report,indent=2)+'\n')
for record in records:
 record['near_world']=list(record.pop('near_vector'));record['far_world']=list(record.pop('far_vector'));record['floor_z']=record.pop('floor_vector').z
(out/'source-correspondences.json').write_text(json.dumps({'runs':data['runs'],'fitted':records,'uncertainty_pixels':2},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
