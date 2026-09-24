"""Fit the local fireplace-side floor edge without moving the room datum."""
import json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'

def apply():
 import bpy,bmesh
 from mathutils import Vector
 native=json.loads((WORK/'baseline/nottingham.rhp.json').read_text())['sight_obstacles'][501]['points'];s,c=math.sin(math.radians(35)),math.cos(math.radians(35));a,b=native[5],native[6]
 def depth(x):return a['y']+(x-a['x'])*(b['y']-a['y'])/(b['x']-a['x'])
 anchors=[(370,0),(380,12),(448,12),(460,0)];perimeter=[(p['x'],p['y'])for p in native[:6]]+[(x,depth(x)+d)for x,d in anchors]+[(p['x'],p['y'])for p in native[6:]]
 # A shallow recessed hearth closes the local boundary below the source-measured
 # fireplace sill. Its depth is inferred; the remaining room stays at420.001.
 recess=[(x,depth(x))for x,d in anchors]+[(x,depth(x)+d)for x,d in reversed(anchors[1:-1])]
 rows=[]
 for component,bottom,top,rb,rt in [('castle-hall-floor',418,420.001,408,410),('castle-hall-floor-support',0,418,0,408)]:
  obj=next(o for o in bpy.data.collections['nottingham Working'].all_objects if o.get('source_node')=='building-501'and o.get('projection_component')==component)
  if obj.get('hall_hearth_boundary')=='local12-v1':raise ValueError('Boundary already fitted')
  vertices=[];faces=[];inverse=obj.matrix_world.inverted()
  for outline,lo,hi in [(perimeter,bottom,top),(recess,rb,rt)]:
   offset=len(vertices);n=len(outline)
   for z in [lo,hi]:vertices.extend(inverse@Vector((x,-y/s,z/c))for x,y in outline)
   faces.extend([tuple(reversed(range(offset,offset+n))),tuple(range(offset+n,offset+2*n))]);faces.extend((offset+i,offset+(i+1)%n,offset+(i+1)%n+n,offset+i+n)for i in range(n))
  mesh=bpy.data.meshes.new(obj.name+' hearth boundary')
  if component=='castle-hall-floor-support':
   boundary=2*len(perimeter);first=[face for face in faces if max(face)<boundary];second=[tuple(v-boundary for v in face)for face in faces if min(face)>=boundary]
   mesh.from_pydata(vertices[:boundary],[],first);mesh.update();old=obj.data;obj.data=mesh
   for mat in old.materials:mesh.materials.append(mat)
   other=bpy.data.meshes.new('Temporary hearth foundation complement');other.from_pydata(vertices[boundary:],[],second);other.update();operand=bpy.data.objects.new(other.name,other);bpy.context.scene.collection.objects.link(operand);operand.matrix_world=obj.matrix_world.copy();bpy.context.view_layer.objects.active=obj
   mod=obj.modifiers.new('Unify closed hearth foundation','BOOLEAN');mod.operation='UNION';mod.solver='EXACT';mod.object=operand;bpy.ops.object.modifier_apply(modifier=mod.name);mesh=obj.data;bpy.data.objects.remove(operand,do_unlink=True)
  else:
   mesh.from_pydata(vertices,[],faces);mesh.update()
  bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges);deg=sum(f.calc_area()<1e-8 for f in bm.faces);assert bad==deg==0,(component,bad,deg);bm.to_mesh(mesh);bm.free()
  if mesh!=obj.data:
   for mat in obj.data.materials:mesh.materials.append(mat)
  for name in ([u.name for u in obj.data.uv_layers] or ['Source projection']):
   uv=mesh.uv_layers.new(name=name)
   for loop in mesh.loops:
    v=obj.matrix_world@mesh.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(v.x/2304,1-(-v.y*s-v.z*c)/3520)
  obj.data=mesh;obj['hall_hearth_boundary']='local12-v1';rows.append(dict(object=obj.name,vertices=len(mesh.vertices),faces=len(mesh.polygons),nonmanifold_edges=bad,degenerate_faces=deg))
 return dict(status='PROTOTYPE',changed=rows,native_floor_datum=420.001,local_native_depth_shift=12,anchors=anchors,recess_native_top=410,recess_inference='Local hearth closure lies below measured fireplace aperture bottom415; exact hidden depth is inferred.',source_probes=[[390,664],[400,660],[420,652],[440,645]])

if __name__=='__main__':
 import sys
 sys.path.insert(0,str(Path(__file__).parent))
 from render_slots import acquire
 from freeze_tooling import select_tooling
 acquire();select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy
 source=WORK/'round-40/assets/nottingham-castle-main-hall/model.blend';out=WORK/'castle-audit/v15-floor-independent/hearth-prototype';out.mkdir(exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(source));report=apply();bpy.context.view_layer.update();bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));report.update(source_model_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),model_sha256=hashlib.sha256((out/'model.blend').read_bytes()).hexdigest());(out/'geometry.json').write_text(json.dumps(report,indent=2)+'\n');print('HEARTH_PROTOTYPE',report,flush=True)
