"""Read/write descriptor-backed maps through the shared TypeScript format code."""
import json
from pathlib import Path
import subprocess

BRIDGE = Path(__file__).resolve().parents[1] / 'pipeline/src/stored-map-bridge.ts'


def asset_source_references(document):
    """Yield pinned model references from plain sources and bundled appearances."""
    for source in document.get('assetSources', []):
        appearances = source.get('appearances')
        if appearances is None:
            yield source
            continue
        for appearance in appearances:
            state = appearance['state']
            yield {
                'id': source['id'] if state == 'base' else source['id'] + '--state-' + state,
                'descriptor': source['descriptor'],
                'descriptor_sha256': source['descriptor_sha256'],
                **{key: value for key, value in appearance.items() if key != 'state'},
            }


def convert(action, library, document):
    result = subprocess.run(['node', str(BRIDGE), action, str(library)],
                            input=json.dumps(document), text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def expand_document(library, document):
    if document.get('version') != 2 and not document.get('assetSources'):
        return document
    return convert('expand', library, document)


def store_document(library, document):
    if not document.get('assetSources'):
        return document
    return convert('store', library, document)
