"""Validated logical asset ownership, including explicitly partitioned sources.

Version 1 owns whole source nodes. Version 2 may distribute a source's named
projection components between assets; canonical_owners retains provenance and
assigns hidden, componentless originals. Parsing never infers spatial ownership.
"""
from dataclasses import dataclass


@dataclass
class CatalogIndex:
    groups: dict
    canonical_owners: dict
    parts_by_source: dict
    component_owners: dict

    @property
    def sources(self):
        return set(self.parts_by_source)

    @property
    def split_sources(self):
        return {source for source, _ in self.component_owners}

    def owner_for(self, source, component=None):
        if source not in self.parts_by_source:
            raise ValueError(f'Unknown source node: {source}')
        if source in self.split_sources and component:
            try:
                return self.component_owners[source, component]
            except KeyError:
                raise ValueError(f'Unexpected source component: {source}/{component}') from None
        owner = self.canonical_owners[source]
        return next((group, part) for group, part in self.parts_by_source[source]
                    if group['id'] == owner)

    def validate_meshes(self, records):
        """Validate actual component coverage before changing a Blender hierarchy.

        Records contain source_node, projection_component and hide_render. Each
        explicit selector addresses exactly one mesh. Retained originals without
        selectors must be hidden from rendering, so they cannot double the split.
        """
        records = [record for record in records if record['source_node'] != 'ground']
        actual = {record['source_node'] for record in records}
        if actual != self.sources:
            raise ValueError(f'Coverage mismatch: missing={sorted(self.sources-actual)}, '
                             f'extra={sorted(actual-self.sources, key=str)}')
        seen = set()
        for record in records:
            source, component = record['source_node'], record.get('projection_component')
            if source not in self.split_sources:
                continue
            if not component:
                if not record.get('hide_render', False):
                    raise ValueError(f'Visible componentless original of split source: {source}')
                continue
            key = source, component
            self.owner_for(*key)
            if key in seen:
                raise ValueError(f'Duplicate component mesh: {source}/{component}')
            seen.add(key)
        missing = set(self.component_owners) - seen
        if missing:
            raise ValueError(f'Missing component meshes: {sorted(missing)}')


def parse_catalog(catalog, expected_sources=None):
    """Return an ownership index, rejecting ambiguous or incomplete selectors."""
    version = catalog.get('version')
    if version not in (1, 2):
        raise ValueError(f'Unsupported catalog version: {version}')
    if not isinstance(catalog.get('map'), str) or not catalog['map'].strip():
        raise ValueError('Catalog requires a map name')
    groups, names, parts, components = {}, set(), {}, {}
    for group in catalog['groups']:
        identifier, name = group['id'], group['name'].strip()
        if not isinstance(identifier, str) or not identifier.strip() or identifier in groups:
            raise ValueError('Missing/duplicate asset ID')
        if not name or name.casefold() in names or name.lower().startswith('group '):
            raise ValueError(f'Missing, duplicate or placeholder asset name: {name}')
        if not group['parts']:
            raise ValueError(f'Empty asset: {name}')
        groups[identifier] = group
        names.add(name.casefold())
        own_sources = set()
        for part in group['parts']:
            number = part['obstacle']
            if type(number) is not int or number < 0 or not part['name'].strip():
                raise ValueError(f'Invalid named source part: {part}')
            source = f'building-{number:03}'
            if source in own_sources:
                raise ValueError(f'Duplicate source entry within asset: {identifier}/{source}')
            own_sources.add(source)
            if version == 1 and ('components' in part or source in parts):
                raise ValueError(f'Version 1 requires unique whole-source ownership: {source}')
            parts.setdefault(source, []).append((group, part))
            if 'components' in part:
                selectors = part['components']
                if not isinstance(selectors, list) or not selectors:
                    raise ValueError(f'Components must be a nonempty list: {source}')
                for component in selectors:
                    if not isinstance(component, str) or not component.strip() or component != component.strip():
                        raise ValueError(f'Invalid component selector: {source}/{component}')
                    key = source, component
                    if key in components:
                        raise ValueError(f'Duplicate component ownership: {source}/{component}')
                    components[key] = group, part
    for source, entries in parts.items():
        if len(entries) > 1 and any('components' not in part for _, part in entries):
            raise ValueError(f'Shared source requires explicit disjoint components: {source}')
    if version == 1:
        owners = {source: entries[0][0]['id'] for source, entries in parts.items()}
    else:
        owners = catalog.get('canonical_owners')
        if not isinstance(owners, dict) or set(owners) != set(parts):
            raise ValueError('canonical_owners must cover every source exactly')
        for source, owner in owners.items():
            if owner not in groups or not any(group['id'] == owner for group, _ in parts[source]):
                raise ValueError(f'Canonical owner must contain its source: {source}/{owner}')
        owners = dict(owners)
    if expected_sources is not None:
        expected = set(expected_sources) - {'ground'}
        if set(parts) != expected:
            raise ValueError(f'Coverage mismatch: missing={sorted(expected-set(parts))}, '
                             f'extra={sorted(set(parts)-expected)}')
    return CatalogIndex(groups, owners, parts, components)
