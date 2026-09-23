"""Record an inspected projection-only revision without claiming new geometry."""
import argparse,hashlib,json
from pathlib import Path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def finalize(workspace):
 w=workspace.resolve();candidate=json.loads((w/'candidate.json').read_text());proof=json.loads((w/'source-visibility-correction.json').read_text())
 assert proof['status']=='PASS' and proof['geometry_preserved'] is True
 assert candidate['model_sha256']==sha(w/'model.blend')
 assert candidate['modified_views_sha256']==sha(w/'modified/views.json')
 assert candidate['inspected_views']==list(range(8))
 assert all(sha(w/'input/views'/f'view-{i}-solid.png')==sha(w/'modified/views'/f'view-{i}-solid.png') for i in range(8))
 assert json.loads((w/'validation.json').read_text())['status']=='PASS'
 prior=Path(proof['previous_workspace'])
 reason=f'Preserved the previously refined geometry from {prior.name} ({prior.parent.parent.name}) in a fresh source-projection baseline. This revision changes source visibility constraints only; the complete geometry preservation proof and all eight identical solid views establish no new mesh edits.'
 candidate['geometry_refined']=False;candidate['geometry_reviewed']=True;candidate['no_change_reason']=reason
 (w/'candidate.json').write_text(json.dumps(candidate,indent=2)+'\n')
 review=w/'review.md';text=review.read_text();heading='\n\nProjection-only revision audit: '
 if heading not in text:review.write_text(text+heading+reason+'\n')
 return dict(asset_id=candidate['asset_id'],model_sha256=candidate['model_sha256'],modified_views_sha256=candidate['modified_views_sha256'],geometry_proof_sha256=sha(w/'source-visibility-correction.json'),status='PASS',geometry_refined=False,reason=reason)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace',type=Path);a=p.parse_args();print(json.dumps(finalize(a.workspace),indent=2))
