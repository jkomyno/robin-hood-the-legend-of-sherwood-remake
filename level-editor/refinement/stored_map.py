"""Read/write descriptor-backed maps through the shared TypeScript format code."""
import json
from pathlib import Path
import subprocess

BRIDGE = Path(__file__).resolve().parents[1] / 'pipeline/src/stored-map-bridge.ts'


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
