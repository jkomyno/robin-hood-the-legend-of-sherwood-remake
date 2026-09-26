"""Publish verified lossless state bundles, preserving concurrent library edits."""
import argparse
import copy
import fcntl
import hashlib
import json
from asset_index import validate_asset_index, write_asset_index
import os
from pathlib import Path
import shutil
import tempfile


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


def atomic(path, data):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def local(name):
    if not name or Path(name).name != name or name in ('.', '..'):
        raise ValueError(f'Unsafe local path: {name}')
    return name


def check(path, expected):
    if Path(path).is_symlink() or not Path(path).is_file() or sha(path) != expected:
        raise ValueError(f'Changed input: {path}')


def prepare(library, stage, scenes):
    library, stage, scenes = map(Path, (library, stage, scenes))
    receipts = json.loads((stage / 'bundles.json').read_text())
    ids = [local(r['asset_id']) for r in receipts]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate bundle IDs')
    staged_index = json.loads((stage / 'index.json').read_text())['assets']
    if sorted(e['id'] for e in staged_index) != sorted(ids):
        raise ValueError('Stage index differs from receipts')
    files, removals, assets = [], [], {}
    for r in receipts:
        aid = r['asset_id']
        src, dst = stage / aid, library / aid
        check(dst / 'asset.json', r['source_descriptor_sha256'])
        sources = {local(f['path']): f for f in r['source_files']}
        for name, f in sources.items():
            check(dst / name, f['sha256'])
        check(src / 'model.glb', r['output']['sha256'])
        check(src / 'asset.json', r['output_descriptor_sha256'])
        rr = json.loads((src / 'bundle.receipt.json').read_text())
        if {k: v for k, v in rr.items() if k != 'skipped'} != {k: v for k, v in r.items() if k != 'skipped'}:
            raise ValueError('Individual receipt differs')
        if not r['states'] or any(s['source_sha256'] != sources[s['source_file']]['sha256'] or not s['semantic_sha256'] for s in r['states']):
            raise ValueError('Missing source/state semantic binding')
        desc = json.loads((src / 'asset.json').read_text())
        if desc['id'] != aid or desc['model'] != 'model.glb':
            raise ValueError('Wrong output descriptor')
        assets[aid] = r
        for name in ('model.glb', 'asset.json', 'bundle.receipt.json', 'preview.glb', 'preview.glb.receipt.json'):
            p = dst / name
            files.append({'path': str(p.resolve()), 'source': str((src / name).resolve()), 'before': sha(p) if p.exists() else None, 'after': sha(src / name)})
        for name, f in sources.items():
            if name != 'model.glb':
                if not (name.startswith('model-door-') or name == 'model-applied.glb'):
                    raise ValueError('Unexpected obsolete source name')
                removals.append({'path': str((dst / name).resolve()), 'before': f['sha256']})
    migrations = []
    for p in sorted(scenes.glob('*.rhlos-map.json')):
        doc = json.loads(p.read_text())
        changed = []
        for ref in doc.get('assetSources', []):
            if ref['id'] not in assets:
                continue
            r = assets[ref['id']]
            old_name = Path(ref['model']).name
            states = [s for s in r['states'] if s['source_file'] == old_name and s['source_scene'] == ref.get('model_scene')]
            if len(states) != 1 or ref['model_sha256'] != states[0]['source_sha256'] or ref['descriptor_sha256'] != r['source_descriptor_sha256']:
                raise ValueError(f'Saved asset pin does not match bundle source: {p}: {ref["id"]}')
            prefix = str(Path(ref['model']).parent)
            ref.update(model=prefix + '/model.glb', model_scene=states[0]['scene'], model_sha256=r['output']['sha256'], descriptor_sha256=r['output_descriptor_sha256'])
            changed.append(ref['id'])
        if changed:
            migrations.append({'path': str(p.resolve()), 'before': sha(p), 'document': doc, 'ids': changed})
    return {'version': 1, 'library': str(library.resolve()), 'stage': str(stage.resolve()), 'files': files, 'removals': removals, 'migrations': migrations, 'entries': staged_index, 'assets': ids,
            'model_bytes_before': sum(f['bytes'] for r in receipts for f in r['source_files']),
            'model_bytes_after': sum(r['output']['bytes'] for r in receipts)}


def merge_index(index, entries):
    result = copy.deepcopy(index)
    updates = {e['id']: e for e in entries}
    found = set()
    for entry in result['assets']:
        if entry['id'] in updates:
            if entry['id'] in found:
                raise ValueError('Duplicate live index ID')
            found.add(entry['id'])
            # Retain live names, tags and any unrelated metadata.
            for key in ('model', 'descriptor', 'model_scene', 'preview_model'):
                entry[key] = updates[entry['id']][key]
            # New model bytes: a lossy model bound to the old bytes would be stale. The next
            # publication staging or `lossy_assets.py -- library` run derives it again.
            entry.pop('lossy_model', None)
    if found != set(updates):
        raise ValueError('Missing live index asset')
    return result


def apply(plan, backup, hook=lambda phase, n: None):
    """Index is installed last. Rollback never overwrites a foreign file change."""
    library, backup = Path(plan['library']), Path(backup)
    if backup.resolve().is_relative_to(library.resolve()):
        raise ValueError('Rollback backup must be outside the live asset library')
    backup.mkdir(parents=True, exist_ok=False)
    receipt = {'status': 'preparing', 'backup': str(backup.resolve()), 'assets': plan['assets'], 'operations': [], 'conflicts': []}
    def save():
        atomic(backup / 'publication.json', encoded(receipt))
    with (library / '.publication.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        index_path = library / 'index.json'
        initial_index = index_path.read_bytes()
        index_sha = hashlib.sha256(initial_index).hexdigest()
        new_index = encoded(merge_index(json.loads(initial_index), plan['entries']))
        prospective = {str(Path(f['path']).relative_to(library)): Path(f['source']) for f in plan['files']}
        validate_asset_index(library, new_index, files=prospective)
        jobs = []
        for f in plan['files']:
            check(f['source'], f['after'])
            jobs.append({**f, 'data_source': f['source']})
        for m in plan['migrations']:
            data = encoded(m['document'])
            jobs.append({'path': m['path'], 'before': m['before'], 'after': hashlib.sha256(data).hexdigest(), 'data': data})
        jobs.extend({**f, 'after': None} for f in plan['removals'])
        jobs.append({'path': str(index_path), 'before': index_sha, 'after': hashlib.sha256(new_index).hexdigest(), 'data': new_index, 'index': True})
        try:
            for i, j in enumerate(jobs):
                p = Path(j['path'])
                if j['before'] is not None:
                    check(p, j['before'])
                    shutil.copy2(p, backup / str(i))
                elif p.exists():
                    raise ValueError(f'Unexpected destination: {p}')
            save()
            for i, j in enumerate(jobs):
                hook('before', i)
                check(index_path, index_sha)
                p = Path(j['path'])
                if j['before'] is not None:
                    check(p, j['before'])
                elif p.exists():
                    raise ValueError(f'Destination appeared: {p}')
                op = {k: j[k] for k in ('path', 'before', 'after')}
                op.update(backup=str(i), status='planned')
                receipt['operations'].append(op)
                save()
                if j['after'] is None:
                    p.unlink()
                else:
                    data = Path(j['data_source']).read_bytes() if 'data_source' in j else j['data']
                    if hashlib.sha256(data).hexdigest() != j['after']:
                        raise ValueError('Stage changed during publication')
                    if j.get('index'):
                        write_asset_index(library, data)
                    else:
                        atomic(p, data)
                op['status'] = 'installed'
                save()
                if j.get('index'):
                    index_sha = j['after']
                hook('after', i)
            for j in jobs:
                if j['after'] is None:
                    if Path(j['path']).exists():
                        raise ValueError('Removed source reappeared')
                else:
                    check(j['path'], j['after'])
            receipt.update(status='published', model_bytes_before=plan['model_bytes_before'], model_bytes_after=plan['model_bytes_after'], migrated_references=sum(len(m['ids']) for m in plan['migrations']))
            save()
        except Exception as e:
            receipt['error'] = str(e)
            for op in reversed(receipt['operations']):
                p = Path(op['path'])
                current = sha(p) if p.exists() else None
                if current == op['before']:
                    continue
                if current != op['after']:
                    receipt['conflicts'].append(str(p))
                    continue
                if op['before'] is None:
                    if p.exists(): p.unlink()
                else:
                    atomic(p, (backup / op['backup']).read_bytes())
            receipt['status'] = 'rollback-conflict' if receipt['conflicts'] else 'rolled-back'
            save()
            raise
    return receipt


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--library', type=Path, required=True)
    p.add_argument('--stage', type=Path, required=True)
    p.add_argument('--scenes', type=Path, required=True)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--backup', type=Path)
    args = p.parse_args()
    plan = prepare(args.library, args.stage, args.scenes)
    if args.apply:
        if plan != json.loads(args.plan.read_text()):
            raise ValueError('Prepared publication changed; prepare again and review differences')
        if not args.backup: raise ValueError('--backup required')
        print(json.dumps(apply(plan, args.backup), indent=2))
    else:
        args.plan.parent.mkdir(parents=True, exist_ok=True)
        atomic(args.plan, encoded(plan))
        print(json.dumps({k: plan[k] for k in ('assets', 'model_bytes_before', 'model_bytes_after')}))


if __name__ == '__main__':
    main()
