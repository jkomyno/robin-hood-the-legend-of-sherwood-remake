"""Publish a review packet only after independent visual and numeric checks."""
import json
from pathlib import Path
from correct_prison_ramp_projection import sha,write
ROOT=Path(__file__).resolve().parents[3];w=ROOT/'level-editor/work/nottingham-refinement/round-26/assets/nottingham-castle-west-conical-tower'
def main():
 proof=json.loads((w/'projection-correction.json').read_text());review=json.loads((w/'inspection/independent-review.json').read_text());rgb=json.loads((w/'known-rgb-validation.json').read_text());stored=json.loads((w/'inspection/stored-materials-export/audit.json').read_text());valid=json.loads((w/'validation.json').read_text())
 assert review['status']=='PASS' and review['model_sha256']==sha(w/'model.blend') and review['inspected_views']==list(range(8))
 assert json.loads((w/'outside-projection-validation.json').read_text())['status']=='PASS'
 assert rgb['status']==valid['status']=='PASS' and stored['status']=='STRUCTURAL-PASS' and not stored['problems']
 assert proof['geometry_before_sha256']==proof['geometry_after_sha256'] and proof['model_sha256']==sha(w/'model.blend')
 proof.update(status='PASS',inspected_views=list(range(8)),independent_review='inspection/independent-review.json');write(w/'projection-correction.json',proof)
 c=json.loads((w/'candidate.json').read_text());c.update(status='ready-for-user',geometry_reviewed=True,inspected_views=list(range(8)),stored_material_evidence='inspection/stored-materials-export/audit.json',user_approval='geometry approved; corrected projection awaiting review');write(w/'candidate.json',c)
 (w/'review.md').write_text('# Castle west conical tower\n\nThe upper-only mask cut off visible lower masonry. The corrected full native tower silhouette excludes the foreground stair and turret, with complete scene visibility retained. Geometry is exactly unchanged from the approved model. All eight projected and actual material views were independently inspected. Reverse and concealed faces remain neutral.\n\nCorrected projection awaiting user review. No generated texture.\n')
if __name__=='__main__':main()
