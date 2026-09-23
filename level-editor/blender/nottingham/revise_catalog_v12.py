"""Correct two village object names after source-artwork identification."""
import copy
import hashlib
import json
from pathlib import Path

WORK = Path(__file__).resolve().parents[2] / 'work/nottingham-refinement'
NAMES = {
    'nottingham-village-stream-trough': 'Streamside low rock fins',
    'nottingham-village-courtyard-well': 'Village courtyard thatched shelter',
}


def main():
    previous = WORK / 'grouping/catalog-v11.json'
    before = json.loads(previous.read_text())
    catalog = copy.deepcopy(before)
    for group in catalog['groups']:
        if group['id'] in NAMES:
            group['name'] = NAMES[group['id']]
    assert [g['parts'] for g in catalog['groups']] == [g['parts'] for g in before['groups']]
    assert catalog['canonical_owners'] == before['canonical_owners']
    catalog['revision'] = 12
    catalog['revision_notes'] = [
        'Source235 is a low rock formation, not a trough; source260 is a thatched shelter, not a hay pile.',
        'Display names only. Stable IDs, source membership, component selectors and existing frozen packets are unchanged.',
    ]
    target = WORK / 'grouping/catalog-v12.json'
    with target.open('x') as output:
        output.write(json.dumps(catalog, indent=2) + '\n')
    validation = {
        'status': 'PASS', 'metadata_only': True, 'groups': len(catalog['groups']),
        'changed_names': NAMES, 'ownership_changes': 0, 'geometry_mutations': 0,
        'previous_catalog_sha256': hashlib.sha256(previous.read_bytes()).hexdigest(),
        'catalog_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
    }
    with (WORK / 'grouping/validation-v12.json').open('x') as output:
        output.write(json.dumps(validation, indent=2) + '\n')
    print(json.dumps(validation))


if __name__ == '__main__':
    main()
