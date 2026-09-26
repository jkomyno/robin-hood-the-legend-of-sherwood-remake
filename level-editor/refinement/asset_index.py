"""The publication boundary for 3D asset indexes, usable without Blender.

Callers keep their existing publication locks and install payloads before the index.
Prospective file mappings allow transaction preflight and staged merged catalogs to
validate the exact payloads that will be installed, including unchanged live assets.
Historical transaction rollback restores backups rather than publishing a new index.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


def _relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or '\0' in value
            or any(part in ('', '.', '..') for part in value.split('/'))
            or Path(value).is_absolute()):
        raise ValueError(f'Unsafe asset index path: {value!r}')
    return value


def _document(index):
    return json.loads(index) if isinstance(index, (bytes, str)) else index


def lossy_problems(root, index, *, files=None):
    """Check source/output receipt hashes for every declared lossy derivative."""
    root, index = Path(root), _document(index)
    files = files or {}
    hashes = {}

    def resolve(name):
        name = _relative(name)
        return Path(files[name]) if name in files else root / name

    def sha(name):
        path = resolve(name)
        if path not in hashes:
            with path.open('rb') as stream:
                hashes[path] = hashlib.file_digest(stream, 'sha256').hexdigest()
        return hashes[path]

    problems = []
    for entry in index['assets']:
        if 'lossy_model' not in entry:
            continue
        identity = entry['id']
        lossy = _relative(entry['lossy_model'])
        model = _relative(entry['model'])
        try:
            if not resolve(lossy).is_file() or not resolve(lossy + '.receipt.json').is_file():
                problems.append(f'{identity}: lossy model or receipt missing')
                continue
            receipt = json.loads(resolve(lossy + '.receipt.json').read_bytes())
            if not isinstance(receipt, dict):
                raise ValueError('receipt must be an object')
            if receipt.get('source') != sha(model):
                problems.append(f'{identity}: lossy receipt does not bind the current model')
            if receipt.get('output') != sha(lossy):
                problems.append(f'{identity}: lossy model bytes differ from its receipt')
        except (OSError, ValueError) as error:
            problems.append(f'{identity}: cannot validate lossy asset: {error}')
    return problems


def validate_asset_index(root, index, *, files=None):
    """Reject malformed catalogs and stale, missing, or corrupt lossy assets."""
    index = _document(index)
    if not isinstance(index, dict) or not isinstance(index.get('assets'), list):
        raise ValueError('Asset index must contain an assets array')
    ids = set()
    for entry in index['assets']:
        if not isinstance(entry, dict) or not isinstance(entry.get('id'), str) or not entry['id']:
            raise ValueError('Asset index entry requires an ID')
        if entry['id'] in ids:
            raise ValueError('Duplicate asset index ID: ' + entry['id'])
        ids.add(entry['id'])
        for key in ('model', 'descriptor', 'lossy_model', 'preview_model'):
            if key in entry:
                _relative(entry[key])
        if 'lossy_model' in entry and 'model' not in entry:
            raise ValueError('Lossy asset requires a source model: ' + entry['id'])
    problems = lossy_problems(root, index, files=files)
    if problems:
        raise ValueError('Asset index has non-current lossy assets:\n' + '\n'.join(problems))


def write_asset_index(root, index, *, target=None, files=None):
    """Validate the entire proposed catalog, then atomically replace its index.

    Byte/string inputs retain their exact encoding for publication hash guards.
    `target` is only needed for a staged merged index outside the asset root.
    """
    validate_asset_index(root, index, files=files)
    data = (index if isinstance(index, bytes) else index.encode() if isinstance(index, str)
            else (json.dumps(index, indent=2, ensure_ascii=False) + '\n').encode())
    target = Path(target) if target is not None else Path(root) / 'index.json'
    mode = target.stat().st_mode & 0o777 if target.exists() else 0o644
    fd, temporary = tempfile.mkstemp(prefix='.' + target.name + '-', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path, help='3d-assets directory')
    parser.add_argument('--check', action='store_true', help='Validate without writing')
    parser.add_argument('--files', type=json.loads, help='JSON mapping of prospective relative paths to staged files')
    args = parser.parse_args()
    data = sys.stdin.buffer.read()
    files = args.files
    if args.check:
        validate_asset_index(args.root, data, files=files)
    else:
        write_asset_index(args.root, data, files=files)
