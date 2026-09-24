"""Transfer the red frontage slice mistakenly included in the brown market base."""
import hashlib,json,math,shutil,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
from render_slots import acquire
from freeze_tooling import select_tooling
from partition_market import clip,geometry_signature
S=math.sin(math.radians(35))
A=(1629.8323974609375,1542.4478613309152)
B=(1743.5977783203125,1545.3294667770167)
N=(-(B[1]-A[1]),-(B[0]-A[0])*S,0)
D=-(B[1]-A[1])*A[0]+(B[0]-A[0])*A[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def signature(o):return geometry_signature(o)
def measure(o):
 bm=bmesh.new();bm.from_mesh(o.data)
 r=dict(vertices=len(bm.verts),faces=len(bm.faces),nonmanifold=sum(not e.is_manifold for e in bm.edges),degenerate=sum(f.calc_area()<1e-8 for f in bm.faces),volume=bm.calc_volume(signed=False))
 bm.free();return r

def clipped_mesh(obj,sign,name):
 points=[];faces=[];lookup={};obj.data.calc_loop_triangles()
 for tri in obj.data.loop_triangles:
  source=[tuple(obj.matrix_world@obj.data.vertices[i].co) for i in tri.vertices]
  # The existing brown facade lies on the cut plane but bounds the retained
  # half only; copying it to the thin transferred slice creates a dangling face.
  if sign>0 and max(abs(sum(v*n for v,n in zip(p,N))-D) for p in source)<.01:continue
  poly=clip(source,N,D,sign)
  face=[]
  for p in poly:
   key=tuple(round(x,6) for x in p)
   if key not in lookup:lookup[key]=len(points);points.append(obj.matrix_world.inverted()@Vector(p))
   vi=lookup[key]
   if not face or face[-1]!=vi:face.append(vi)
  if len(set(face))>=3:faces.append(face)
 mesh=bpy.data.meshes.new(name);mesh.from_pydata(points,[],faces);mesh.update()
 bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-5)
 bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-6)
 boundary=[e for e in bm.edges if e.is_boundary]
 if boundary:bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
 bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.uv_layers.new(name='Source projection')
 for m in obj.data.materials:mesh.materials.append(m)
 return mesh

def transfer():
 meshes=list(bpy.data.collections['nottingham Working'].all_objects)
 brown=next(o for o in meshes if o.get('projection_component')=='market-base-012-front-2')
 red=next(o for o in meshes if o.get('projection_component')=='market-base-012-front-3')
 outside={o.name:signature(o) for o in bpy.data.objects if o.type=='MESH' and o not in (brown,red)}
 original_brown=measure(brown);original_red=measure(red)
 piece=bpy.data.objects.new('Temporary transferred red frontage',clipped_mesh(brown,1,'Transferred red frontage'))
 bpy.data.collections['nottingham Working'].objects.link(piece);piece.matrix_world=brown.matrix_world.copy();piece_measure=measure(piece)
 brown.data=clipped_mesh(brown,-1,'Brown base with correct frontage')
 # Remove the shared partition cap explicitly. Boolean unions of exactly
 # touching, triangulated caps can leave open seams; here exterior faces stay
 # untouched and only the existing internal separator is shortened.
 seam_a=Vector((1741.1165771484375,-1481.753924093256/S,0))
 seam_b=Vector((1743.5977783203125,-1545.3294667770167/S,0))
 tangent=seam_b-seam_a;seam_normal=Vector((-tangent.y,tangent.x,0)).normalized()
 def on_seam(poly):return max(abs((Vector(v)-seam_a).dot(seam_normal)) for v in poly)<.002
 points=[];faces=[];lookup={};inv=red.matrix_world.inverted()
 for obj in (red,piece):
  for face in obj.data.polygons:
   poly=[tuple(obj.matrix_world@obj.data.vertices[i].co) for i in face.vertices]
   if on_seam(poly):
    if obj==piece:continue
    poly=clip(poly,N,D,-1)
   ids=[]
   for point in poly:
    key=tuple(round(v,5) for v in point)
    if key not in lookup:lookup[key]=len(points);points.append(inv@Vector(point))
    vi=lookup[key]
    if not ids or ids[-1]!=vi:ids.append(vi)
   if len(set(ids))>=3:faces.append(ids)
 mesh=bpy.data.meshes.new('Red base with recovered frontage');mesh.from_pydata(points,[],faces);mesh.update()
 bm=bmesh.new();bm.from_mesh(mesh)
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.001)
 # Match pre-existing triangular edge subdivisions along the shared cut.
 for vertex in list(bm.verts):
  for edge in list(bm.edges):
   if vertex in edge.verts:continue
   a,b=edge.verts;delta=b.co-a.co
   if delta.length_squared<1e-10:continue
   t=(vertex.co-a.co).dot(delta)/delta.length_squared
   if 1e-6<t<1-1e-6 and (a.co+delta*t-vertex.co).length<.001:
    _,split=bmesh.utils.edge_split(edge,a,t);split.co=vertex.co
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.001)
 bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.uv_layers.new(name='Source projection')
 for material in red.data.materials:mesh.materials.append(material)
 red.data=mesh
 bpy.data.objects.remove(piece,do_unlink=True)
 for o in (brown,red):
  bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.001);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-6);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()
 after={o.name:measure(o) for o in (brown,red)}

 if not all(v['nonmanifold']==v['degenerate']==0 for v in after.values()):
  bm=bmesh.new();bm.from_mesh(red.data);print('BOUNDARIES',[(tuple(red.matrix_world@e.verts[0].co),tuple(red.matrix_world@e.verts[1].co),len(e.link_faces)) for e in bm.edges if not e.is_manifold],flush=True);bm.free()
  print('ORIGINALS',original_brown,original_red,piece_measure,flush=True)
 assert all(v['nonmanifold']==v['degenerate']==0 for v in after.values()),after
 before_volume=original_brown['volume']+original_red['volume'];after_volume=sum(v['volume'] for v in after.values());assert abs(before_volume-after_volume)<max(.1,before_volume*1e-6),(before_volume,after_volume)
 assert outside=={o.name:signature(o) for o in bpy.data.objects if o.type=='MESH' and o not in (brown,red)}
 return dict(status='PASS',frontage_plane_native_anchors=[A,B],source='building-012',components=['market-base-012-front-2','market-base-012-front-3'],before=dict(brown=original_brown,red=original_red),transferred_piece=piece_measure,after=after,total_volume_before=before_volume,total_volume_after=after_volume,volume_residual=after_volume-before_volume,outside_meshes_preserved=len(outside),geometry_union_method='Brown clipped into two closed halves at its existing front plane; forward half stitched into red after removing only the coincident internal partition caps. All other meshes preserved.'),brown,red

def main():
 acquire();select_tooling(W/'tooling/58744eeaf71a21e9')
 from refinement_workspace import modified,_files,_ownership
 for asset in ('nottingham-market-front-brown','nottingham-market-front-red'):
  old=W/'round-10/assets'/asset;new=W/'round-38/assets'/asset
  if new.exists():
   assert not (new/'model.blend').exists()
   new.rename(new.with_name(new.name+'-failed-'+str(len(list(new.parent.glob(new.name+'-failed-*'))))))
  new.mkdir(parents=True);(new/'inspection').mkdir()
  for name in ('reference','mask-reference'):shutil.copytree(old/name,new/name)
  shutil.copytree(old/'modified',new/'input');shutil.copy2(old/'model.blend',new/'baseline.blend');shutil.copy2(old/'source-masks.json',new/'source-masks.json')
  config=json.loads((old/'workspace.json').read_text());config.update(source_blend=str(old/'model.blend'),source_blend_sha256=sha(old/'model.blend'),baseline_sha256=sha(new/'baseline.blend'),input_files=_files(new/'input'))
  bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));bpy.context.window.scene=bpy.data.scenes[config['scene_name']]
  report,brown,red=transfer()
  _,outside=_ownership(config)
  changed=[name for name in outside if outside[name]!=config['outside_geometry'].get(name)]
  expected=[red.name if asset.endswith('brown') else brown.name]
  assert changed==expected,(changed,expected)
  config['outside_geometry']=outside;config['authorized_adjacent_ownership_transfer']=dict(changed_objects=changed,evidence=str(new/'inspection/ownership-transfer.json'),reason='Restore the red house frontage incorrectly assigned to brown during the seven-building split; archived round10 approvals remain unchanged.')
  (new/'workspace.json').write_text(json.dumps(config,indent=2)+'\n')
  bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(new/'model.blend'));validation=modified(new)
  report.update(model_sha256=sha(new/'model.blend'),modified_views_sha256=sha(new/'modified/views.json'),validation=validation,prior_model_sha256=sha(old/'model.blend'))
  (new/'inspection/ownership-transfer.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(__file__,new/'ownership-transfer-recipe.py');print(asset,json.dumps(report),flush=True)
if __name__=='__main__':main()
