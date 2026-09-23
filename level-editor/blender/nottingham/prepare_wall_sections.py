"""Freeze V8 split-wall packets and apply provenance-preserving refined components."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
sys.path.insert(0,str(Path(__file__).parent))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def geometry(o):return {'vertices':[list(v.co)for v in o.data.vertices],'faces':[list(p.vertices)for p in o.data.polygons],'matrix':[list(row)for row in o.matrix_world]}
def main():
 p=argparse.ArgumentParser();p.add_argument('--asset',required=True);p.add_argument('--apply-existing',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
 from render_slots import acquire
 acquire()
 from freeze_tooling import select_tooling
 tooling=select_tooling(WORK/'tooling/94116d984f92dbae')
 import bpy,bmesh
 from refinement_workspace import prepare,modified
 workspace=WORK/'round-13/assets'/a.asset;evidence=WORK/'grouped/nottingham-grouped-v8.evidence'
 if workspace.exists() and not a.apply_existing:raise FileExistsError(workspace)
 source_asset=a.asset if a.asset=='nottingham-south-gate-east-tower' else ('nottingham-southwest-curtain-wall' if 'southwest' in a.asset else 'nottingham-south-curtain-wall')
 bpy.ops.wm.open_mainfile(filepath=str(WORK/'grouped/nottingham-grouped-v8.blend'));bpy.context.view_layer.update()
 working=bpy.data.collections['nottingham Working']
 # Partition artifacts carry geometry and source UVs; restore neutral fallback before baking.
 neutral=bpy.data.materials.new('Partition unknown neutral');neutral.diffuse_color=(0.5,0.5,0.5,1)
 for obj in working.all_objects:
  if obj.type=='MESH' and obj.get('projection_component') and not obj.data.materials:obj.data.materials.append(neutral)
 if a.apply_existing:
  bpy.ops.wm.open_mainfile(filepath=str(workspace/'model.blend'));bpy.context.view_layer.update();neutral=bpy.data.materials.get('Partition unknown neutral')
 else:
  prepare(workspace,asset_id=a.asset,scene_name='nottingham Refinement',collection_name='nottingham Working',source_path=WORK/'source-states/covered.png',grouping_manifest=evidence/'catalog.json',inventory_path=evidence/'inventory.json',review_path=evidence/'grouping-review.json',source_mask_manifest=WORK/'round-1/assets'/source_asset/'source-masks.json',width=384,height=448,elevation_degrees=35,context_padding=40,framing_padding=1.15)
 working=bpy.data.collections['nottingham Working'];targets=[o for o in working.all_objects if o.type=='MESH' and o.get('asset_group')==a.asset and not o.hide_render]
 outside={o.name:geometry(o)for o in working.all_objects if o.type=='MESH' and o not in targets}
 replacements={o.get('projection_component'):o for o in targets if o.get('projection_component')}
 parts=WORK/'wall-partitions-v8/components.blend'
 with bpy.data.libraries.load(str(parts),link=False)as(src,dst):dst.objects=sorted(replacements)
 report=[]
 for imported in dst.objects:
  target=replacements[imported['projection_component']]
  if imported.parent is not None:raise ValueError('Partition artifact unexpectedly parented')
  # Unlinked library objects have unevaluated matrix_world. Partition artifacts
  # are unparented, so their persisted matrix_basis is the source world matrix.
  mesh=imported.data.copy();mesh.transform(target.matrix_world.inverted()@imported.matrix_basis);mesh.materials.clear();mesh.materials.append(neutral);target.data=mesh
  bm=bmesh.new();bm.from_mesh(mesh);defects={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'degenerate_faces':sum(f.calc_area()<1e-8 for f in bm.faces)};bm.free()
  if any(defects.values()):raise ValueError((target.name,defects))
  report.append({'component':target['projection_component'],'validation':defects,'geometry_sha256':hashlib.sha256(json.dumps(geometry(target),sort_keys=True).encode()).hexdigest()})
  bpy.data.objects.remove(imported,do_unlink=True)
 if a.asset=='nottingham-south-gate-east-tower':
  prior=WORK/'round-1/assets'/a.asset/'model.blend'
  with bpy.data.libraries.load(str(prior),link=False)as(src,dst):dst.objects=[name for name in src.objects if name.startswith('South gate eastern turret and return /')]
  by_node={o.get('source_node'):o for o in targets if not o.get('projection_component')}
  copied=[]
  for imported in dst.objects:
   node=imported.get('source_node')
   if node in by_node and imported.type=='MESH':
    target=by_node[node];target.data=imported.data.copy();copied.append(node)
   bpy.data.objects.remove(imported,do_unlink=True)
  if set(copied)!=set(by_node):raise ValueError(('Tower canonical imports',copied,list(by_node)))
  report.append({'preserved_refined_tower_nodes':copied,'source_model_sha256':sha(prior)})
 if outside!={o.name:geometry(o)for o in working.all_objects if o.type=='MESH' and o not in targets}:raise ValueError('Outside geometry changed')
 before={o.name:geometry(o)for o in targets};bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(workspace/'model.blend'));modified(workspace)
 if before!={o.name:geometry(o)for o in targets}:raise ValueError('Source bake changed component geometry')
 proof={'status':'PASS','tooling':tooling,'partition_blend_sha256':sha(parts),'partition_proof_sha256':sha(WORK/'wall-partitions-v8/partition-proof.json'),'components':report,'outside_geometry_preserved':len(outside),'post_projection_geometry_preserved':True,'grouping_revision':8}
 (workspace/'partition-application.json').write_text(json.dumps(proof,indent=2)+'\n')
 candidate={'version':1,'asset_id':a.asset,'status':'fix-needed','geometry_refined':True,'geometry_reviewed':False,'inspected_views':[],'recipe':str(Path(__file__).resolve()),'recipe_sha256':sha(__file__),'model_sha256':sha(workspace/'model.blend'),'modified_views_sha256':sha(workspace/'modified/views.json'),'changes':['Split the curtain at the requested structural boundaries.','Retain measured parapet geometry and close new internal partition seams; rebuild native wall-walk envelopes.'],'limitations':['New internal seam caps and concealed depth are inferred.','Standalone partition framing and source projection await visual inspection.'],'approval':'pending','texture_generation':'not-started'}
 if a.asset=='nottingham-south-gate-east-tower':
  candidate['changes']=['Transfer the adjoining wall box to southern wall section2.','Preserve the existing refined tower roof and structural meshes; retain the disjoint201 tower platform component.']
 (workspace/'candidate.json').write_text(json.dumps(candidate,indent=2)+'\n');(workspace/'review.md').write_text('# Curtain partition review\n\nFresh V8 baseline and fixed eight-camera input/modified packets. Geometry partition provenance is bound in partition-application.json. Visual review is pending.\n')
 print('WALL_WORKSPACE_COMPLETE',a.asset,flush=True)
if __name__=='__main__':main()
