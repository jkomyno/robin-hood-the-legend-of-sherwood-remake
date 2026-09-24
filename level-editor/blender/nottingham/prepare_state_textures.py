"""Prepare the exact reviewed Nottingham state jobs without calling image APIs.

State workers retain separate input/preparation identities, while all states of
one building share the approved parent geometry identity used by the gallery.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
GEN = ROOT / 'level-editor/work/nottingham-refinement/texture-generation'
sys.path.insert(0, str(Path(__file__).parent))
from prepare_texture_adapter import normalize, read, sha
from prepare_ready_textures import verify_prepared

spec = importlib.util.spec_from_file_location('state_texture_preparation', ROOT / 'level-editor/refinement/prepare_texture_packet.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)


def selection(job):
    roles = job['roles']
    if roles == ['gallery-covered']:
        return 'covered'
    if roles == ['gallery-revealed']:
        return 'revealed'
    if len(roles) == 1 and roles[0].startswith('animation-'):
        return roles[0]
    raise ValueError('Ambiguous state job roles: ' + str(roles))


def batch(plan_path, output):
    plan = read(plan_path)
    rows = []
    for job in plan['jobs']:
        aid, state = job['asset_id'], selection(job)
        normalized = GEN / 'normalized-states' / aid / state
        experiment = GEN / 'state-experiments' / aid / state
        manifest = normalized / 'manifest.json'
        row = dict(asset_id=aid, state=state, experiment=str(experiment), normalized_manifest=str(manifest))
        try:
            for path_key, hash_key in [('source_blend', 'source_blend_sha256'), ('frame_manifest', 'frame_manifest_sha256')]:
                if sha(job[path_key]) != job[hash_key]:
                    raise ValueError('Planned state evidence changed: ' + path_key)
            if not manifest.exists():
                if normalized.exists():
                    raise ValueError('Incomplete normalized state contract exists; inspect before replacement')
                options = {'state': state}
                if job.get('state_binding'):
                    options['state_binding'] = Path(job['state_binding'])
                lighting = GEN / 'lighting' / aid / 'review.json'
                if lighting.exists() and read(lighting).get('status') == 'PASS':
                    options['generation_lighting'] = lighting
                normalize(aid, normalized, **options)
            item = read(manifest)['items'][0]
            if Path(item['preparation_model']).resolve() != Path(job['source_blend']).resolve():
                raise ValueError('Normalized model differs from planned state')
            frames = item['revision']['evidence']['frames']
            if frames['sha256'] != job['frame_manifest_sha256']:
                raise ValueError('Normalized cameras differ from planned state')
            original = item['approval_provenance']['source_approval']
            latest = [r for r in read(GEN.parent / 'approvals.json')['approvals'] if r['asset_id'] == aid]
            if len(latest) != 1 or any(latest[0].get(k) != original.get(k) for k in
                    ('decision', 'model_sha256', 'modified_views_sha256', 'state_bundle_sha256', 'lighting_review_sha256')):
                raise ValueError('Current approval differs from state preparation authorization')
            check = shared.prepare(manifest, aid, GEN / '.state-check-only' / aid / state, check_only=True)
            if not experiment.exists():
                shared.prepare(manifest, aid, experiment)
            approval = verify_prepared(experiment)
            if approval.get('preparation_revision') != item['revision']['sha256']:
                raise ValueError('Prepared state is not bound to its separate preparation revision')
            row.update(status='ready', geometry_revision=approval['geometry_revision'],
                       preparation_revision=approval['preparation_revision'], input_sha256=approval['input_sha256'],
                       editable_pixels=check['editable_pixels'], approval=str(experiment / 'approval.json'),
                       frames=str(experiment / 'views.json'))
        except Exception as error:
            message = str(error)
            pending = any(s in message for s in ('map-calibrated lighting evidence', 'Selected state has no approved lighting',
                'Generation lighting not inspected', 'Invalid generation lighting report', 'material audit missing',
                'Generation lighting lacks selected state'))
            row.update(status='waiting-technical' if pending else 'failed', reason=message)
        rows.append(row)
    for aid in {r['asset_id'] for r in rows}:
        ready = [r for r in rows if r['asset_id'] == aid and r['status'] == 'ready']
        if len({r['geometry_revision'] for r in ready}) > 1:
            raise ValueError('Gallery parent geometry revision differs across states: ' + aid)
        if len({r['preparation_revision'] for r in ready}) != len(ready):
            raise ValueError('Distinct states unexpectedly share preparation revision: ' + aid)
    report = {'version': 1, 'map': 'Nottingham', 'scope': '16 exact reviewed states; no image API requests',
              'plan': str(plan_path), 'plan_sha256': sha(plan_path), 'jobs': rows,
              'counts': {s: sum(r['status'] == s for r in rows) for s in sorted({r['status'] for r in rows})}}
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, indent=2) + '\n')
    temporary.replace(output)
    print(json.dumps(report['counts']), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=GEN / 'state-proof/state-job-plan.json')
    parser.add_argument('--output', type=Path, default=GEN / 'state-preparation-jobs.json')
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    while True:
        report = batch(args.plan.resolve(), args.output.resolve())
        if not args.watch or not any(r['status'] == 'waiting-technical' for r in report['jobs']):
            break
        time.sleep(30)
