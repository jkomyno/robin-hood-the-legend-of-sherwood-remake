"""Explicit component selectors for a reviewed revealed projection pass."""

# Door animation graphics are distinct projection sources, but use the room's
# reviewed removable cover components. Keep this association explicit: a label
# suffix or a selector's requested patch alone is not ownership authority.
ENDPOINT_COVER_PATCHES = {
    'upper-prison-door-initial': 'patch-002',
    'upper-prison-door-applied': 'patch-002',
    'southwest-prison-door-initial': 'patch-007',
    'southwest-prison-door-applied': 'patch-007',
}


def filter_receivers(objects, selectors=None, *, available_objects=None):
    """Restrict named source nodes to reviewed components within one layer."""
    objects=list(objects)
    if not selectors:return objects
    catalog=list(available_objects) if available_objects is not None else objects
    permitted={}
    for selector in selectors:
        if set(selector)!={'source_node','projection_components','patch_id'}:
            raise ValueError('Receiver selector requires source_node, projection_components and patch_id')
        node=selector['source_node'];components=selector['projection_components']
        if (not isinstance(node,str) or not node or not isinstance(components,list) or not components
                or not isinstance(selector['patch_id'],str) or not selector['patch_id']):
            raise ValueError('Invalid or duplicate receiver selector')
        selected=set()
        for component in components:
            if not isinstance(component,str) or not component:raise ValueError('Empty receiver component')
            matches=[o for o in catalog if o.get('source_node')==node and o.get('projection_component')==component
                     and o.get('reveal_component_patch_id')==selector['patch_id']]
            if len(matches)!=1:
                raise ValueError('Receiver selector does not identify one reviewed patch component')
            if matches[0] in selected or matches[0] in permitted.get(node,set()):
                raise ValueError('Duplicate receiver component selection')
            selected.add(matches[0])
        permitted.setdefault(node,set()).update(selected)
    return [o for o in objects if o.get('source_node') not in permitted or o in permitted[o.get('source_node')]]


def validate_receiver_partition(objects, layers, selectors, *, available_objects=None):
    """Resolve complete layers before mutation; every mesh has at most one owner.

    A canonical node may span patches only through disjoint resolved components.
    Broad selectors still include every mesh of their node and therefore cannot
    silently overlap a narrower selector in another layer.
    """
    objects=list(objects)
    catalog=list(available_objects) if available_objects is not None else objects
    owned={};resolved={}
    for label,nodes in layers.items():
        selected=filter_receivers([o for o in objects if o.get('source_node') in nodes],
                                  selectors.get(label),available_objects=catalog)
        for obj in selected:
            if obj in owned:
                raise ValueError(f'Overlapping receiver mesh {obj.name}: {owned[obj]} and {label}')
            owned[obj]=label
        resolved[label]=selected
    return resolved


def filter_occluders(objects, selectors=None, *, projection_label, available_objects=None):
    """Exclude only named cover components; never mutate scene visibility.

    Empty selectors preserve historical source-node-only projection exactly.
    Available objects may include hidden components when reviewing an already
    revealed scene, but each selector must still identify exactly one component.
    """
    objects=list(objects)
    if not selectors:
        return objects
    patch = ENDPOINT_COVER_PATCHES.get(projection_label)
    if patch is None and not projection_label.startswith('interior-'):
        raise ValueError('Cover component exclusion requires an interior projection label')
    patch = patch or projection_label.removeprefix('interior-')
    catalog=list(available_objects) if available_objects is not None else objects
    excluded=set()
    for selector in selectors:
        if set(selector)!={'source_node','projection_component','patch_id'}:
            raise ValueError('Cover selector requires source_node, projection_component and patch_id')
        if selector['patch_id']!=patch or any(not isinstance(v,str) or not v for v in selector.values()):
            raise ValueError('Cover selector does not match the projection patch')
        matches=[o for o in catalog if o.get('source_node')==selector['source_node']
                 and o.get('projection_component')==selector['projection_component']]
        if len(matches)!=1:
            raise ValueError(f'Cover selector must identify one component: {selector}, found {len(matches)}')
        obj=matches[0]
        if obj.get('reveal_component_role')!='removable-cover' or obj.get('reveal_component_patch_id')!=patch:
            raise ValueError('Selected component is not an authored cover for this patch')
        excluded.add(obj)
    return [o for o in objects if o not in excluded]


def validate_occluder_nodes(requested, visible_objects, available_objects,
                            selectors=None, *, projection_label):
    """Allow a hidden node only when its every mesh is an excluded room cover."""
    if requested is None:
        return
    missing = set(requested) - {obj.get('source_node') for obj in visible_objects}
    if not missing:
        return
    catalog = list(available_objects)
    hidden = [obj for obj in catalog if obj.type == 'MESH'
              and obj.get('source_node') in missing]
    if (missing - {obj.get('source_node') for obj in hidden}
            or any(not obj.hide_render for obj in hidden)
            or filter_occluders(hidden, selectors, projection_label=projection_label,
                                available_objects=catalog)):
        raise ValueError('Unknown projection nodes: ' + str(missing))
