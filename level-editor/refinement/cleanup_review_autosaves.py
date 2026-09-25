"""Remove an explicitly reviewed autosave list after final publication closure."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def preflight(repository, work_root, manifest, expected_manifest_sha256,
              protected, expected_protected_sha256, expected_count):
    repository, work_root = repository.resolve(), work_root.resolve()
    if not work_root.is_relative_to(repository):
        raise ValueError('Work root escapes repository')
    if sha(manifest) != expected_manifest_sha256 or sha(protected) != expected_protected_sha256:
        raise ValueError('Reviewed manifest or final publication union changed')
    union = json.loads(protected.read_text())
    if union.get('status') != 'FINAL-126-IMPORTS':
        raise ValueError('Final complete publication protection is required')
    protected_files = union['files']
    protected_paths = {Path(p).resolve() for p in protected_files}
    protected_hashes = set(protected_files.values())
    items = json.loads(manifest.read_text())
    if len(items) != expected_count or len({x['path'] for x in items}) != expected_count:
        raise ValueError('Reviewed autosave count or uniqueness changed')
    checked = []
    for item in items:
        relative = Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Only repository-relative autosave paths are allowed')
        path = repository / relative
        if path.suffix != '.blend1' or path.is_symlink() or path.resolve() != path:
            raise ValueError('Not a direct Blender autosave: ' + str(path))
        if not path.is_relative_to(work_root):
            raise ValueError('Autosave outside approved work root')
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != item['bytes']:
            raise ValueError('Autosave type, size or link count changed')
        if sha(path) != item['sha256']:
            raise ValueError('Autosave content changed')
        pair = path.with_suffix('.blend')
        if not pair.is_file() or pair.is_symlink():
            raise ValueError('Paired current model is absent')
        if path in protected_paths or item['sha256'] in protected_hashes:
            raise ValueError('Autosave is protected by final publication')
        checked.append(dict(item, absolute_path=str(path), paired_model=str(pair),
                            inode=[info.st_dev, info.st_ino], mtime_ns=info.st_mtime_ns))
    return checked


def write_receipt(path, report):
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['repository', 'work-root', 'manifest', 'protected-union', 'receipt']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--protected-sha256', required=True)
    parser.add_argument('--expected-count', type=int, required=True)
    parser.add_argument('--delete', action='store_true')
    args = parser.parse_args()
    checked = preflight(args.repository, args.work_root, args.manifest,
                        args.manifest_sha256, args.protected_union,
                        args.protected_sha256, args.expected_count)
    if args.receipt.exists():
        raise FileExistsError('Use a new receipt; prior receipts are immutable')
    report = dict(status='PREFLIGHT-PASS', deletion_authorized=args.delete,
                  timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  manifest=str(args.manifest.resolve()), manifest_sha256=args.manifest_sha256,
                  protected_union=str(args.protected_union.resolve()),
                  protected_union_sha256=args.protected_sha256, files=[])
    write_receipt(args.receipt, report)
    for item in checked:
        path = Path(item['absolute_path'])
        if sha(args.protected_union) != args.protected_sha256:
            raise ValueError('Final publication protection changed during cleanup')
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            with os.fdopen(descriptor, 'rb', closefd=False) as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            info = os.fstat(descriptor)
            if ([info.st_dev, info.st_ino] != item['inode'] or info.st_nlink != 1 or
                    info.st_size != item['bytes'] or digest != item['sha256']):
                raise ValueError('Autosave changed after preflight')
            current = path.lstat()
            if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                raise ValueError('Autosave path changed after preflight')
            if not Path(item['paired_model']).is_file():
                raise ValueError('Paired current model disappeared')
            row = dict(item, action='delete-planned' if args.delete else 'dry-run-retained')
            report['files'].append(row)
            write_receipt(args.receipt, report)
            if args.delete:
                path.unlink()
                row['action'] = 'deleted'
                write_receipt(args.receipt, report)
        finally:
            os.close(descriptor)
    report['status'] = 'DELETED' if args.delete else 'DRY-RUN-PASS'
    report['bytes'] = sum(item['bytes'] for item in checked)
    write_receipt(args.receipt, report)
    print(json.dumps({k: v for k, v in report.items() if k != 'files'}, indent=2))


if __name__ == '__main__':
    main()
