"""Localize a source-visible roof edge on a thin return beside the front roof."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 import bpy,bmesh
 from mathutils import Vector
 from render_slots import acquire,release
 from freeze_tooling import select_tooling
 from correct_prison_ramp_projection import clone_workspace
 from correct_source_projection import geometry
 acquire()
 try:
  select_tooling(WORK/'tooling/58744eeaf71a21e9')
  from refinement_workspace import modified
  old=WORK/'round-9/assets/nottingham-church-north-house';w=WORK/'round-50/assets/nottingham-church-north-house'
  if w.exists():raise RuntimeError('Immutable candidate exists')
  clone_workspace(old,w);bpy.ops.wm.open_mainfile(filepath=str(w/'model.blend'));before=geometry()
  objects={o.get('source_node'):o for o in bpy.data.collections['nottingham Working'].all_objects if o.get('asset_group')=='nottingham-church-north-house'}
  target=objects['building-130'];roof=objects['building-131'];rv=[roof.matrix_world@v.co for v in roof.data.vertices]
  # Exact front-roof ridge/eave edge, extended seven source pixels outward.
  ridge=rv[10].copy();eave=rv[7].copy();a,b,c=[rv[i] for i in [4,10,7]];normal=(b-a).cross(c-a).normalized()
  down=Vector((0,-.573576436351046,-.819152044288992));toward=Vector((0,-.819152044288992,.573576436351046))
  def on_roof(x,y):
   base=Vector((x,0,0))+y*down
   return base+toward*(normal.dot(a-base)/normal.dot(toward))
  outer_ridge=on_roof(ridge.x-7,ridge.dot(down)+5.2)
  outer_eave=on_roof(eave.x-7,eave.dot(down)+5.2)
  top=[ridge,eave,outer_eave,outer_ridge];bottom=[p-Vector((0,0,2)) for p in top]
  v=[target.matrix_world@p.co for p in target.data.vertices];faces=[tuple(f.vertices) for f in target.data.polygons];old_count=len(v)
  added=[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
  # Recalculate only the added closed component; original faces stay exact.
  bm=bmesh.new();vs=[bm.verts.new(p) for p in top+bottom]
  for f in added:bm.faces.new([vs[i] for i in f])
  bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.verts.index_update();bm.faces.index_update()
  assert all(e.is_manifold for e in bm.edges);assert all(f.calc_area()>1e-8 for f in bm.faces)
  volume=bm.calc_volume(signed=True);assert volume>0
  newfaces=[tuple(x.index+old_count for x in f.verts) for f in bm.faces];bm.free()
  mesh=bpy.data.meshes.new('Northern house roof edge return');mesh.from_pydata([p.co.copy() for p in target.data.vertices]+[target.matrix_world.inverted()@p for p in top+bottom],[],faces+newfaces);mesh.update()
  for mat in target.data.materials:mesh.materials.append(mat)
  for f,prior in zip(mesh.polygons,target.data.polygons):f.material_index=prior.material_index
  mesh.uv_layers.new(name='UVMap');target.data=mesh
  bpy.context.view_layer.update();bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(w/'model.blend'))
  report=dict(status='awaiting-source-and-independent-review',prior_model_sha256=sha(old/'model.blend'),added_vertices=[list(p) for p in top+bottom],added_faces=newfaces,added_closed_component_volume=volume,preserved_original_vertices=True,unchanged_source_masks=True,geometry_inference='Seven-source-pixel roof return with two-world-unit thickness; exact inner edge joins unchanged front roof131. Added return intercepts grazing roof-edge pixels formerly stretched across rear gable130.',approval='pending',recipe=str(Path(__file__).resolve()))
  (w/'roof-return-correction.json').write_text(json.dumps(report,indent=2)+'\n')
  modified(w);after=geometry();changed=[n for n in before if before[n]!=after[n]];assert changed==[target.name],changed
  report.update(model_sha256=sha(w/'model.blend'),modified_views_sha256=sha(w/'modified/views.json'),changed_meshes=changed)
  (w/'roof-return-correction.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
 finally:release()
if __name__=='__main__':main()
