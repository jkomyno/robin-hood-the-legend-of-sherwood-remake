"""Report Nottingham texture work from current packets, without counting retries twice."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path


def read(path):
    return json.loads(path.read_text()) if path.is_file() else None


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validated_resolutions(path):
    """Resolve historical holds only against the unchanged final evidence."""
    sidecar = read(path)
    if sidecar is None:
        return {}
    result = {}
    for item in sidecar['resolutions']:
        generation = Path(item['original_generation_review'])
        experiment = generation.parent.resolve()
        if experiment in result:
            raise ValueError('Duplicate work resolution: ' + str(experiment))
        expected = item['original_generation_review_sha256']
        if expected is None:
            if generation.exists():
                raise ValueError('Historical generation review appeared')
        elif not generation.is_file() or digest(generation) != expected:
            raise ValueError('Historical generation review changed')
        evidence = item['resolution_evidence']
        review = experiment / 'texture-review.json'
        texture = read(review)
        if not texture or texture.get('status') != 'ready-for-user':
            raise ValueError('Resolved texture is no longer ready')
        bake = experiment / texture['bake']
        required = {review, bake / 'validation.json', bake / 'worker.blend'}
        if {Path(p).resolve() for p in evidence} != {p.resolve() for p in required}:
            raise ValueError('Resolution does not bind the current bake')
        for name, expected_digest in evidence.items():
            with Path(name).open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != expected_digest:
                    raise ValueError('Stale work resolution evidence: ' + name)
        if item['current_work_status'] != 'resolved-by-reviewed-projection':
            raise ValueError('Unsupported work resolution')
        result[experiment] = {'status': item['current_work_status'],
                              'sidecar': str(path), 'evidence': evidence}
    return result


def packet(experiment, resolutions=None):
    experiment = Path(experiment)
    generation = read(experiment / 'generation-short-no-mask-with-lighting-openrouter/generation.json')
    review = read(experiment / 'generation-review.json')
    texture = read(experiment / 'texture-review.json')
    resolution = (resolutions or {}).get(experiment.resolve())
    return {
        'experiment': str(experiment),
        'generated': bool(generation and generation.get('status') == 200),
        'protected_pixel_changes': generation.get('changedProtected') if generation else None,
        'generation_review': review.get('status') if review else 'pending',
        'texture_review': texture.get('status') if texture else 'pending',
        'current_work_status': resolution['status'] if resolution else (
            texture.get('status', 'pending') if texture else 'pending'),
        'historical_generation_hold_resolved': bool(resolution),
        'work_resolution': resolution,
        'user_texture_approval': texture.get('user_approval', 'pending') if texture else 'pending',
    }


def report(root):
    root = root.resolve()
    generation_root = root / 'texture-generation'
    resolutions = validated_resolutions(generation_root / 'work-item-resolutions.json')
    preparation = read(generation_root / 'preparation-jobs.json')
    states = read(generation_root / 'state-preparation-jobs.json')
    if not preparation or not states:
        raise ValueError('Both static and state preparation ledgers are required')
    assets = []
    for item in preparation['assets']:
        asset_id = item['asset_id']
        if item.get('lane') == 'terrain':
            jobs = [packet(generation_root / 'nottingham-terrain-ground-uv-atlas-v1', resolutions)]
        elif item['status'] == 'separate-lane':
            jobs = [dict(state=state['state'], **packet(state['experiment'], resolutions))
                    for state in states['jobs'] if state['asset_id'] == asset_id]
            if not jobs:
                raise ValueError('Missing state jobs: ' + asset_id)
        else:
            jobs = [packet(item['experiment'], resolutions)]
        assets.append({'asset_id': asset_id, 'jobs': jobs})
    ids = [item['asset_id'] for item in assets]
    if len(ids) != 126 or len(set(ids)) != len(ids):
        raise ValueError('Expected 126 unique approved asset groups')
    jobs = [job for asset in assets for job in asset['jobs']]
    gallery = read(root / 'texture-review/texture-candidates.json') or {'items': []}
    gallery_ids = [item['id'] for item in gallery['items']]
    if len(gallery_ids) != len(set(gallery_ids)) or set(gallery_ids) - set(ids):
        raise ValueError('Unexpected or duplicate texture gallery asset IDs')
    return {
        'updated_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Current generation packets only; retries and archived outputs are excluded.',
        'asset_groups': len(assets), 'texture_jobs': len(jobs),
        'generated_jobs': sum(job['generated'] for job in jobs),
        'protected_pixel_failures': sum(job['generated'] and job['protected_pixel_changes'] != 0 for job in jobs),
        'generation_review': dict(Counter(job['generation_review'] for job in jobs)),
        'generation_review_semantics': 'Historical raw-output verdicts; resolved holds are reported separately in current_work_status.',
        'current_work_status': dict(Counter(job['current_work_status'] for job in jobs)),
        'resolved_generation_holds': sum(job['historical_generation_hold_resolved'] for job in jobs),
        'texture_review': dict(Counter(job['texture_review'] for job in jobs)),
        'gallery_candidates': len(gallery_ids),
        'missing_gallery_assets': sorted(set(ids) - set(gallery_ids)),
        'assets': assets,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = report(args.root)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items()
                      if key not in {'assets', 'missing_gallery_assets'}}, indent=2))
