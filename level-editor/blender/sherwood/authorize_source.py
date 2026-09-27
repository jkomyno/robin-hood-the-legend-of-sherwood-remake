"""Bind independently verified and visually inspected source evidence for synthesis."""
import argparse
import json
from pathlib import Path
from source_authority import sha
from compile_source_masks import NATIVE,SOURCE

def main(root,masks):
    root,masks=map(lambda p:Path(p).resolve(),(root,masks))
    report=json.loads((root/'reprojection.json').read_text())
    verification=json.loads((root/'saved-worker-verification.json').read_text())
    inspection=json.loads((root/'inspection.json').read_text())
    coverage=json.loads((masks/'coverage.json').read_text())
    assignments=json.loads((masks/'assignment-verification.json').read_text())
    if (verification['status']!='PASS_REPROJECTION_CHECKS' or verification['worker_sha256']!=report['worker_sha256']
            or inspection['worker_sha256']!=report['worker_sha256'] or inspection.get('all_source_views_inspected') is not True
            or coverage['unresolved_source_nodes'] or assignments['status']!='PASS_DAY_ASSIGNMENTS'
            or assignments['coverage_sha256']!=sha(masks/'coverage.json')
            or sha(root/'source-only.blend')!=report['worker_sha256']):
        raise ValueError('Source verification or inspection is incomplete')
    if set(inspection['renders'])!={'source','east','west'}:raise ValueError('Missing actual source views')
    evidence=dict(coverage['evidence']);evidence.update(report['source_mask_evidence'])
    for name,row in inspection['renders'].items():
        if sha(row['path'])!=row['sha256']:raise ValueError('Inspected source view changed: '+name)
        evidence[row['path']]=row['sha256']
    recipe=json.loads((masks/'recipe.json').read_text());native={r['index']:r for r in json.loads(NATIVE.read_text())['masks']}
    for rule in recipe['assignments']+recipe.get('component_assignments',[]):
        for index,digest in rule['inspection'].get('mask_sha256',{}).items():
            path=(NATIVE.parent/native[int(index)]['png']).resolve()
            if sha(path)!=digest:raise ValueError('Native mask changed: '+str(path))
            evidence[str(path)]=digest
    for layer in report['canopy_sources'].values():
        for field in ('source','mask','sprite'):evidence[layer[field]]=layer[field+'_sha256']
    canopy=Path(report['canopy_manifest']).parent
    evidence.update(json.loads((canopy/'manifest.json').read_text())['evidence'])
    canopy_inspection=json.loads((canopy/'inspection.json').read_text())
    if canopy_inspection.get('status')!='INSPECTED' or canopy_inspection['source_contact_sha256']!=sha(canopy/'source-contact.png'):
        raise ValueError('Canopy source comparison has not been inspected')
    for path in [SOURCE,NATIVE,root/'saved-worker-verification.json',root/'inspection.json',masks/'coverage.json',masks/'assignment-verification.json',canopy/'manifest.json',canopy/'inspection.json',canopy/'source-contact.png']:
        evidence[str(path.resolve())]=sha(path)
    for path,digest in evidence.items():
        if sha(path)!=digest:raise ValueError('Changed source evidence: '+path)
    receipt=dict(status='PASS',worker_sha256=report['worker_sha256'],unresolved_source_nodes=0,unconstrained_receivers=0,
        accepted_texels=verification['accepted_texels'],independent_uv_samples=verification['independent_uv_samples'],
        source_pixel_scope='All accepted samples reproduce original RGB. Conservative source-domain gaps and inferred/hidden surfaces remain eligible for synthesis.',
        evidence=evidence)
    path=root/'source-ownership-validation.json';path.write_text(json.dumps(receipt,indent=2)+'\n')
    report['source_ownership_validation']=dict(path=str(path),sha256=sha(path));report['status']='SOURCE_REPROJECTION_VALIDATED';report['synthesis_ready']=True
    (root/'reprojection.json').write_text(json.dumps(report,indent=2)+'\n');print('Validated source worker:',report['worker_sha256'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--masks',required=True);a=p.parse_args();main(a.root,a.masks)
