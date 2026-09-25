"""Bind the independently reviewed dormer correction without changing approved pointers."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 w=Path(sys.argv[1]).resolve();a='nottingham-north-dormer-house';model=sha(w/'model.blend');frames=sha(w/'modified/views.json')
 independent=json.loads((w/'inspection/independent-review.json').read_text())
 assert independent['status']=='PASS' and independent['model_sha256']==model and independent['modified_views_sha256']==frames and independent['inspected_views']==list(range(8))
 for name,digest in independent['evidence_sha256'].items():assert sha(w/name)==digest, name
 for name in ['validation.json','known-rgb-validation.json','inspection/source-domain-difference.json','inspection/mesh-topology.json','inspection/outside-camera-validation.json']:
  record=json.loads((w/name).read_text());assert record['status']=='PASS',name
  assert record.get('model_sha256',model)==model,name
 material=json.loads((w/'inspection/stored-materials/audit.json').read_text());assert material['status'] in ['PASS','STRUCTURAL-PASS'] and not material.get('problems')
 assert material['model_sha256']==model and material['frame_manifest_sha256']==frames
 viewdata=json.loads((w/'modified/views.json').read_text());assert material['render_object_names']==(viewdata.get('render_object_names') or viewdata['object_names'])
 assert set(material['artifact_sha256'])=={'materials.png',*(f'view-{i}.png'for i in range(8))}
 for name,digest in material['artifact_sha256'].items():assert sha(w/'inspection/stored-materials'/name)==digest
 domain=json.loads((w/'inspection/source-domain-difference.json').read_text());assert domain['retained_source_pixel_count']==18770 and domain['added_source_pixel_count']==93 and domain['removed_source_pixel_count']==1178
 assert domain['retained_prop_receiver_counts']=={'building-553':642,'building-554':227} and not domain['transferred_original_prop_pixels']
 atlas=json.loads((w/'inspection/atlas-boundary-classification.json').read_text());assert atlas['model_sha256']==model and not atlas['classification_counts'].get('potential-material-hole',0)
 rgb=json.loads((w/'known-rgb-validation.json').read_text())['packets'];assert len(rgb)==1 and rgb[0]['views_sha256']==frames and rgb[0]['source_rgb_mismatches']==rgb[0]['missing_geometry_hits']==0
 changes=['Replaced the broad grazing roof/timber projection with a source-fitted roof return and short wall receiver.','Preserved the native lower footprint and ground datum, with a closed transition to the source-fitted upper wall.','Fitted the board perimeter to its own native source domain while preserving its original plane; added a concealed wall recess and retained the bucket geometry.','Removed source-classified foreground storage, coping and staircase contamination from house ownership, and restored legitimate roof, timber, board and bucket source pixels.']
 limitations=independent['limitations']
 proofs=['model.blend','modified/views.json','source-masks.json','reference/source.png','validation.json','return-correction.json','known-rgb-validation.json','inspection/independent-review.json','inspection/author-review.json','inspection/source-domain-difference.json','inspection/source-domain-difference.png','inspection/source-material-comparison.json','inspection/source-material-comparison.png','inspection/source-semantic-classification.json','inspection/atlas-boundary-classification.json','inspection/ground-datum.json','inspection/bucket-clearance.json','inspection/bucket-clearance-plan.png','inspection/mesh-topology.json','inspection/outside-camera-validation.json','inspection/stored-materials/audit.json','inspection/stored-materials/materials.png']
 audit=dict(version=1,status='PASS',asset_id=a,model_sha256=model,modified_views_sha256=frames,inspected_views=list(range(8)),actual_material_inspected_views=list(range(8)),source_visible_holes_found=False,geometry_changed=True,original_valid_source_pixels_retained=18770,restored_source_pixels=93,classified_foreign_original_samples_removed=1178,unexplained_source_losses=0,known_rgb_pixels=rgb[0]['known_pixels'],known_rgb_mismatches=0,atlas_boundary_classification=atlas['classification_counts'],evidence_sha256={p:sha(w/p)for p in proofs},limitations=limitations,reviewer='/root/audit_unseen_props/forest',independent_reviewer='/root/audit_unseen_props')
 (w/'source-coverage-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
 recipe=Path(__file__).with_name('correct_north_dormer_return.py');candidate=dict(version=1,asset_id=a,status='ready-for-user',geometry_refined=True,geometry_reviewed=True,inspected_views=list(range(8)),model_sha256=model,modified_views_sha256=frames,recipe=str(recipe),recipe_sha256=sha(recipe),changes=changes,limitations=limitations,independent_review='inspection/independent-review.json',source_rgb_validation='known-rgb-validation.json',source_visibility_evidence='inspection/source-domain-difference.json',stored_material_evidence='inspection/stored-materials/audit.json',source_comparison='inspection/source-material-comparison.png',source_comparison_secondary='inspection/source-domain-difference.png',source_trace='inspection/remaining-fleck-source.png',user_approval='pending',geometry_approval='pending-new-user-review',texture_generation='not-started')
 (w/'review.md').write_text('# Northern dormer source correction\n\n'+'\n'.join('- '+x for x in changes+limitations)+'\n\nAll eight solid and actual saved-material views were independently inspected. The exact source census retains 18,770 valid original pixels and restores 93, while removing 1,178 explicitly classified foreign samples. Original board and bucket receiver identities are preserved. Native ground datum and bucket clearance are verified; the hidden wall transition remains inferred. Renewed user geometry approval is pending, and original approved pointers remain untouched.\n')
 (w/'candidate.json').write_text(json.dumps(candidate,indent=2)+'\n');print(w/'candidate.json')
if __name__=='__main__':main()
