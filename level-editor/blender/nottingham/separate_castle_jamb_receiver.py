"""Keep the transferred jamb exterior separate from retained room materials."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
def main():
 sys.path.insert(0,str(Path(__file__).parent))
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 select_tooling(WORK/'tooling/58744eeaf71a21e9')
 import bpy,bmesh
 from mathutils import Matrix
 from refine_church import copy_component,neutral,fingerprint
 from refinement_workspace import prepare,_reproject,modified
 from restore_foreign_uv_schema import restore_foreign_uv_schema
 from audit_stored_materials import run
 baseline=WORK/'round-23/assets/nottingham-castle-gate-east-tower';prev=WORK/'round-40/assets/nottingham-castle-gate-east-tower';out=WORK/'round-42/assets/nottingham-castle-gate-east-tower';gate=WORK/'round-39/assets/nottingham-castle-gate-arch'
 if '--audit' in sys.argv:
  workspace=Path(sys.argv[sys.argv.index('--audit')+1]).resolve();run(workspace,workspace/'inspection/stored-materials',render=True,export=False);return
 if '--finish' in sys.argv:
  bpy.ops.wm.open_mainfile(filepath=str(out/'model.blend'));modified(out);restore_foreign_uv_schema(out);run(out,out/'inspection/stored-materials',render=True,export=False);return
 bpy.ops.wm.open_mainfile(filepath=str(gate/'model.blend'));bpy.context.view_layer.update();context={o.name:dict(vertices=[list(o.matrix_world@v.co)for v in o.data.vertices],visible=not o.hide_render,source_node=o.get('source_node'))for o in bpy.data.collections['nottingham Working'].all_objects if o.type=='MESH' and o.get('asset_group')==gate.name}
 bpy.ops.wm.open_mainfile(filepath=str(baseline/'model.blend'));c=json.loads((baseline/'workspace.json').read_text())
 def paired_context():
  coll=bpy.data.collections[c['collection_name']]
  for o in list(coll.all_objects):
   if o.type=='MESH' and (o.get('asset_group')==gate.name or o.get('source_node')in {r['source_node']for r in context.values()}):bpy.data.objects.remove(o,do_unlink=True)
  with bpy.data.libraries.load(str(gate/'model.blend'),link=False)as(a,b):b.objects=list(context)
  for name,o in zip(context,b.objects):
   coll.objects.link(o);o.parent=None;o.matrix_world=Matrix.Identity(4)
   for v,xyz in zip(o.data.vertices,context[name]['vertices']):v.co=xyz
   o.hide_render=not context[name]['visible'];o.hide_set(o.hide_render)
  bpy.context.view_layer.update()
 if not out.exists():
  paired_context()
  prepare(out,asset_id=out.name,scene_name=c['scene_name'],collection_name=c['collection_name'],source_path=baseline/'reference/source.png',grouping_manifest=baseline/'reference/grouping.json',inventory_path=baseline/'reference/inventory.json',review_path=baseline/'reference/grouping-review.json',projection_manifest=baseline/'projection-layers.json',source_mask_manifest=prev/'source-masks.json',width=320,height=400,context_padding=35,framing_padding=c['framing_padding'])
 else:bpy.ops.wm.open_mainfile(filepath=str(out/'baseline.blend'));bpy.context.view_layer.update()
 coll=bpy.data.collections[c['collection_name']];before={o.name:fingerprint(o)for o in coll.all_objects if o.type=='MESH'}
 with bpy.data.libraries.load(str(gate/'inspection/transferred-jamb.blend'),link=False)as(a,b):b.objects=['Measured existing gate jamb volume']
 source=b.objects[0];template=next(o for o in coll.all_objects if o.get('asset_group')==out.name and o.get('projection_component')=='mechanism-base');chunk=copy_component(template,'gate-jamb-exterior');chunk.data=source.data;chunk.parent=None;chunk.matrix_world=Matrix.Identity(4)
 for v,p in zip(chunk.data.vertices,json.loads(source['transfer_world_vertices_json'])):v.co=p
 bpy.data.objects.remove(source,do_unlink=True);chunk['projection_component']='gate-jamb-exterior';chunk['reveal_component_patch_id']='patch-005';chunk['reveal_component_role']='retained';chunk['reveal_state']='both';chunk.hide_render=False;chunk.hide_set(False)
 def volume(o):
  bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world);v=abs(bm.calc_volume());bm.free();return v
 original_volume=volume(chunk)
 for o in list(coll.all_objects):
  if o==chunk or o.type!='MESH' or o.get('asset_group')!=out.name or o.get('source_node')!='building-337' or o.get('animation_state'):continue
  bpy.context.view_layer.objects.active=chunk;mod=chunk.modifiers.new('Shared boundary with '+o.name,'BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=o;bpy.ops.object.modifier_apply(modifier=mod.name)
 bm=bmesh.new();bm.from_mesh(chunk.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=0.002);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=0.002);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(chunk.data);bm.free()
 chunk.data.materials.clear();chunk.data.materials.append(neutral())
 fallback=chunk.data.attributes.get('reprojection_fallback_material')
 if fallback:chunk.data.attributes.remove(fallback)
 for f in chunk.data.polygons:f.material_index=0
 for layer in list(chunk.data.uv_layers):chunk.data.uv_layers.remove(layer)
 chunk.data.uv_layers.new(name='UnprojectedSurfaceUV');assert all(fingerprint(bpy.data.objects[n])==v for n,v in before.items())
 pp=out/'projection-layers.json';p=json.loads(pp.read_text());components=p['projection_reviews']['patch-005']['receiver_components']['exterior'][0]['projection_components']
 if 'gate-jamb-exterior'not in components:components.append('gate-jamb-exterior')
 pp.write_text(json.dumps(p,indent=2)+'\n')
 mp=out/'source-masks.json';m=json.loads(mp.read_text());m['projections']['exterior']['assignments']=[r for r in m['projections']['exterior']['assignments']if r.get('projection_component')!='gate-jamb-exterior'];m['projections']['exterior']['assignments'].append(dict(source_node='building-337',projection_component='gate-jamb-exterior',reviewed=True,constraint_kind='reviewed-native-silhouette',mask_indices=[375],review_evidence=str(gate/'inspection/jamb-transfer.json'),review_note='Exact transferred closed gateway reveal exterior; native375 owns this source-visible brown side. Explicitly excluded from room interior receiver selectors.'))
 m['projections']['exterior']['occluder_constraints']=[r for r in m['projections']['exterior'].get('occluder_constraints',[])if r['source_node']!='building-349']
 mp.write_text(json.dumps(m,indent=2)+'\n');(out/'inspection').mkdir(exist_ok=True)
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));config=json.loads((out/'workspace.json').read_text());_reproject(config,out/'projection/jamb-scoped-first-test');bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
 bm=bmesh.new();bm.from_mesh(chunk.data);topology=dict(nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),degenerate_faces=sum(f.calc_area()<1e-8 for f in bm.faces));bm.free();assert not any(topology.values()),topology
 report=dict(status='projection-test-ready',model_sha256=hashlib.sha256((out/'model.blend').read_bytes()).hexdigest(),component=chunk.name,original_volume=original_volume,disjoint_exterior_volume=volume(chunk),shared_contact_removed_volume=original_volume-volume(chunk),topology=topology,all_original_meshes_preserved=len(before),exterior_component='gate-jamb-exterior',interior_components=p['projection_reviews']['patch-005']['receiver_components']['interior-patch-005'][0]['projection_components'])
 (out/'inspection/jamb-exterior-receiver.json').write_text(json.dumps(report,indent=2)+'\n');print('SCOPED_JAMB_TEST_READY',json.dumps(report),flush=True)
 # Complete packets only after the full layer bake has retained the explicit
 # exterior material on every newly transferred face.
 assert any(mat and mat.get('ownership_label')=='exterior' for mat in chunk.data.materials) or any(mat and 'owned exterior' in mat.name for mat in chunk.data.materials)
 if '--test-only' in sys.argv:return
 modified(out);restore_foreign_uv_schema(out);run(out,out/'inspection/stored-materials',render=True,export=False)
if __name__=='__main__':main()
