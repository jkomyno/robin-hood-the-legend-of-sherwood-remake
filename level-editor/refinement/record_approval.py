"""Record an explicit user decision, bound to reviewed evidence hashes.

Legacy manifests retain the model/solid/textured approval interface. Exact
revision manifests append a geometry decision to decisions.json and archive all
reviewed evidence; the collector applies that decision on its next refresh.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil


def record_gallery_decision(gallery_path, records_path, asset_id, decision, exact_text,
                            *, scope='geometry-and-source-projection', projection_review=None):
    """Archive a decision against the exact model/packet displayed by a guarded gallery.

    The ownership report must contain model_sha256 and packet_hashes.modified.
    This separate decision log survives rebuilding the candidate manifest.
    """
    if decision not in ('approved', 'rejected', 'revision-requested') or not exact_text.strip():
        raise ValueError('An explicit user decision and its exact text are required')
    gallery_path, records_path = Path(gallery_path).resolve(), Path(records_path).resolve()
    item = None
    candidates = [gallery_path] + sorted((gallery_path / 'history').glob('*'),
                                         key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidates:
        if not (candidate / 'evidence.json').is_file():
            continue
        gallery = json.loads((candidate / 'evidence.json').read_text())
        item = next((row for row in gallery['items'] if row['id'] == asset_id), None)
        if item is not None:
            gallery_path = candidate
            break
    if item is None:
        raise ValueError('Asset is not in the displayed gallery: ' + asset_id)
    if Path(asset_id).name != asset_id or asset_id in ('.', '..'):
        raise ValueError('Unsafe asset ID')
    evidence = json.loads((gallery_path / item['reports']['ownership']['file']).read_text())
    record = dict(asset_id=asset_id, decision=decision, scope=scope, exact_text=exact_text,
                  model_sha256=evidence['model_sha256'],
                  modified_views_sha256=evidence['packet_hashes']['modified']['views.json'],
                  state_bundle_sha256=evidence.get('state_bundle_sha256'),
                  lighting_review_sha256=evidence.get('lighting_review_sha256'),
                  review_gallery=str(gallery_path),
                  recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    if projection_review is not None:
        record['projection_review'] = projection_review
    if decision == 'approved':
        workspace = Path(item['workspace'])
        model = workspace / 'model.blend'
        if hashlib.sha256(model.read_bytes()).hexdigest() != record['model_sha256']:
            raise ValueError('Current model differs from the displayed approval revision: ' + asset_id)
        for name, expected in evidence['packet_hashes']['modified'].items():
            packet_file = workspace / 'modified' / name
            if hashlib.sha256(packet_file.read_bytes()).hexdigest() != expected:
                raise ValueError('Current packet differs from the displayed approval revision: ' + asset_id)
        lighting_review = workspace / 'lighting-review'
        if evidence.get('lighting_review_sha256'):
            lighting_path = lighting_review / 'review.json'
            if hashlib.sha256(lighting_path.read_bytes()).hexdigest() != evidence['lighting_review_sha256']:
                raise ValueError('Lighting review differs from the displayed approval revision: ' + asset_id)
            lighting = json.loads(lighting_path.read_text())
            for packet in lighting['packets']:
                for key in ('solid', 'original_solid', 'source_blend', 'frame_manifest'):
                    if hashlib.sha256(Path(packet[key]).read_bytes()).hexdigest() != packet[key + '_sha256']:
                        raise ValueError('Lighting evidence differs from the displayed approval revision: ' + asset_id)
        archive = records_path.parent / 'approval-evidence' / asset_id / record['model_sha256'][:12]
        archive.mkdir(parents=True, exist_ok=True)
        for name in ('model.blend', 'candidate.json', 'validation.json', 'review.md', 'projection-correction.json'):
            source = workspace / name
            if source.exists() and not (archive / name).exists():
                shutil.copy2(source, archive / name)
        if not (archive / 'modified').exists():
            shutil.copytree(workspace / 'modified', archive / 'modified')
        if evidence.get('lighting_review_sha256') and not (archive / 'lighting-review').exists():
            shutil.copytree(lighting_review, archive / 'lighting-review')
        (archive / 'gallery-evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
        record['evidence_directory'] = str(archive)
        (archive / 'decision.json').write_text(json.dumps(record, indent=2) + '\n')
    data = json.loads(records_path.read_text()) if records_path.exists() else {'version': 1, 'approvals': []}
    if data.get('version') != 1:
        raise ValueError('Unsupported decision log version')
    previous = [row for row in data['approvals'] if row['asset_id'] == asset_id]
    data.setdefault('history', []).extend(previous)
    data['approvals'] = [row for row in data['approvals'] if row['asset_id'] != asset_id] + [record]
    temporary = records_path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    temporary.replace(records_path)
    return record
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from review_evidence import (sha, load_decisions, bind_decision,
                             archive_decisions, archive_reviewed_revision, geometry_basis, archive_geometry_basis)


def _source(path, value):
    source = Path(value)
    return source if source.is_absolute() else path.parent / source


def record(manifest_path, asset_ids, decision, *, result='approved',
           revision_sha256=None, decisions_path=None, geometry_only=False):
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
        known_ids = set(items) | {item['id'] for item in data.get('without_packets', [])}
        records = load_decisions(target, known_ids)
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
            if geometry_only:
                if result != 'approved' or item.get('worker_status', item['status']) != 'ready-for-user':
                    raise ValueError('Geometry-only approval requires a completed geometry review')
                record['geometry_basis'] = geometry_basis(item)
                record['technical_validation_at_approval'] = item['status']
            bind_decision(item, records + [record])
            pending.append((item, evidence, record))
        for item, evidence, record in pending:
            archive_reviewed_revision(path.parent, item, evidence)
            archive_geometry_basis(path.parent, item, record)
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
    parser.add_argument('--geometry-only', action='store_true', help='Record explicit geometry approval while separate material validation is pending')
    parser.add_argument('--result', choices=('approved', 'rejected'), default='approved')
    parser.add_argument('--revision-sha256', help='Expected exact revision for one asset')
    parser.add_argument('--decisions', type=Path, help='Exact-revision decision log; default beside manifest')
    args = parser.parse_args()
    record(args.manifest, args.asset_ids, args.decision, result=args.result,
           revision_sha256=args.revision_sha256, decisions_path=args.decisions, geometry_only=args.geometry_only)
