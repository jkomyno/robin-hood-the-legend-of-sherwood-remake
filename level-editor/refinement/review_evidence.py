"""Shared exact-revision decisions, immutable archives and actual-material guards."""
import hashlib
import json
import re
import shutil
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()



def load_decisions(path, known_ids):
    """Read explicit geometry decisions; absence never implies approval."""
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if data.get('version') != 1 or not isinstance(data.get('decisions'), list):
        raise ValueError('Expected decisions JSON version 1 with a decisions list')
    for record in data['decisions']:
        if record.get('asset_id') not in known_ids:
            raise ValueError('Decision references an unknown asset')
        if record.get('scope') != 'geometry' or record.get('decision') not in ('approved', 'rejected'):
            raise ValueError('An explicit approved/rejected geometry decision is required')
        if not isinstance(record.get('exact_user_text'), str) or not record['exact_user_text'].strip():
            raise ValueError('Decision requires the exact user approval/rejection text')
        if not re.fullmatch(r'[0-9a-f]{64}', record.get('revision_sha256', '')):
            raise ValueError('Decision requires the exact candidate revision SHA256')
    return data['decisions']


def geometry_basis(item):
    """Freeze reviewed geometry/source evidence independently of later audit reports."""
    workspace = Path(item['workspace'])
    files = {}
    for key in ('solid', 'textured', 'context', 'ownership', 'recipe',
                'revealed_solid', 'revealed_textured', 'revealed_context'):
        entry = item['revision']['evidence'].get(key)
        if entry:
            files['review/' + key] = {'path': entry['path'], 'sha256': sha(Path(entry['path']))}
    for folder in ('input', 'reference', 'modified'):
        for path in sorted((workspace / folder).rglob('*')):
            if path.is_file():
                files[str(path.relative_to(workspace))] = {'path': str(path), 'sha256': sha(path)}
    for name in ('workspace.json', 'source-masks.json', 'projection-layers.json'):
        path = workspace / name
        if path.is_file():
            files[name] = {'path': str(path), 'sha256': sha(path)}
    model_hash = sha(workspace / 'model.blend')
    identity = {'asset_id': item['id'], 'model_sha256': model_hash,
                'files': {key: entry['sha256'] for key, entry in files.items()}}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'version': 1, 'sha256': digest, 'model_sha256': model_hash, 'files': files}


def archive_geometry_basis(output, item, record):
    basis = record.get('geometry_basis')
    if not basis:
        return
    archive = output / 'reviewed-revisions' / item['id'] / record['revision_sha256'] / 'geometry-basis'
    for index, (key, entry) in enumerate(sorted(basis['files'].items())):
        source = Path(entry['path'])
        target = archive / (str(index) + source.suffix)
        target.parent.mkdir(parents=True, exist_ok=True)
        if sha(source) != entry['sha256']:
            raise ValueError('Geometry approval evidence changed during archive: ' + key)
        if target.exists() and sha(target) != entry['sha256']:
            raise ValueError('Archived geometry basis was modified')
        if not target.exists():
            shutil.copyfile(source, target)
    model = Path(item['workspace']) / 'model.blend'
    target = archive / 'model.blend'
    if sha(model) != basis['model_sha256']:
        raise ValueError('Approved model changed during archive')
    if target.exists() and sha(target) != basis['model_sha256']:
        raise ValueError('Archived approved model was modified')
    if not target.exists():
        shutil.copyfile(model, target)
    (archive / 'basis.json').write_text(json.dumps(basis, indent=2) + '\n')


def bind_decision(item, records):
    decisions = [r for r in records if r['asset_id'] == item['id']]
    # The last explicit decision for this asset is authoritative. A decision on
    # an older revision cannot approve newer evidence, even if its model matches.
    record = decisions[-1] if decisions else None
    item['user_approval'] = 'pending'
    if record is None:
        item['decision_state'] = 'missing'
    elif record.get('geometry_basis') and record['geometry_basis']['sha256'] != geometry_basis(item)['sha256']:
        item['decision_state'] = 'stale'
        item['stale_decision'] = record
    elif not record.get('geometry_basis') and record['revision_sha256'] != item['revision']['sha256']:
        item['decision_state'] = 'stale'
        item['stale_decision'] = record
    elif record['decision'] == 'approved' and item['status'] != 'ready-for-user' and not record.get('geometry_basis'):
        raise ValueError('Cannot approve an incomplete candidate: '+item['id'])
    else:
        item['decision_state'] = 'current'
        item['user_approval'] = record['decision']
        item['user_decision'] = record
        if record['decision'] == 'rejected':
            item['status'] = 'rejected'
    item['technical_eligible'] = item['status'] == 'ready-for-user' and item.get('stored_material_validation', 'PASS') == 'PASS'
    item['generation_eligible'] = item['user_approval'] == 'approved' and item['technical_eligible']
    item['publication_eligible'] = item['generation_eligible']
    return item


def archive_decisions(output, records):
    directory = output / 'decision-history'
    for record in records:
        content = json.dumps(record, sort_keys=True, indent=2)+'\n'
        digest = hashlib.sha256(content.encode()).hexdigest()
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / (digest+'.json')
        if target.exists() and target.read_text() != content:
            raise ValueError('Decision archive differs from its content hash')
        target.write_text(content)


def archive_reviewed_revision(output, item, evidence):
    """Retain actual reviewed files even when the pending gallery hides them."""
    if item['decision_state'] != 'current':
        return
    archive = output / 'reviewed-revisions' / item['id'] / item['revision']['sha256']
    archive.mkdir(parents=True, exist_ok=True)
    for key, source in evidence.items():
        target = archive / (key+source.suffix)
        digest = item['revision']['evidence'][key]['sha256']
        if target.exists() and sha(target) != digest:
            raise ValueError('Archived review evidence was modified: '+str(target))
        if not target.exists():
            shutil.copyfile(source, target)
        if sha(target) != digest:
            raise ValueError('Evidence changed while archiving: '+str(source))
    # Content-addressed decision records remain separate from this immutable
    # revision identity, so later rejection does not rewrite prior approval.
    (archive / 'revision.json').write_text(json.dumps(item['revision'], indent=2)+'\n')


def material_evidence(workspace, audit_path, frame_path, model_hash, prefix):
    """Validate actual bytes; retain available evidence even when validation fails."""
    evidence, errors = {}, []
    if not audit_path.is_file():
        return evidence, ['missing material audit'], None
    evidence[prefix + '_audit'] = audit_path
    try:
        audit = json.loads(audit_path.read_text())
    except (ValueError, OSError):
        return evidence, ['invalid material audit JSON'], None
    if not isinstance(audit, dict):
        return evidence, ['invalid material audit object'], None
    if audit.get('problems'):
        errors.append('material audit lists structural problems')
    visual = audit.get('visual_review')
    visual_status = visual.get('status') if isinstance(visual, dict) else visual
    if audit.get('status') not in ('PASS', 'STRUCTURAL-PASS') or visual_status != 'PASS':
        errors.append('material structural or visual review is pending/failed')
    if audit.get('model_sha256') != model_hash:
        errors.append('material model hash is stale')
    if not frame_path.is_file() or audit.get('frame_manifest_sha256') != sha(frame_path):
        errors.append('material frame hash is stale or missing')
    if frame_path.is_file():
        evidence[prefix + '_frames'] = frame_path
        frames = json.loads(frame_path.read_text())
        expected_names = frames.get('render_object_names')
        if expected_names is not None and sorted(audit.get('render_object_names', [])) != sorted(expected_names):
            errors.append('material display-state selection differs from frozen frame')
    required = {f'view-{i}.png' for i in range(8)} | {'materials.png', 'asset.glb'}
    hashes = audit.get('artifact_sha256', {})
    if not isinstance(hashes, dict):
        hashes = {}
    if required - hashes.keys():
        errors.append('material artifact manifest is incomplete')
    for name in sorted(required | hashes.keys()):
        if not isinstance(name, str) or Path(name).name != name or name in ('.', '..', 'audit.json'):
            errors.append('unsafe material artifact path')
            continue
        path = audit_path.parent / name
        if not path.resolve().is_relative_to(audit_path.parent.resolve()):
            errors.append('material artifact escapes audit directory')
            continue
        if not path.is_file():
            errors.append('missing material artifact: ' + name)
            continue
        evidence[prefix + '_' + name.replace('.', '_')] = path
        if hashes.get(name) != sha(path):
            errors.append('modified material artifact: ' + name)
    return evidence, errors, audit

