"""Restore the southwest courtyard support to its contiguous wall group."""
import json
from revise_catalog_v13 import WORK, sha, write, parse_catalog


def main():
    previous = WORK / 'grouping/catalog-v13.json'
    catalog = json.loads(previous.read_text())
    groups = {g['id']: g for g in catalog['groups']}
    origin = groups['nottingham-castle-southwest-stair']
    destination = groups['nottingham-castle-west-courtyard-wall']
    assert [p['obstacle'] for p in origin['parts']] == [352]
    destination['parts'].append({'obstacle': 352, 'name': 'Hidden courtyard support volume'})
    destination['parts'].sort(key=lambda p: p['obstacle'])
    catalog['groups'].remove(origin)
    catalog['canonical_owners']['building-352'] = destination['id']
    catalog['revision'] = 14
    catalog['revision_notes'] = [
        'Restore canonical352 as the original courtyard support volume belonging to the west courtyard wall.',
        'Retire the duplicate southwest castle stair reconstruction. The distinct approved wall stair221 retains its geometry, source ownership and ground connection.',
        'Canonical352 has no exposed source-camera pixels; its source-hidden surfaces remain unsupported by artwork.',
    ]
    index = parse_catalog(catalog, {f'building-{i:03}' for i in range(555)})
    validation = {'status': 'PASS', 'groups': len(index.groups), 'source_parts': len(index.sources),
        'explicit_components': len(index.component_owners), 'missing_sources': [], 'duplicate_component_ownership': [],
        'transfers': [{'source_node': 'building-352', 'from': origin['id'], 'to': destination['id']}],
        'retired_groups': [origin['id']], 'geometry_mutations': 0}
    target = WORK / 'grouping/catalog-v14.json'
    write(target, catalog)
    write(WORK / 'grouping/validation-v14.json', validation)
    evidence = ['castle-audit/review6-stair/native-identity.json', 'castle-audit/review6-stair/native352-first-hits.json',
                'castle-audit/review6-stair/identity-source-comparison.png']
    write(WORK / 'grouping/grouping-review-v14.json', {'status': 'reviewed',
        'reviewer': 'Source footprint, native elevation connections and full-scene first-hit review',
        'catalog_sha256': sha(target), 'inventory_sha256': sha(WORK / 'inventory/inventory-v2.json'),
        'previous_catalog_sha256': sha(previous), 'notes': catalog['revision_notes'], 'validation': validation,
        'evidence': [{'path': p, 'sha256': sha(WORK / p)} for p in evidence]})
    print(json.dumps(validation))


if __name__ == '__main__':
    main()
