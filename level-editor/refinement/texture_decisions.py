"""Record explicit texture decisions against displayed and baked evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil


IMAGE_FIELDS = ('solid', 'textured', 'source_comparison',
                'source_comparison_secondary', 'source_trace')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evidence(item):
    paths = {key: Path(item[key]) for key in (*IMAGE_FIELDS, 'validation', 'review')}
    paths['model'] = paths['validation'].parent / 'worker.blend'
    hashes = {key: sha(path) for key, path in paths.items()}
    review = json.loads(paths['review'].read_text())
    if hashes['model'] != review['baked_model_sha256'] or hashes['textured'] != review['actual_sheet_sha256']:
        raise ValueError('Baked texture evidence changed: ' + item['id'])
    return paths, hashes


def bind(item, records):
    _, hashes = evidence(item)
    matches = [record for record in records if record['asset_id'] == item['id']
               and record.get('scope') == 'texture']
    if matches and matches[-1].get('evidence_sha256') == hashes:
        item['user_approval'] = matches[-1]['decision']
        item['texture_decision'] = matches[-1]


def record(gallery, decisions, text):
    gallery, decisions = Path(gallery).resolve(), Path(decisions).resolve()
    displayed = json.loads((gallery / 'evidence.json').read_text())
    items = {item['id']: item for item in displayed['items']}
    pending = []
    seen = set()
    for line in text.splitlines():
        if not line.strip() or ' model review - http' in line:
            continue
        match = re.fullmatch(r'(\S+): (approved|needs refinement)(.*?) \[review ([0-9a-f]{16})\]', line)
        if not match:
            raise ValueError('Unrecognized texture decision: ' + line)
        asset_id, decision, _, revision = match.groups()
        if asset_id in seen:
            raise ValueError('Duplicate texture decision: ' + asset_id)
        seen.add(asset_id)
        item = items[asset_id]
        if item['review_revision'][:16] != revision:
            raise ValueError('Displayed texture revision differs: ' + asset_id)
        paths, hashes = evidence(item)
        for key in (*IMAGE_FIELDS, 'validation', 'review'):
            entry = item['images' if key in IMAGE_FIELDS else 'reports'][key]
            if hashes[key] != entry['sha256'] or sha(gallery / entry['file']) != entry['sha256']:
                raise ValueError('Displayed texture evidence changed: ' + asset_id + '/' + key)
        pending.append((paths, {
            'asset_id': asset_id, 'scope': 'texture',
            'decision': 'approved' if decision == 'approved' else 'rejected',
            'review_revision': item['review_revision'], 'exact_user_text': line,
            'evidence_sha256': hashes,
            'evidence_paths': {key: str(path) for key, path in paths.items()},
        }))
    if not pending:
        raise ValueError('No texture decisions supplied')
    records = json.loads(decisions.read_text())['decisions'] if decisions.exists() else []
    for paths, decision in pending:
        archive = decisions.parent / 'approved-evidence' / decision['asset_id'] / decision['review_revision']
        archive.mkdir(parents=True, exist_ok=True)
        for key, source in paths.items():
            target = archive / (key + source.suffix)
            if target.exists():
                if sha(target) != decision['evidence_sha256'][key]:
                    raise ValueError('Archived texture evidence changed: ' + str(target))
            else:
                shutil.copy2(source, target)
        decision['archive'] = str(archive)
        (archive / 'decision.json').write_text(json.dumps(decision, indent=2) + '\n')
        if decision not in records:
            records.append(decision)
    decisions.parent.mkdir(parents=True, exist_ok=True)
    temporary = decisions.with_suffix('.json.tmp')
    temporary.write_text(json.dumps({'version': 1, 'decisions': records}, indent=2) + '\n')
    temporary.replace(decisions)
    return {'recorded': len(pending), 'decisions': str(decisions)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gallery', type=Path)
    parser.add_argument('decisions', type=Path)
    parser.add_argument('feedback', type=Path)
    args = parser.parse_args()
    print(json.dumps(record(args.gallery, args.decisions, args.feedback.read_text())))
