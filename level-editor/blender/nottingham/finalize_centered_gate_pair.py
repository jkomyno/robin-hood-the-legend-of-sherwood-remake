"""Publish review metadata only after saved-material and independent pair checks."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
gate=WORK/'round-39/assets/nottingham-castle-gate-arch';tower=WORK/'round-43/assets/nottingham-castle-gate-east-tower'
pair=gate/'inspection/paired-v43';atlas=read(pair/'source-atlas.json')
assert atlas['gate_model_sha256']==sha(gate/'model.blend') and atlas['tower_model_sha256']==sha(tower/'model.blend')
assert atlas['counts']['source-colored:building-337']==869
for workspace in [gate,tower]:
 arch=workspace==gate;inspection=workspace/'inspection';independent=inspection/'independent-batch6-gate-pair-review.json'
 assert read(independent)['status']=='PASS'
 assert read(workspace/'known-rgb-validation.json')['status']=='PASS'
 assert read(inspection/'final-pair-structure.json')['status']=='PASS'
 actual=inspection/'stored-materials';assert read(actual/'audit.json')['status']=='STRUCTURAL-PASS'
 state_manifest=inspection/'endpoints-v6/states.json';states=read(state_manifest)['states'];assert len(states)==2
 for state in states:
  assert sha(state['model'])==state['model_sha256'] and sha(state['views'])==state['views_sha256']
  assert read(Path(state['directory'])/'stored-materials/audit.json')['status']=='STRUCTURAL-PASS'
 changes=(['Corrected the concealed tunnel and pier depth direction to the measured native axis; the exact original portcullis is centered within 0.043 source pixel at its own plane.',
           'Retained both metal endpoint meshes, front contour, crown and floor. Removed the redundant filler slab now contained by the corrected continuous walkway.',
           'Transferred the measured brown right jamb volume to its native375 exterior owner in the paired east tower.'] if arch else
          ['Added the exact measured brown gateway jamb as a separate static exterior component of source337, subtracting existing tower overlap to retain a shared contact boundary.',
           'Corrected the source-visible crown silhouette and eight capstones after full native-domain coverage exposed a missing rim. Preserved the lower body, mechanism and all unrelated geometry; kept the jamb outside interior material selectors.',
           'Froze the final paired arch geometry as projection context, eliminating stale pre-partition pier proxies without expanding source masks.'])
 gray=['Rear and concealed faces retain neutral materials because the source artwork cannot establish their appearance.',
       'Of 968 traced jamb samples, 869 have saved source color. The 66 arch-edge samples are within 0.984 pixel of the trace, 27 tower threshold/top/right samples within 1.883 pixels, and six samples are excluded by the native mask. These are recorded individually as tracing/contact fringes, not filled from unrelated pixels.',
       'The full admitted native-domain audit distinguishes broad mask pixels outside the receiver silhouette and foreground roofs. All eight measured cap polygons have 1844 visible samples and one exact boundary miss; the measured right rim has no interior misses from source y1182 to1245. Nine samples before that interval are mixed cap-edge color/background within two-pixel slanted-edge uncertainty.']
 dense=inspection/('dense-source-domain.json' if arch else 'final-source-ray-coverage.json')
 evidence=[inspection/'final-pair-structure.json',workspace/'known-rgb-validation.json',pair/'source-atlas.json',pair/'source-atlas-classification.json',pair/'brown-source-atlas.png',pair/'stored-materials/audit.json',state_manifest,gate/'inspection/jamb-transfer.json']
 if arch:evidence.extend([inspection/'source-coverage-witnesses.json',workspace/'gate-center-report.json'])
 else:evidence.extend([WORK/'round-42/assets/nottingham-castle-gate-east-tower/inspection/jamb-exterior-receiver.json',inspection/'native-domain-rejections.json',inspection/'native-domain-rejections.png',workspace/'crown-correction.json',inspection/'crown-geometry-proof.json',inspection/'crown-native-polygon-coverage.json'])
 contract=dict(version=1,status='PASS',asset_id=workspace.name,model_sha256=sha(workspace/'model.blend'),modified_views_sha256=sha(workspace/'modified/views.json'),source_sha256=sha(workspace/'reference/source.png'),source_masks_sha256=sha(workspace/'source-masks.json'),inspected_views=list(range(8)),source_visible_holes_found=False,geometry_changed=True,changes=changes,gray_surface_explanation=gray,independent_review=str(independent),independent_review_sha256=sha(independent),actual_saved_material_audit=str(actual/'audit.json'),actual_saved_material_audit_sha256=sha(actual/'audit.json'),actual_saved_material_sheet_sha256=sha(actual/'materials.png'),actual_saved_material_views=[dict(index=i,path=str(actual/f'view-{i}.png'),sha256=sha(actual/f'view-{i}.png'))for i in range(8)],dense_domain_evidence=str(dense),dense_domain_evidence_sha256=sha(dense),evidence=[dict(path=str(p),sha256=sha(p))for p in evidence],animation_states=states)
 write(workspace/'source-coverage-audit.json',contract)
 recipe=Path(__file__).parent/('center_castle_portcullis.py' if arch else 'refine_east_gate_crown_complete.py')
 candidate=dict(version=1,asset_id=workspace.name,status='ready-for-user',geometry_refined=True,geometry_reviewed=True,inspected_views=list(range(8)),recipe=str(recipe),recipe_sha256=sha(recipe),model_sha256=contract['model_sha256'],modified_views_sha256=contract['modified_views_sha256'],changes=changes,limitations=gray,animation_states=[dict(id=s['id'],directory=str(Path(s['directory']).relative_to(workspace)))for s in states],source_rgb_validation='known-rgb-validation.json',source_visibility_evidence=str(dense.relative_to(workspace)),stored_material_evidence='inspection/stored-materials/audit.json',independent_review=str(independent.relative_to(workspace)),user_approval='pending',texture_generation='not-started')
 write(workspace/'candidate.json',candidate)
 text='\n\n'.join(changes)+'\n\nThe saved model, all eight review views, actual packed-material views, both saved endpoint models and the paired assembly were checked. Exact source RGB validation found no mismatches. Lower tower geometry and portcullis meshes are preserved; the added exterior chunk has zero nonmanifold edges or degenerate faces.\n\n'+'\n\n'.join(gray)+'\n\nIndependent review: inspection/independent-batch6-gate-pair-review.json. Geometry awaits user review; texture generation has not started.\n'
 (workspace/'review.md').write_text(text)
 print('READY',workspace)
