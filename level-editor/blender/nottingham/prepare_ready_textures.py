"""Resume preparation of technically ready, explicitly approved static textures.

Never invokes an image service. Failed/incomplete preparation directories are
retained; stale approval or altered evidence stops that asset instead of silently
rebuilding a different revision.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'level-editor/work/nottingham-refinement'
GEN=WORK/'texture-generation'
sys.path.insert(0,str(Path(__file__).parent))
from prepare_texture_adapter import normalize, sha, read
spec=importlib.util.spec_from_file_location('shared_texture_preparation',ROOT/'level-editor/refinement/prepare_texture_packet.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)

STATEFUL={'nottingham-church','nottingham-upper-prison','nottingham-southwest-prison',
          'nottingham-castle-main-hall','nottingham-castle-gate-arch','nottingham-castle-gate-east-tower'}
PILOTS={'nottingham-castle-gate-west-tower':{
    'experiment':GEN/'pilot-west-tower',
    'manifest':GEN/'normalized-pilot-west-tower-v3/manifest.json'}}


def classify(error):
    message=str(error)
    holds=('map-calibrated lighting evidence','Generation lighting not inspected',
           'Invalid generation lighting report','material audit missing','Sunburst custom-size constraints')
    return 'waiting-technical' if any(s in message for s in holds) else 'failed'


def verify_prepared(directory):
    report=read(directory/'preparation.json')
    for name,digest in report['files'].items():
        if sha(directory/name)!=digest:raise ValueError('Prepared artifact changed: '+name)
    approval=read(directory/'approval.json')
    if sha(directory/'input.png')!=approval['input_sha256']:raise ValueError('Prepared input changed')
    return approval


def batch(output=GEN/'preparation-jobs.json'):
    gallery=read(WORK/'gallery-candidates.json')
    rows=[]
    for item in gallery['items']:
        if 'parent_asset_id' in item:continue
        aid=item['id'];workspace=Path(item['workspace'])
        row={'asset_id':aid,'workspace':str(workspace),'state':'covered'}
        if aid in STATEFUL or aid=='nottingham-terrain-ground':
            row.update(status='separate-lane',lane='stateful' if aid in STATEFUL else 'terrain');rows.append(row);continue
        normalized=GEN/'normalized'/aid
        experiment=GEN/'experiments'/aid
        manifest=normalized/'manifest.json'
        if aid in PILOTS:
            manifest=PILOTS[aid]['manifest'];experiment=PILOTS[aid]['experiment']
        row.update(normalized_manifest=str(manifest),experiment=str(experiment))
        try:
            if not manifest.exists():
                lighting=GEN/'lighting'/aid/'review.json'
                if lighting.exists() and read(lighting).get('status')=='PASS':
                    options={'generation_lighting':lighting}
                else:
                    approved_light=workspace/'lighting-review/review.json'
                    if not approved_light.exists() or read(approved_light).get('status')!='PASS':
                        row.update(status='waiting-technical',reason='Map lighting still pending');rows.append(row);continue
                    options={}
                if normalized.exists():
                    raise ValueError('Incomplete normalized contract exists; inspect before replacing')
                normalize(aid,normalized,**options)
            normalized_item=read(manifest)['items'][0]
            original=normalized_item['approval_provenance']['source_approval']
            latest=[a for a in read(WORK/'approvals.json')['approvals'] if a['asset_id']==aid]
            if len(latest)!=1 or any(latest[0].get(k)!=original.get(k) for k in
                    ('decision','model_sha256','modified_views_sha256','state_bundle_sha256','lighting_review_sha256')):
                raise ValueError('Current user decision differs from preparation authorization')
            check=shared.prepare(manifest,aid,GEN/'.check-only'/aid,check_only=True)
            # Check-only does not write but normally rejects an existing output.
            # Validate existing work using a fresh non-created check target.
            if experiment.exists() and not (experiment/'preparation.json').exists():
                archive=GEN/'incomplete-preparations'/f'{aid}-{time.time_ns()}'
                archive.parent.mkdir(parents=True,exist_ok=True)
                experiment.rename(archive)
                row['retained_incomplete_preparation']=str(archive)
            if experiment.exists():
                approval=verify_prepared(experiment)
            else:
                shared.prepare(manifest,aid,experiment)
                approval=verify_prepared(experiment)
            row.update(status='ready',editable_pixels=check['editable_pixels'],
                       geometry_revision=approval['geometry_revision'],input_sha256=approval['input_sha256'],
                       approval=str(experiment/'approval.json'),frames=str(experiment/'views.json'))
        except Exception as error:
            row.update(status=classify(error),reason=str(error))
        rows.append(row)
    counts={state:sum(r['status']==state for r in rows) for state in sorted({r['status'] for r in rows})}
    report={'version':1,'map':'Nottingham','scope':'Static covered preparation only; no generation requests',
            'counts':counts,'assets':rows}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix('.tmp');temp.write_text(json.dumps(report,indent=2)+'\n');temp.replace(output)
    print(json.dumps(counts),flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=GEN/'preparation-jobs.json')
    parser.add_argument('--watch',action='store_true');args=parser.parse_args()
    while True:
        result=batch(args.output)
        if not args.watch or not any(r['status']=='waiting-technical' for r in result['assets']):break
        time.sleep(30)
