"""Bind verified shutter-house return evidence for a new user geometry review."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'level-editor/work/nottingham-refinement';W=WORK/'round-33/assets/nottingham-southeast-shutter-house'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,d):Path(p).write_text(json.dumps(d,indent=2)+'\n')
def main():
 model=sha(W/'model.blend');views=sha(W/'modified/views.json');qa=read(W/'inspection/independent-review.json');rgb=read(W/'known-rgb-validation.json')
 assert qa['status']=='PASS' and qa['model_sha256']==model and qa['modified_views_sha256']==views
 domain=read(W/'inspection/source-domain-difference.json');assert domain['status']=='PASS' and domain['model_sha256']==model
 assert rgb['status']=='PASS' and all(p['views_sha256']==views and p['known_pixels']>0 and p['source_rgb_mismatches']==p['missing_geometry_hits']==0 for p in rgb['packets'])
 for name in ['validation.json','inspection/outside-camera-validation.json']:assert read(W/name)['status']=='PASS'
 stored=read(W/'inspection/stored-materials/audit.json');assert stored['status']=='STRUCTURAL-PASS' and not stored['problems'] and stored['model_sha256']==model
 for name,digest in qa['evidence'].items():assert sha(W/name)==digest
 c=read(W/'candidate.json');c.update(status='ready-for-user',geometry_reviewed=True,inspected_views=list(range(8)),independent_review='inspection/independent-review.json',source_rgb_validation='known-rgb-validation.json',user_approval='pending',geometry_approval='pending',texture_generation='not-started');write(W/'candidate.json',c)
 proof=read(W/'short-return-correction.json');proof.update(status='PASS',inspected_views=list(range(8)),independent_review='inspection/independent-review.json',approval='pending');write(W/'short-return-correction.json',proof)
 paths=['model.blend','source-masks.json','modified/views.json','reference/source.png','inspection/independent-review.json','inspection/stored-materials/audit.json','inspection/stored-materials/materials.png','inspection/outside-camera-validation.json','known-rgb-validation.json','inspection/source-comparison.png','inspection/native-source.png','inspection/source-domain-difference.json','inspection/source-domain-difference.png']
 write(W/'source-coverage-audit.json',dict(version=1,status='PASS',asset_id=W.name,model_sha256=model,modified_views_sha256=views,inspected_views=list(range(8)),actual_material_inspected_views=list(range(8)),findings=['Foreground garden-return pixels no longer project onto the house.','Observed narrow timber transition is localized on the short front return; full-depth diagonal stretch removed.','Roof/body join continuous in diagnostic and actual saved materials.'],limitations=c['limitations']+['Exact RGB proves color preservation for accepted pixels, not completeness of all possible source ownership. Single-view hidden-side inference remains a user geometry decision.'],evidence_sha256={p:sha(W/p)for p in paths},reviewer='audit_unseen_props/forest',independent_reviewer='audit_unseen_props'))
 print(W,'ready-for-user',sum(p['known_pixels']for p in rgb['packets']))
if __name__=='__main__':main()
