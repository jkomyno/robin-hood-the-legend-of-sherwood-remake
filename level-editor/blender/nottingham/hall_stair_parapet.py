"""Add the source-traced foreground parapet missing beside the interior stairs."""
import math

def apply():
 import bpy,bmesh
 from mathutils import Vector
 node='building-500';component='castle-hall-stair-parapet'
 assert not any(o.get('source_node')==node and o.get('projection_component')==component for o in bpy.data.objects)
 base=next(o for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH'and o.get('source_node')==node and not o.get('projection_component')and not o.hide_render)
 cap=[(389,723),(399,719),(466,780),(471,791),(461,794),(458,784)];top=480.;bottom=420.;s,c=math.sin(math.radians(35)),math.cos(math.radians(35));inverse=base.matrix_world.inverted();vertices=[inverse@Vector((x,-(y+top)/s,z/c))for z in [bottom,top]for x,y in cap];n=len(cap);faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n)for i in range(n)]
 mesh=bpy.data.meshes.new(node+' '+component);mesh.from_pydata(vertices,[],faces);mesh.update();bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));assert all(e.is_manifold for e in bm.edges);assert all(f.calc_area()>1e-8 for f in bm.faces);bm.to_mesh(mesh);bm.free()
 obj=bpy.data.objects.new(node+'__'+component,mesh);bpy.data.collections['nottingham Working'].objects.link(obj);obj.parent=base.parent;obj.matrix_world=base.matrix_world.copy()
 for key in ['source_node','asset_group','asset_group_name','source_obstacle']:
  if key in base:obj[key]=base[key]
 obj['projection_component']=component;obj['hall_parapet_source_review']='Cap traced at source pixels389723/399719/466780/471791/461794/458784. Top480 follows upperlanding; base420 follows roomfloor. Hidden lower closure inferred.'
 for mat in base.data.materials:mesh.materials.append(mat)
 uv=mesh.uv_layers.new(name='Source projection')
 for loop in mesh.loops:
  v=obj.matrix_world@mesh.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(v.x/2304,1-(-v.y*s-v.z*c)/3520)
 return {'object':obj.name,'source_cap':cap,'native_top':top,'native_bottom':bottom,'closed':True,'vertices':len(mesh.vertices),'faces':len(mesh.polygons)}
