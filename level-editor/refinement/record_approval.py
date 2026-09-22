"""Record an explicit user decision, bound to reviewed evidence hashes.

Legacy manifests retain the model/solid/textured approval interface. Exact
revision manifests append a geometry decision to decisions.json and archive all
reviewed evidence; the collector applies that decision on its next refresh.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from review_evidence import (sha, load_decisions, bind_decision,
                             archive_decisions, archive_reviewed_revision)


def _source(path, value):
    source = Path(value)
    return source if source.is_absolute() else path.parent / source


def record(manifest_path, asset_ids, decision, *, result='approved',
           revision_sha256=None, decisions_path=None):
    path = Path(manifest_path).resolve(strict=True)
    if not isinstance(decision, str) or not decision.strip():
        raise ValueError('The exact explicit user decision is required')
    if result not in ('approved', 'rejected'):
        raise ValueError('Expected approved or rejected decision')
    data = json.loads(path.read_text())
    items = {item['id']: item for item in data['items']}
    missing = set(asset_ids) - items.keys()
    if missing:
        raise ValueError(f'Unknown assets: {sorted(missing)}')
    selected = [items[asset_id] for asset_id in asset_ids]
    revision_items = [item for item in selected if 'revision' in item]
    if revision_items:
        if len(revision_items) != len(selected):
            raise ValueError('Cannot mix legacy and exact-revision decisions')
        if revision_sha256 is not None and len(selected) != 1:
            raise ValueError('An expected revision hash requires exactly one asset')
        target = Path(decisions_path).resolve() if decisions_path else path.parent / 'decisions.json'
        records = load_decisions(target, set(items))
        pending = []
        for item in selected:
            revision = item['revision']
            if revision_sha256 is not None and revision['sha256'] != revision_sha256:
                raise ValueError('Expected revision differs from current manifest')
            identity = {'asset_id': item['id'], 'model_sha256': revision['model_sha256'],
                        'evidence': {key: entry['sha256'] for key, entry in revision['evidence'].items()}}
            actual = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            if actual != revision['sha256']:
                raise ValueError('Revision identity does not match its evidence')
            model = _source(path, item['model']) if item.get('model') else _source(path, item['workspace']) / 'model.blend'
            if sha(model) != revision['model_sha256']:
                raise ValueError('Model changed since review')
            evidence = {key: _source(path, entry['path']) for key, entry in revision['evidence'].items()}
            for key, source in evidence.items():
                if sha(source) != revision['evidence'][key]['sha256']:
                    raise ValueError('Review evidence changed: ' + key)
            record = {'asset_id': item['id'], 'scope': 'geometry', 'decision': result,
                      'revision_sha256': revision['sha256'], 'exact_user_text': decision}
            bind_decision(item, records + [record])
            pending.append((item, evidence, record))
        for item, evidence, record in pending:
            archive_reviewed_revision(path.parent, item, evidence)
        records.extend(record for _, _, record in pending)
        archive_decisions(path.parent, records)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({'version': 1, 'decisions': records}, indent=2)+'\n')
        return {'decisions': str(target), 'assets': list(asset_ids), 'scope': 'geometry'}
    if revision_sha256 is not None or decisions_path is not None or result != 'approved':
        raise ValueError('Exact revision options require an exact revision manifest')
    # Keep the established legacy record fields and model/solid/textured hashes.
    for item in selected:
        hashes = {key: sha(_source(path, item[key])) for key in ('model', 'solid', 'textured')}
        item.update(status='approved', user_approval='Approved: ' + decision,
                    approved_sha256=hashes,
                    ai_texture='Authorized by recorded user decision; generation pending')
    path.write_text(json.dumps(data, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    parser.add_argument('asset_ids', nargs='+')
    parser.add_argument('--decision', required=True, help='Exact actual user decision and scope; never invent approval')
    parser.add_argument('--result', choices=('approved', 'rejected'), default='approved')
    parser.add_argument('--revision-sha256', help='Expected exact revision for one asset')
    parser.add_argument('--decisions', type=Path, help='Exact-revision decision log; default beside manifest')
    args = parser.parse_args()
    record(args.manifest, args.asset_ids, args.decision, result=args.result,
           revision_sha256=args.revision_sha256, decisions_path=args.decisions)
