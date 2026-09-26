"""Install an independently verified map conversion with concurrent-write guards.

Old snapshots and documents are retained under the library scenes/backups directory. Immutable
assets are installed first; map documents are replaced atomically under the same
publication lock used by refinement promotion.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shutil


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def normalized(document):
    document = json.loads(json.dumps(document))
    for key in ('glb', 'sceneAssets', 'sourceMap'):
        document.pop(key, None)
    provenance = document.get('provenance', {})
    provenance.pop('glb_sha256', None)
    if not provenance:
        document.pop('provenance', None)
    return document


def migrate(report_path, apply=False):
    migration = json.loads(report_path.read_text())
    library, output = Path(migration['library']), Path(migration['output'])
    backup = library / 'scenes/backups/map-manifest-migration'
    with (library / '.publication.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        files = {}
        for item in migration['maps']:
            for path_key, hash_key in [('glb', 'glb_sha256'), ('metadata', 'metadata_sha256'), ('document', 'previous_document_sha256')]:
                if sha(Path(item[path_key])) != item[hash_key]:
                    raise ValueError('Live source changed: ' + item[path_key])
            document_path = output / 'scenes' / (item['name'] + '.level3d.json')
            document = json.loads(document_path.read_text())
            if item['previous_document_sha256'] and normalized(json.loads(Path(item['document']).read_text())) != normalized(document):
                raise ValueError('Conversion changed editor state: ' + item['name'])
            report = json.loads((output / 'import-reports' / (document['map'] + '.json')).read_text())
            if report['source_sha256'] != item['glb_sha256'] or report['sceneAssets'] != document['sceneAssets']:
                raise ValueError('Conversion report differs from document: ' + item['name'])
            for reference in document['sceneAssets']:
                files[reference['model']] = reference['model_sha256']
                for resource in reference['resources']:
                    files[resource['path']] = resource['sha256']
        for relative, digest in files.items():
            if sha(output / relative) != digest:
                raise ValueError('Staged asset changed: ' + relative)
            if (library / relative).exists() and sha(library / relative) != digest:
                raise ValueError('Immutable library asset changed: ' + relative)
        if not apply:
            return {'status': 'VERIFIED', 'maps': len(migration['maps']), 'files': len(files)}
        if backup.exists():
            raise FileExistsError(backup)
        (backup / 'scenes').mkdir(parents=True)
        for item in migration['maps']:
            for key in ('glb', 'metadata', 'document'):
                source = Path(item[key])
                if source.exists():
                    shutil.copy2(source, backup / 'scenes' / source.name)
        for relative in files:
            target = library / relative
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix(target.suffix + '.migration-tmp')
                shutil.copy2(output / relative, temporary)
                temporary.replace(target)
        written = []
        try:
            for item in migration['maps']:
                target = Path(item['document'])
                if sha(target) != item['previous_document_sha256']:
                    raise ValueError('Map changed before manifest replacement: ' + str(target))
                temporary = target.with_suffix('.migration-tmp')
                shutil.copy2(output / 'scenes' / target.name, temporary)
                temporary.replace(target)
                written.append(item)
        except Exception:
            for item in reversed(written):
                target = Path(item['document'])
                if item['previous_document_sha256'] is None:
                    target.unlink()
                else:
                    shutil.copy2(backup / 'scenes' / target.name, target)
            raise
        for item in migration['maps']:
            for key, hash_key in [('glb', 'glb_sha256'), ('metadata', 'metadata_sha256')]:
                source = Path(item[key])
                if sha(source) != item[hash_key]:
                    raise ValueError('Source changed before archival: ' + str(source))
                # The verified archival copy already exists; remove only its identical live copy.
                source.unlink()
        result = {'status': 'APPLIED', 'maps': len(migration['maps']), 'files': len(files), 'backup': str(backup)}
        (output.parent / 'applied.json').write_text(json.dumps(result, indent=2)+'\n')
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(migrate(args.report.resolve(strict=True), args.apply)))
