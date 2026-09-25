"""Bind an explicit bulk publication instruction without changing review decisions."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from texture_decisions import evidence, fields, sha


def prepare(gallery, output, exact_user_text):
    gallery, output = Path(gallery).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    if not exact_user_text.strip():
        raise ValueError('Explicit publication instruction required')
    snapshot = gallery / 'evidence.json'
    items = json.loads(snapshot.read_text())['items']
    if not items or len({item['id'] for item in items}) != len(items):
        raise ValueError('Expected a nonempty unique ready inventory')
    records = []
    for item in items:
        if item.get('status') != 'ready-for-user':
            raise ValueError('Publication inventory contains a held asset: ' + item['id'])
        paths, hashes = evidence(item)
        image_fields, report_fields = fields(item)
        for key in (*image_fields, *report_fields):
            displayed = item['images' if key in image_fields else 'reports'][key]
            if hashes[key] != displayed['sha256'] or sha(gallery / displayed['file']) != hashes[key]:
                raise ValueError('Displayed publication evidence changed: ' + item['id'] + '/' + key)
        records.append(dict(
            asset_id=item['id'], scope='texture', decision='approved',
            authorization_kind='publish-ready-assets', individual_visual_review=False,
            exact_user_text=exact_user_text, review_revision=item['review_revision'],
            evidence_paths={key: str(path.resolve()) for key, path in paths.items()},
            evidence_sha256=hashes, texture_states=item.get('texture_states', [])))
    result = dict(version=1,
                  scope='Bulk publication authorization; individual gallery review decisions remain unchanged.',
                  authorized_at=datetime.now(timezone.utc).isoformat(),
                  snapshot_path=str(snapshot), snapshot_sha256=sha(snapshot), decisions=records)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gallery', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--instruction-file', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.gallery, args.output, args.instruction_file.read_text())
    print(json.dumps({'assets': len(result['decisions']), 'output': str(args.output)}))
