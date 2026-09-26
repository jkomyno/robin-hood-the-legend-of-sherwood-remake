"""Map-independent catalog coverage and staged scene naming checks."""
import sys as _refinement_sys
from pathlib import Path as _RefinementPath
_refinement_legacy = str(_RefinementPath(__file__).resolve().parents[2] / 'blender')
if _refinement_legacy not in _refinement_sys.path:
    _refinement_sys.path.append(_refinement_legacy)

from pathlib import Path
import re
from catalog_schema import source_for_part, parse_catalog


def canonical_parts(catalog, map_name):
    if catalog['map'] != map_name:
        raise ValueError('Publication map and catalog differ')
    if catalog.get('version') == 2:
        return parse_catalog(catalog).sources
    parts = [source_for_part(part) for group in catalog['groups']
             for part in group['parts']]
    if not parts or len(parts) != len(set(parts)):
        raise ValueError('Publication catalog has empty or duplicate part ownership')
    return set(parts)


def editor_part_id(source, component=None):
    """Keep native provenance separate from a selectable component identity."""
    if component is None:
        return source
    if not re.fullmatch(r'building-\d+', source) or not isinstance(component, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', component):
        raise ValueError('Invalid component editor identity')
    return source + '--component-' + component


def publication_parts(catalog):
    """Return exact selectable parts; never waive shared whole-source ownership."""
    canonical_parts(catalog, catalog['map'])
    result = {}
    for group in catalog['groups']:
        for part in group['parts']:
            source = source_for_part(part)
            for component in part.get('components', [None]):
                node = editor_part_id(source, component)
                if node in result:
                    raise ValueError('Duplicate publication editor part: ' + node)
                result[node] = dict(asset_id=group['id'], source_node=source,
                                    source_components=[] if component is None else [component])
    return result


def validate_export_records(catalog, records, asset_ids=None):
    """Bind each exported mesh to its catalog part and exact selector subset."""
    expected = publication_parts(catalog)
    if asset_ids is not None:
        expected = {key: value for key, value in expected.items() if value['asset_id'] in asset_ids}
    split = {value['source_node'] for value in publication_parts(catalog).values() if value['source_components']}
    assigned, seen = {}, {}
    for record in records:
        source = record['source_node']
        if source == 'ground':
            continue
        component = record.get('projection_component') if source in split else None
        if source in split and not component:
            raise ValueError('Export contains a componentless split original: ' + source)
        node = editor_part_id(source, component)
        if node not in expected or expected[node]['asset_id'] != record['asset_group']:
            raise ValueError('Exported component differs from catalog ownership: ' + node)
        if node in seen and component is not None:
            raise ValueError('Duplicate exported component: ' + node)
        if record['name'] in assigned:
            raise ValueError('Duplicate exported mesh name: ' + record['name'])
        seen[node] = True
        assigned[record['name']] = node
    validate_coverage(set(seen), set(expected))
    return assigned


def scene_filename(plan):
    name = plan.get('scene_filename', plan['map_name'].lower().replace(' ', '-') + '.rhlos-map.json')
    if not isinstance(name, str) or Path(name).name != name or not name.endswith('.rhlos-map.json'):
        raise ValueError('Staged scene filename must be a local .rhlos-map.json filename')
    return name


def validate_coverage(actual, expected):
    if actual != expected:
        raise ValueError('Publication canonical coverage differs from catalog: ' +
                         repr({'missing': sorted(expected - actual, key=str),
                               'unexpected': sorted(actual - expected, key=str)}))
