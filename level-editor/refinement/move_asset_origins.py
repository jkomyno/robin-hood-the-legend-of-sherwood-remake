"""Move legacy map export origins into their pinned asset descriptors.

Run once against a local library: python3 refinement/move_asset_origins.py library --apply
All active maps and descriptor pins are checked before any file is changed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


def migrate(library, apply=False):
    maps = sorted((library / 'scenes').glob('*.rhlos-map.json'))
    if not maps:
        raise ValueError('No active maps')
    descriptors = {}
    documents = {}
    for path in maps:
        document = json.loads(path.read_bytes())
        origins = document.get('sceneMetadata', {}).get('assetOrigins', {})
        references = document.get('assetSources', [])
        if not origins:
            continue
        if set(origins) != {ref['id'] for ref in references}:
            raise ValueError('Asset origins do not match map references: ' + str(path))
        for ref in references:
            origin = origins[ref['id']]
            if len(origin) != 3 or any(isinstance(x, bool) or not isinstance(x, (int, float))
                                      or not math.isfinite(x) for x in origin):
                raise ValueError('Invalid export origin: ' + ref['id'])
            descriptor_path = library / ref['descriptor']
            descriptor_bytes = descriptor_path.read_bytes()
            if hashlib.sha256(descriptor_bytes).hexdigest() != ref['descriptor_sha256']:
                raise ValueError('Changed descriptor pin: ' + str(descriptor_path))
            prior = descriptors.get(descriptor_path)
            if prior and prior[1] != origin:
                raise ValueError('Conflicting export origins: ' + str(descriptor_path))
            descriptors[descriptor_path] = (descriptor_bytes, origin)
        documents[path] = document
    replacements = {}
    hashes = {}
    for path, (original, origin) in descriptors.items():
        descriptor = json.loads(original)
        if 'source_origin_scene' in descriptor and descriptor['source_origin_scene'] != origin:
            raise ValueError('Descriptor export origin differs from map: ' + str(path))
        descriptor['source_origin_scene'] = origin
        data = encoded(descriptor)
        replacements[path] = data
        hashes[path] = hashlib.sha256(data).hexdigest()
    for path, document in documents.items():
        for ref in document['assetSources'] + document['sceneAssets']:
            if library / ref.get('descriptor', '') in hashes:
                ref['descriptor_sha256'] = hashes[library / ref['descriptor']]
        document['sceneMetadata'].pop('assetOrigins')
        replacements[path] = encoded(document)
    report = {'maps': len(documents), 'descriptors': len(descriptors),
              'bytes_removed_from_maps': sum(path.stat().st_size - len(replacements[path]) for path in documents)}
    if apply and replacements:
        backup = library / 'scenes' / 'backups' / ('asset-origin-migration-' +
                 datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        for path in replacements:
            saved = backup / path.relative_to(library)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
        try:
            for path, data in replacements.items():
                temporary = path.with_name(path.name + '.origin-migration-tmp')
                temporary.write_bytes(data)
                os.replace(temporary, path)
        except Exception:
            for path in replacements:
                shutil.copy2(backup / path.relative_to(library), path)
            raise
        report['backup'] = str(backup)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('library', type=Path)
    parser.add_argument('--apply', action='store_true')
    arguments = parser.parse_args()
    print(json.dumps(migrate(arguments.library.resolve(), arguments.apply), indent=2))
