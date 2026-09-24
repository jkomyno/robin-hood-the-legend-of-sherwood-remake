"""Transfer the measured right jamb volume to the neighboring tower receiver."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
POLY=[(966,1414),(980,1427),(981,1488),(966,1477)]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 sys.path.insert(0,str(Path(__file__).parent))
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy,bmesh
 from mathutils import Vector,Matrix
 from refine_church import SIN,COS,neutral,fingerprint
 from refinement_workspace import prepare
 gate=WORK/'round-39/assets/nottingham-castle-gate-arch';tower=WORK/'round-39/assets/nottingham-castle-gate-east-tower';old=WORK/'round-23/assets/nottingham-castle-gate-east-tower'
 def volume(o):
  bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world);v=abs(bm.calc_volume());bm.free();return v
 def boolean(o,cutter,operation):
  bpy.context.view_layer.objects.active=o
  mod=o.modifiers.new('Measured jamb volume '+operation,'BOOLEAN');mod.operation=operation;mod.solver='EXACT';mod.object=cutter
  bpy.ops.object.modifier_apply(modifier=mod.name)
 def clone(o,name):
  q=o.copy();q.data=o.data.copy();q.name=name;bpy.data.collections['nottingham Working'].objects.link(q);return q
 bpy.ops.wm.open_mainfile(filepath=str(gate/'model.blend'));bpy.context.view_layer.update();coll=bpy.data.collections['nottingham Working']
 body=next(o for o in coll.all_objects if o.type=='MESH' and o.get('asset_group')=='nottingham-castle-gate-arch' and o.get('source_node')=='building-333' and not o.get('animation_state'))
 before=volume(body);ratio=35.94214/31.6296
 verts=[]
 # A source-plane polygon extruded through the entire existing moulding. The
 # cutter adds no geometry: the transferred mesh is its exact intersection.
 for depth in [.05,-30]:
  for x,sy in POLY:
   y=1585.248+(x-984)/ratio;z=y-sy
   verts.append((x,-(y+depth)/SIN,z/COS))
 mesh=bpy.data.meshes.new('Measured brown jamb cutter');mesh.from_pydata(verts,[],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]);mesh.update();bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
 cutter=bpy.data.objects.new('Measured brown jamb cutter',mesh);coll.objects.link(cutter)
 chunk=clone(body,'Measured existing gate jamb volume');boolean(chunk,cutter,'INTERSECT');chunk_volume=volume(chunk);assert chunk_volume>1
 boolean(body,cutter,'DIFFERENCE');body_after=volume(body);assert abs(before-body_after-chunk_volume)<.01*chunk_volume,(before,body_after,chunk_volume)
 bpy.data.objects.remove(cutter,do_unlink=True)
 chunk['transfer_world_matrix_json']=json.dumps([list(r)for r in chunk.matrix_world])
 original_world=[list(chunk.matrix_world@v.co)for v in chunk.data.vertices]
 chunk['transfer_world_vertices_json']=json.dumps(original_world)
 library=gate/'inspection/transferred-jamb.blend';bpy.data.libraries.write(str(library),{chunk})
 chunk_name=chunk.name;bpy.data.objects.remove(chunk,do_unlink=True)
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(gate/'model.blend'))
 bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'));c=json.loads((old/'workspace.json').read_text())
 if not tower.exists():prepare(tower,asset_id=tower.name,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',projection_manifest=old/'projection-layers.json',source_mask_manifest=old/'source-masks.json',width=320,height=400,context_padding=35,framing_padding=c['framing_padding'])
 else:bpy.ops.wm.open_mainfile(filepath=str(tower/'baseline.blend'));bpy.context.view_layer.update()
 coll=bpy.data.collections['nottingham Working'];before_objects={o.name:fingerprint(o) for o in coll.all_objects if o.type=='MESH'}
 with bpy.data.libraries.load(str(library),link=False) as (a,b):b.objects=[chunk_name]
 chunk=b.objects[0];coll.objects.link(chunk);chunk.parent=None;chunk.matrix_world=Matrix.Identity(4)
 # Materialize the recorded world vertices instead of decomposing/recomposing
 # a parent matrix: that round trip otherwise introduces float32 drift.
 for v,p in zip(chunk.data.vertices,original_world):v.co=p
 bpy.context.view_layer.update()
 restored_world=[list(chunk.matrix_world@v.co)for v in chunk.data.vertices]
 world_error=max(abs(a-b)for p,q in zip(original_world,restored_world)for a,b in zip(p,q));assert world_error<1e-5,world_error
 overlaps=[]
 for o in list(coll.all_objects):
  if o.type!='MESH' or o.get('asset_group')!=tower.name or o.get('source_node')!='building-337' or o.get('animation_state'):continue
  test=clone(o,'Jamb contact test');boolean(test,chunk,'INTERSECT');v=volume(test);bpy.data.objects.remove(test,do_unlink=True)
  if v>1e-3:overlaps.append((v,o))
 assert overlaps,'Measured jamb volume does not physically meet the existing tower'
 overlaps.sort(key=lambda x:x[0],reverse=True);overlap,target=overlaps[0];total_overlap=sum(v for v,o in overlaps)
 for v,o in overlaps[1:]:boolean(chunk,o,'DIFFERENCE')
 old_volume=volume(target);boolean(target,chunk,'UNION');new_volume=volume(target);delta=new_volume-old_volume-(chunk_volume-total_overlap)
 assert abs(delta)<max(.1,chunk_volume*1e-3),(delta,old_volume,new_volume,chunk_volume,overlap)
 bpy.data.objects.remove(chunk,do_unlink=True)
 assert all(fingerprint(bpy.data.objects[n])==v for n,v in before_objects.items() if n!=target.name)
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(tower/'model.blend'))
 report=dict(status='geometry-transferred-awaiting-projection',gate_model_sha256=sha(gate/'model.blend'),tower_model_sha256=sha(tower/'model.blend'),source_polygon=POLY,native_owner_mask=375,gate_source_mask288_unchanged=True,removed_gate_volume=before-body_after,transferred_volume=chunk_volume,original_tower_intersection_volume=total_overlap,physical_contacts=[dict(object=o.name,volume=v)for v,o in overlaps],tower_changed_object=target.name,tower_old_volume=old_volume,tower_new_volume=new_volume,tower_union_volume_residual=delta,combined_union_volume_residual=delta-(before-body_after-chunk_volume),library_world_vertex_max_error=world_error,library_world_bounds_before=[[min(p[i]for p in original_world)for i in range(3)],[max(p[i]for p in original_world)for i in range(3)]],library_world_bounds_after=[[min(p[i]for p in restored_world)for i in range(3)],[max(p[i]for p in restored_world)for i in range(3)]],other_tower_objects_preserved=len(before_objects)-1)
 (gate/'inspection/jamb-transfer.json').write_text(json.dumps(report,indent=2)+'\n');(tower/'inspection').mkdir(exist_ok=True);(tower/'inspection/jamb-transfer.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
