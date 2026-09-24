"""Bind the independently reviewed northern house roof-return candidate."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'level-editor/work/nottingham-refinement/round-51/assets/nottingham-church-north-house'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def main():
 model=sha(W/'model.blend');views=sha(W/'modified/views.json');qa=read(W/'inspection/independent-review.json')
 assert qa['status']=='PASS' and qa['model_sha256']==model and qa['modified_views_sha256']==views
 for name,value in qa['evidence'].items():assert sha(W/name)==value
 for name in ['validation.json','known-rgb-validation.json','inspection/source-domain-difference.json','inspection/geometry-preservation.json']:assert read(W/name)['status']=='PASS'
 rgb=read(W/'known-rgb-validation.json');assert all(p['views_sha256']==views and p['known_pixels']>0 and p['source_rgb_mismatches']==p['missing_geometry_hits']==0 for p in rgb['packets'])
 stored=read(W/'inspection/unseen-stored-material/audit.json');assert stored['status']=='STRUCTURAL-PASS' and stored['model_sha256']==model and not stored['problems']
 c=read(W/'candidate.json');c.update(status='ready-for-user',geometry_refined=True,geometry_reviewed=True,inspected_views=list(range(8)),independent_review='inspection/independent-review.json',source_rgb_validation='known-rgb-validation.json',model_sha256=model,modified_views_sha256=views,geometry_approval='pending',user_approval='pending',texture_generation='not-started');write(W/'candidate.json',c)
 proof=read(W/'roof-return-correction.json');proof.update(status='PASS',independent_review='inspection/independent-review.json',approval='pending');write(W/'roof-return-correction.json',proof)
 paths=['model.blend','modified/views.json','source-masks.json','reference/source.png','known-rgb-validation.json','inspection/independent-review.json','inspection/source-domain-difference.json','inspection/source-domain-difference.png','inspection/geometry-preservation.json','inspection/unseen-stored-material/audit.json','inspection/unseen-stored-material/materials.png','inspection/independent-source-edge.png']
 write(W/'source-coverage-audit.json',dict(version=1,status='PASS',asset_id=W.name,model_sha256=model,modified_views_sha256=views,inspected_views=list(range(8)),actual_material_inspected_views=list(range(8)),findings=c['changes'],limitations=c['limitations'],evidence_sha256={p:sha(W/p) for p in paths},independent_reviewer='audit_unseen_props/forest',source_visible_holes_found=False))
 review=W/'review.md';review.write_text(review.read_text().replace('Independent review remains required before readiness.','Independent source/geometry review PASS; ready for renewed user geometry approval.'))
 print(W,'ready-for-user',model)
if __name__=='__main__':main()
