"""Give the stair landing exclusive geometry instead of a coplanar wall top."""
import sys,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
def main():
 sys.path.insert(0,str(Path(__file__).parent))
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy,bmesh
 from mathutils import Vector
 import refinement_workspace as rw
 from refine_village_secondary import digest
 from refine_environment import _topology
 asset='nottingham-southwest-curtain-wall-north';old=WORK/'round-13/assets'/asset;new=WORK/'round-31/assets'/asset;stair=WORK/'round-31/assets/nottingham-southwest-wall-stair';c=json.loads((old/'workspace.json').read_text())
 bpy.ops.wm.open_mainfile(filepath=str(stair/'model.blend'));o=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')==stair.name and not o.hide_render);landing=[o.matrix_world@o.data.vertices[i].co for i in [1,2,40,39]]
 from mathutils.geometry import convex_hull_2d
 points=[o.matrix_world@v.co for v in o.data.vertices];indices=convex_hull_2d([Vector((p.x,p.y)) for p in points]);quad=[points[i] for i in indices]
 if not new.exists():
  bpy.ops.wm.open_mainfile(filepath=str(old/'model.blend'))
  rw.prepare(new,asset_id=asset,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=old/'reference/source.png',grouping_manifest=old/'reference/grouping.json',inventory_path=old/'reference/inventory.json',review_path=old/'reference/grouping-review.json',source_mask_manifest=old/'source-masks.json',width=512,height=448,context_padding=48,framing_padding=1.1)
 bpy.ops.wm.open_mainfile(filepath=str(new/'baseline.blend'));bpy.context.view_layer.update()
 before={o.name:digest(o) for o in bpy.context.scene.objects if o.type=='MESH'};wall=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_group')==asset and o.get('source_node')=='building-220' and not o.hide_render)
 z=max(p.z for p in landing)+1;n=len(quad);v=[(p.x,p.y,h) for h in [-1,z] for p in quad];f=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
 mesh=bpy.data.meshes.new('Landing footprint cutter');mesh.from_pydata(v,[],f);mesh.update();bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();cut=bpy.data.objects.new('Landing footprint cutter',mesh);bpy.context.scene.collection.objects.link(cut)
 mod=wall.modifiers.new('Stair landing exclusive footprint','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cut;bpy.context.view_layer.objects.active=wall;wall.select_set(True);bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cut,do_unlink=True)
 changed=[o.name for o in bpy.context.scene.objects if o.type=='MESH' and before[o.name]!=digest(o)];assert changed==[wall.name],changed
 topo=_topology(wall.data);assert not topo['nonmanifold_edges'] and not topo['degenerate_faces'],topo
 (new/'inspection').mkdir(exist_ok=True);report=dict(asset_id=asset,changed_objects=changed,landing_footprint_world=[list(p) for p in landing],stair_exclusive_footprint_world=[list(p) for p in quad],topology=topo,outside_objects_preserved=len(before)-1,changes=['Removed the wall-walk volume beneath the stair and recovered landing so their source-visible surfaces are not blocked by the wall volume.'],limitations=['The stair remains a separately selectable asset; its matching landing must be composed with this wall revision.'])
 (new/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n');bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(new/'model.blend'));rw.modified(new)
 from restore_foreign_uv_schema import restore_foreign_uv_schema
 restore_foreign_uv_schema(new,apply=True)
 from audit_stored_materials import run
 audit=run(new,new/'inspection/stored-material-final',render=True,export=False);assert audit['status']=='STRUCTURAL-PASS',audit['problems']
 (new/'candidate.json').write_text(json.dumps(dict(version=1,asset_id=asset,status='refinement-in-progress',recipe=str(Path(__file__).resolve())),indent=2)+'\n')
if __name__=='__main__':main()
