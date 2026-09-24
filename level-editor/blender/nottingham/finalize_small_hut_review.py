"""Bind completed forge audits after explicit eight-view visual inspection."""
import sys,json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 if '--visual-review-complete' not in sys.argv:raise SystemExit('Inspect all eight solid, projected and actual-material views plus source comparisons first.')
 w=Path(sys.argv[1]).resolve();a='nottingham-village-small-hut';model=sha(w/'model.blend');frames=sha(w/'modified/views.json')
 for name in ['validation.json','known-rgb-validation.json','inspection/full-native-source-coverage.json','inspection/stored-material/audit.json']:
  record=json.loads((w/name).read_text())
  if record.get('status') not in ['PASS','STRUCTURAL-PASS']:raise ValueError((name,record.get('status')))
  if record.get('model_sha256',model)!=model:raise ValueError('Stale model: '+name)
  if record.get('modified_views_sha256',frames)!=frames:raise ValueError('Stale frames: '+name)
 independent=json.loads((w/'inspection/independent-review.json').read_text())
 assert independent['status']=='PASS' and independent['model_sha256']==model and independent['modified_views_sha256']==frames and independent['inspected_views']==list(range(8))
 material=json.loads((w/'inspection/stored-material/audit.json').read_text())
 assert material['model_sha256']==model and material['frame_manifest_sha256']==frames
 viewdata=json.loads((w/'modified/views.json').read_text())
 assert sorted(material['render_object_names'])==sorted(viewdata.get('render_object_names') or viewdata['object_names'])
 assert set(material['artifact_sha256'])=={'materials.png',*(f'view-{i}.png' for i in range(8))}
 for name,digest in material['artifact_sha256'].items():assert sha(w/'inspection/stored-material'/name)==digest
 rgb=json.loads((w/'known-rgb-validation.json').read_text())
 assert len(rgb['packets'])==1 and rgb['packets'][0]['views_sha256']==frames
 comparison=json.loads((w/'inspection/source-material-comparison.json').read_text())
 assert comparison['model_sha256']==model and comparison['modified_views_sha256']==frames and comparison['proposed_geometry_misses']==0
 assert comparison['status']=='PASS' and comparison.get('visual_source_comparison_inspected') is True
 native=json.loads((w/'inspection/full-native-source-coverage.json').read_text())
 assert native['native_pixels']==6932 and native['counts']=={'accepted':6932},native['counts']
 evidence_root=ROOT/'level-editor/work/nottingham-refinement/coordinator-audit/small-hut-projection'
 for f in ['structural-landmarks.png','structural-landmarks.json','source-detail.png']:
  shutil.copyfile(evidence_root/f,w/'inspection'/f)
 limitations=['Concealed ridge position, square timber sections and symmetric chimney taper are inferred from the visible artwork; this geometry revision requires renewed user approval before texture generation.','The complete native artwork is preserved. Rear-facing surfaces and hidden support faces remain neutral because their appearance is not visible in the source.','Source-visible post feet follow the local slope, below the generic zero-height ground proxy; only that explicitly evidenced proxy is excluded from projection occlusion.']
 changes=['Replaced the false front gable and grazing rear roof with a source-fitted hipped roof.','Added all three visible support posts and the front eave beam; fitted their source-visible tops and feet.','Restored the chimney hood and rim silhouette with symmetric geometry and a hollow opening.']
 proofs=['inspection/independent-review.json','inspection/full-native-source-coverage.json','inspection/source-material-comparison.json','inspection/source-material-comparison.png','inspection/stored-material/audit.json','inspection/stored-material/materials.png','geometry-report.json','post-ground-evidence.json','known-rgb-validation.json']
 audit=dict(version=1,status='PASS',asset_id=a,model_sha256=model,modified_views_sha256=frames,source_sha256=sha(w/'reference/source.png'),source_masks_sha256=sha(w/'source-masks.json'),inspected_views=list(range(8)),source_visible_holes_found=False,geometry_changed=True,changes=changes,gray_surface_explanation=limitations,proof_artifacts=[dict(path=str(w/p),sha256=sha(w/p))for p in proofs])
 (w/'source-coverage-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
 recipe=Path(__file__).with_name('correct_small_hut_roof.py');structure=Path(__file__).with_name('small_hut_source_structure.py')
 candidate=dict(version=1,asset_id=a,status='ready-for-user',geometry_refined=True,geometry_reviewed=True,inspected_views=list(range(8)),model_sha256=model,modified_views_sha256=frames,recipe=str(recipe),recipe_sha256=sha(recipe),structure_recipe=str(structure),structure_recipe_sha256=sha(structure),changes=changes,limitations=limitations,independent_review='inspection/independent-review.json',source_rgb_validation='known-rgb-validation.json',source_visibility_evidence='inspection/full-native-source-coverage.json',stored_material_evidence='inspection/stored-material/audit.json',source_comparison='inspection/source-material-comparison.png',source_comparison_secondary='inspection/full-native-source-coverage.png',source_trace='inspection/structural-landmarks.png',user_approval='pending',geometry_approval='pending-new-user-review',texture_generation='not-started')
 (w/'candidate.json').write_text(json.dumps(candidate,indent=2)+'\n');print(w/'candidate.json')
if __name__=='__main__':main()
