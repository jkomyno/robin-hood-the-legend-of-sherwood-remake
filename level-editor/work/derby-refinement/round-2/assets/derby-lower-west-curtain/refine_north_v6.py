"""North-only correction: trace gaps, not the neighboring bright merlon caps."""
import sys,json,math,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root.parents[4]/'blender'))
import bpy,bmesh
from derby_asset_lower_west_curtain import _wall
out=root/'inspection/north-corner-v6';out.mkdir(parents=True,exist_ok=True)
working=bpy.data.collections['Derby Working']
old=next(o for o in working.objects if o.type=='MESH' and o.get('source_node')=='building-025' and not o.hide_render)
source=next(o for o in working.objects if o.type=='MESH' and o.get('source_node')=='building-025' and o.hide_render and 'modeled battlements' not in o.name)
def digest(o):
 return hashlib.sha256(repr(([tuple(o.matrix_world@v.co) for v in o.data.vertices],[tuple(p.vertices) for p in o.data.polygons])).encode()).hexdigest()
protected={o.name:digest(o) for o in working.objects if o.type=='MESH' and o!=old}
temp=source.copy();temp.data=source.data.copy();working.objects.link(temp)
inverse=temp.matrix_world.inverted();pts=[temp.matrix_world@v.co for v in temp.data.vertices];top=max(p.z for p in pts)
for v,p in zip(temp.data.vertices,pts):
 if p.z>top-.1:p.z-=7.545129505568542;v.co=inverse@p
cuts=[(28,27,0,((338,341),(349,354),(363,367),(372,376))),
      (27,26,0,((334,340),(348,354),(362,368),(376,382)))]
result=_wall(temp,cuts,notch_depth=23.5)
new=bpy.data.objects[result['object']]
# Return crown is about two source pixels too low; blend the correction into
# the front run at the shared bend. Body footprint and ground stay identical.
a=pts[28];b=pts[27];d=b-a;d.z=0
for v in new.data.vertices:
 p=v.co
 t=max(0,min(1,((p-a).dot(d))/d.length_squared))
 cross=d.x*(p.y-a.y)-d.y*(p.x-a.x)
 if p.y < b.y-3 and abs(cross)/d.length<20:
  strength=min(1,(b.y-p.y)/30)
  # Bright cap edges in the return are roughly five source pixels wide,
  # whereas the inherited footprint extrudes an eight-to-ten pixel cap.
  # Retain the lower footprint and taper only the upper receiver vertices.
  upper=max(0,min(1,(p.z-185)/15))
  inward=-cross/d.length
  if inward>0:
   p.x-=d.y/d.length*inward*.4*strength*upper
   p.y+=d.x/d.length*inward*.4*strength*upper
  p.z+=2.5*strength*max(0,min(1,(p.z-185)/15))
bm=bmesh.new();bm.from_mesh(new.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
result.update(nonmanifold=sum(not e.is_manifold for e in bm.edges),volume=bm.calc_volume(signed=True),degenerate=sum(f.calc_area()<1e-7 for f in bm.faces))
assert result['nonmanifold']==0 and result['volume']>0 and result['degenerate']==0
bm.to_mesh(new.data);bm.free()
name=old.name;bpy.data.objects.remove(old,do_unlink=True);bpy.data.objects.remove(temp,do_unlink=True);new.name=name
assert all(digest(bpy.data.objects[name])==value for name,value in protected.items())
result.update(protected_mesh_count=len(protected),cuts=cuts,return_raise=2.5,return_crown_width_factor=.6,source_uncertainty_px=2)
(out/'geometry.json').write_text(json.dumps(result,indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
