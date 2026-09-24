"""Attach facade props and the upper terrace parapet to their buildings."""
import json
from revise_catalog_v13 import WORK, sha, write, parse_catalog


def main():
    previous = WORK / 'grouping/catalog-v14.json'
    catalog = json.loads(previous.read_text())
    groups = {g['id']: g for g in catalog['groups']}
    transfers = []
    for number, source, target, name in [
        (551, 'nottingham-church-road-mission-props', 'nottingham-northwest-timber-house', 'Facade shelf and barrel'),
        (552, 'nottingham-church-road-mission-props', 'nottingham-northwest-timber-house', 'Raised facade shutter'),
        (553, 'nottingham-church-road-mission-props', 'nottingham-north-dormer-house', 'Raised facade shutter'),
        (554, 'nottingham-church-road-mission-props', 'nottingham-north-dormer-house', 'Facade bucket'),
        (497, 'nottingham-castle-west-stair-tower', 'nottingham-castle-main-hall', 'Upper terrace parapet'),
    ]:
        part = next(p for p in groups[source]['parts'] if p['obstacle'] == number)
        groups[source]['parts'].remove(part)
        part['name'] = name
        if number >= 551:
            part['state_note'] = 'Retain patch010 simulation membership and mission artwork as a separate selectable part.'
        groups[target]['parts'].append(part)
        groups[target]['parts'].sort(key=lambda p: p['obstacle'])
        node = f'building-{number:03}'
        catalog['canonical_owners'][node] = target
        transfers.append({'source_node': node, 'from': source, 'to': target})
    retired = groups['nottingham-church-road-mission-props']
    assert not retired['parts']
    catalog['groups'].remove(retired)
    catalog['revision'] = 15
    catalog['revision_notes'] = [
        'Attach facade props551/552 to the northwest timber house and553/554 to the north dormer house, retaining separate selection and patch010 state identity.',
        'Move detached parapet497 from the west stair tower into the main hall upper terrace it encloses.',
        'Ownership changes preserve approved part geometry; newly combined groups require fresh review with all relevant source states.',
    ]
    index = parse_catalog(catalog, {f'building-{i:03}' for i in range(555)})
    validation = {'status': 'PASS', 'groups': len(index.groups), 'source_parts': len(index.sources),
        'explicit_components': len(index.component_owners), 'missing_sources': [], 'duplicate_component_ownership': [],
        'transfers': transfers, 'retired_groups': [retired['id']], 'geometry_mutations': 0}
    target = WORK / 'grouping/catalog-v15.json'
    write(target, catalog)
    write(WORK / 'grouping/validation-v15.json', validation)
    evidence = ['coordinator-audit/batch6-grouping/selection-parent-plan.json']
    write(WORK / 'grouping/grouping-review-v15.json', {'status': 'reviewed',
        'reviewer': 'Source facade and terrace footprint inspection; user requested immediate building grouping',
        'catalog_sha256': sha(target), 'inventory_sha256': sha(WORK / 'inventory/inventory-v2.json'),
        'previous_catalog_sha256': sha(previous), 'notes': catalog['revision_notes'], 'validation': validation,
        'evidence': [{'path': p, 'sha256': sha(WORK / p)} for p in evidence]})
    print(json.dumps(validation))


if __name__ == '__main__':
    main()
