"""Extend the retained roof's source-visible metal edge without moving its shingles."""
import math

def apply():
 import bpy,bmesh
 from mathutils import Vector
 o=next(o for o in bpy.data.collections['nottingham Working'].all_objects if o.get('source_node')=='building-505' and o.get('projection_component')=='castle-hall-retained-roof')
 assert not o.get('hall_metal_rim_extended')
 s,c=math.sin(math.radians(35)),math.cos(math.radians(35));bm=bmesh.new();bm.from_mesh(o.data);bm.faces.ensure_lookup_table()
 # The narrow outer end face spans the source-measured eave-to-ridge edge.
 candidates=[f for f in bm.faces if len(f.verts)==4 and all(1113 < -(o.matrix_world@v.co).y*s <1117 for v in f.verts)]
 assert len(candidates)==1,[(f.index,len(f.verts)) for f in candidates]
 face=candidates[0];before=[list(o.matrix_world@v.co) for v in face.verts];result=bmesh.ops.extrude_face_region(bm,geom=[face]);new=[v for v in result['geom'] if isinstance(v,bmesh.types.BMVert)];delta=o.matrix_world.to_3x3().inverted()@Vector((0,8/s,0));bmesh.ops.translate(bm,verts=new,vec=delta);bmesh.ops.delete(bm,geom=[face],context='FACES_ONLY');bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-8 for f in bm.faces);assert bad==deg==0,(bad,deg);bm.to_mesh(o.data);bm.free();o.data.update()
 for layer in o.data.uv_layers:
  for loop in o.data.loops:
   v=o.matrix_world@o.data.vertices[loop.vertex_index].co;layer.data[loop.index].uv=(v.x/2304,1-(-v.y*s-v.z*c)/3520)
 o['hall_metal_rim_extended']='native-y-minus8';return dict(object=o.name,native_y_extension=-8,native_z_unchanged=True,original_edge_world=before,new_vertices=len(new),nonmanifold_edges=bad,degenerate_faces=deg)
