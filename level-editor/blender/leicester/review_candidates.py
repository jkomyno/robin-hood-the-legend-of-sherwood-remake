"""Collect Leicester worker handoffs without promoting incomplete work to approval.

Each completed worker writes handoff.json with status, notes, recipe, ownership,
and optionally revealed_solid/revealed_textured/revealed_context paths. Paths in
handoff.json are relative to the worker directory. Unprepared jobs remain listed
in progress.json, never masquerade as completed gallery candidates.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_review_gallery import build


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(catalog_path, assets, output):
    catalog = json.loads(catalog_path.read_text())
    if catalog['map'] != 'Leicester':
        raise ValueError('Expected Leicester catalog')
    output.mkdir(parents=True, exist_ok=True)
    items, progress = [], []
    for group in catalog['groups']:
        workspace = assets / group['id']
        handoff_path = workspace / 'handoff.json'
        entry = {'id': group['id'], 'name': group['name'], 'workspace': str(workspace)}
        if not handoff_path.exists():
            progress.append({**entry, 'status': 'refinement-in-progress' if workspace.exists() else 'not-prepared'})
            continue
        handoff = json.loads(handoff_path.read_text())
        status = handoff['status']
        if status not in ('ready-for-user', 'fix-needed', 'validation-pending'):
            raise ValueError(f'Unsupported handoff status for {group["id"]}: {status}')
        item = {**entry, 'status': status, 'notes': handoff['notes'], 'user_approval': 'pending'}
        for key, relative in {
            'solid': 'modified/solid.png', 'textured': 'modified/textured.png',
            'context': 'input/context.png', 'validation': 'validation.json', 'review': 'review.md',
            'ownership': handoff['ownership'],
        }.items():
            item[key] = str((workspace / relative).resolve(strict=True))
        for key in ('revealed_solid', 'revealed_textured', 'revealed_context'):
            if handoff.get(key):
                item[key] = str((workspace / handoff[key]).resolve(strict=True))
        validation = json.loads(Path(item['validation']).read_text())
        if status == 'ready-for-user':
            if validation.get('status') != 'PASS':
                raise ValueError(f'Failed validation cannot be ready: {group["id"]}')
            if not handoff.get('all_eight_views_inspected'):
                raise ValueError(f'Missing visual review: {group["id"]}')
            if handoff.get('has_revealed_state') and not all(key in item for key in
                    ('revealed_solid', 'revealed_textured', 'revealed_context')):
                raise ValueError(f'Missing revealed-state evidence: {group["id"]}')
        recipe = (workspace / handoff['recipe']).resolve(strict=True)
        item['revision'] = {'model_sha256': sha(workspace / 'model.blend'),
                            'recipe': str(recipe), 'recipe_sha256': sha(recipe),
                            'handoff_sha256': sha(handoff_path)}
        items.append(item)
        progress.append({**entry, 'status': status})
    manifest = output / 'review-candidates.json'
    manifest.write_text(json.dumps({'map': 'Leicester', 'items': items}, indent=2) + '\n')
    (output / 'progress.json').write_text(json.dumps({'map': 'Leicester', 'groups': progress,
        'total': len(progress), 'packets': len(items), 'ready': sum(i['status'] == 'ready-for-user' for i in items),
        'geometry_approval': 'pending', 'texture_generation': 'not-started',
        'publication': 'not-started'}, indent=2) + '\n')
    if items:
        build(manifest, output / 'gallery', pending_only=True)
    return {'manifest': str(manifest), 'groups': len(progress), 'packets': len(items)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalog', type=Path)
    parser.add_argument('assets', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(collect(args.catalog.resolve(), args.assets.resolve(), args.output.resolve())))
