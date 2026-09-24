"""Report Nottingham texture work from current packets, without counting retries twice."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text()) if path.is_file() else None


def packet(experiment):
    experiment = Path(experiment)
    generation = read(experiment / 'generation-short-no-mask-with-lighting-openrouter/generation.json')
    review = read(experiment / 'generation-review.json')
    texture = read(experiment / 'texture-review.json')
    return {
        'experiment': str(experiment),
        'generated': bool(generation and generation.get('status') == 200),
        'protected_pixel_changes': generation.get('changedProtected') if generation else None,
        'generation_review': review.get('status') if review else 'pending',
        'texture_review': texture.get('status') if texture else 'pending',
    }


def report(root):
    root = root.resolve()
    generation_root = root / 'texture-generation'
    preparation = read(generation_root / 'preparation-jobs.json')
    states = read(generation_root / 'state-preparation-jobs.json')
    if not preparation or not states:
        raise ValueError('Both static and state preparation ledgers are required')
    assets = []
    for item in preparation['assets']:
        asset_id = item['asset_id']
        if item.get('lane') == 'terrain':
            jobs = [packet(generation_root / 'nottingham-terrain-ground-uv-atlas-v1')]
        elif item['status'] == 'separate-lane':
            jobs = [dict(state=state['state'], **packet(state['experiment']))
                    for state in states['jobs'] if state['asset_id'] == asset_id]
            if not jobs:
                raise ValueError('Missing state jobs: ' + asset_id)
        else:
            jobs = [packet(item['experiment'])]
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
