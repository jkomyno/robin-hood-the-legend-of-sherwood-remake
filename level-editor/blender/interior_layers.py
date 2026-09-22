"""Annotate projection receivers without equating sight blockers with removable walls.

Run annotate_layers(layers_json) after grouping. This only writes metadata; it
never hides geometry. Render/cutaway visibility is a separate authored decision.
The manifest preserves each patch's independent mask and sight state changes.
"""
import json
import hashlib
import re
from pathlib import Path

# Reviewed interior geometry in the Derby catalog. Overlap alone is deliberately
# not an assignment: exterior walls and furniture can occupy the same pixels.
DERBY_INTERIORS = {
    "patch-000": [*range(223, 228), *range(229, 239)],
    "patch-001": [239, 240],
    "patch-002": [186, *range(241, 249)],
    "patch-003": [252, 253],
}

# Source-image review of the covered/revealed pairs. These lists describe
# visibility for projection onto the receivers below, not a cutaway mesh state.
# In particular, a wall can retain its upper parapet while only a lower portion
# is painted away; whole-object hiding cannot represent that distinction.
DERBY_RETAINED_PROJECTION_OCCLUDERS = {
    "patch-000": [143, 145, 180],
    "patch-001": [130, 134, 137, 138, 139, 145],
    "patch-002": [81, 82, 190, 193, 194, 200, 201, 207, 208, 209],
    "patch-003": [249, 250, 251, 254, 255, 256, 257, 258,
                  259, 260, 261, 262, 263, 264, 265, 266],
}

DERBY_OCCLUDER_AUDIT = {
    "patch-000": {
        "status": "partial-conservative",
        "notes": "Entrance arch and exterior buttresses remain around the hall opening. Roof and facade are partially cut away; their full meshes are not approved occluders.",
        "partial_cover_nodes": [146, 148, 149, 150, 151, 179, 182, 228],
    },
    "patch-001": {
        "status": "partial-conservative",
        "notes": "Tower terrace, rooftop stair/turrets and connecting buttress remain. The opening cuts only a portion of the tower facade, so its whole mesh must not block the revealed room.",
        "partial_cover_nodes": [132],
    },
    "patch-002": {
        "status": "partial-conservative",
        "notes": "Hall roof, upper floor, roof parapet, side turret, lower buttress and exterior access stair remain. Windowed facade portions disappear while their top battlements survive; these mixed meshes need a face-level cutaway review.",
        "partial_cover_nodes": [183, 185, 188, 189, 191, 211, 212],
    },
    "patch-003": {
        "status": "reviewed-for-upper-floor-receivers",
        "notes": "Upper terrace receivers252/253 remain behind their surrounding masonry and battlements. Retain the shell in their projection BVH, preventing crenellation pixels from being painted onto the terrace a second time. The lower chamber opening is a separate partial facade cutaway, not permission to remove these occluders from the upper-floor pass.",
        "partial_cover_nodes": [257, 263],
    },
}


def projection_occluders(manifest, available_nodes):
    """Return explicit per-patch receiver and retained-shell occluder nodes.

    Available nodes allow an isolated asset packet to use its existing context.
    Receivers and retained occluders are filtered to that context; the caller
    must separately validate that every requested receiver exists. Unreviewed
    exterior meshes are not silently added, and sight-state lists never decide
    which rendered surfaces disappear. Consult ``projection_occluder_audit``
    for partial covers and remaining face-level review work.
    """
    receivers = projection_receivers(manifest)
    available = set(available_nodes)
    if manifest['map'].casefold() != 'derby':
        reviews = projection_reviews(manifest)
        result = {patch: sorted(set(nodes) | set(reviews[patch]['retained_occluder_nodes']) |
                               set(reviews[patch].get('occluder_additions', {}).get('interior-'+patch, [])))
                  for patch, nodes in receivers.items()}
        missing = {node for nodes in result.values() for node in nodes} - available
        if missing:
            raise ValueError(f'Missing authored projection nodes: {sorted(missing)}')
        return result
    additions=projection_occluder_additions(manifest)
    return {patch: sorted((set(nodes) | set(additions.get('interior-'+patch,[])) | {
        f"building-{n:03d}" for n in DERBY_RETAINED_PROJECTION_OCCLUDERS[patch]
    }) & available) for patch, nodes in receivers.items()}


def projection_occluder_audit(manifest):
    """Report limitations separately from operational projection node lists."""
    projection_receivers(manifest)
    if manifest['map'].casefold() != 'derby':
        return {patch: {'status': 'reviewed', 'reviewer': review['reviewer'],
                        'notes': review['evidence'],
                        'retained_occluders': review['retained_occluder_nodes'],
                        'partial_cover_nodes': review['partial_cover_nodes'],
                        'exclude_occluder_components': review['exclude_occluder_components'],
                        'scope': 'projection-only; not runtime geometry visibility'}
                for patch, review in projection_reviews(manifest).items()}
    result={patch: {
        **audit,
        "retained_occluders": [f"building-{n:03d}" for n in DERBY_RETAINED_PROJECTION_OCCLUDERS[patch]],
        "partial_cover_nodes": [f"building-{n:03d}" for n in audit["partial_cover_nodes"]],
        "removed_whole_cover_nodes": [],
        "scope": "projection-only; not runtime geometry visibility",
    } for patch, audit in DERBY_OCCLUDER_AUDIT.items()}
    for patch,review in projection_reviews(manifest).items():
        result[patch].update(status='reviewed-component-cover',
            notes=review.get('evidence','Reviewed component cover and regional receivers'),
            exclude_occluder_components=review['exclude_occluder_components'])
    return result


def projection_receivers(manifest):
    if manifest["map"].casefold() != "derby":
        return {patch: list(review['receiver_nodes'])
                for patch, review in projection_reviews(manifest).items()
                if review.get('role', 'interior') == 'interior'}
    result={patch: [f"building-{n:03d}" for n in nodes]
            for patch, nodes in DERBY_INTERIORS.items()}
    for patch,review in projection_reviews(manifest).items():
        result[patch]=list(review['receiver_nodes'])
    return result


def projection_reviews(manifest):
    """Opt-in reviewed partitions; absent reviews preserve existing manifests."""
    reviews=manifest.get('projection_reviews',{})
    if not isinstance(reviews,dict):raise ValueError('Projection reviews must be an object')
    if manifest['map'].casefold() != 'derby':
        return _authored_projection_reviews(manifest, reviews)
    for patch,review in reviews.items():
        if manifest['map'].casefold()!='derby' or patch!='patch-003':
            raise ValueError('No reviewed component projection for this map/patch')
        if review.get('version')!=1 or review.get('reviewed') is not True or review.get('patch_id')!=patch:
            raise ValueError('Invalid or unreviewed projection override')
        if review.get('receiver_nodes')!=['building-249','building-252','building-253','building-263','building-265']:
            raise ValueError('Unexpected upper gate chamber receiver partition')
        if review.get('exclude_occluder_components')!=[{
            'source_node':'building-257','projection_component':'upper-chamber-removable-cover','patch_id':patch},
            {'source_node':'building-263','projection_component':'upper-chamber-west-removable-cover','patch_id':patch}]:
            raise ValueError('Unexpected upper gate removable cover selector')
        expected={'exterior':[{'source_node':'building-263','projection_components':['upper-chamber-west-removable-cover'],'patch_id':patch}],
                  'interior-patch-003':[{'source_node':'building-263','projection_components':['upper-chamber-west-retained-wall'],'patch_id':patch}]}
        if review.get('receiver_components')!=expected:
            raise ValueError('Unexpected upper gate component receiver partition')
        additions=review.get('occluder_additions')
        if additions is not None and additions!={'exterior':['building-249','building-252','building-253','building-263','building-265'],
                                                 'interior-patch-003':['building-267']}:
            raise ValueError('Unexpected upper gate physical occluder additions')
    return reviews


def _authored_projection_reviews(manifest, reviews):
    """Require reviewed ownership for every base reveal; never derive it from sight lists.

    Each projection_reviews entry binds receiver_nodes, retained_occluder_nodes,
    partial_cover_nodes, reviewer/evidence, source_sha256 and alpha_sha256 to its
    patch_id. Component selectors use the same contract as the projection baker.
    Empty component collections explicitly select whole source nodes.
    A reviewed role='non-interior' classifies a trigger or integrated state patch
    with empty node/component lists; it does not authorize an interior pass.
    """
    patches = manifest.get('patches')
    if not isinstance(patches, list):
        raise ValueError('Authored projection requires an explicit patch inventory')
    ids = [p['id'] for p in patches]
    if len(ids) != len(set(ids)) or set(reviews) != set(ids):
        raise ValueError('Authored projection reviews must cover every base patch exactly once')

    def nodes(value, label, nonempty=False):
        if (not isinstance(value, list) or (nonempty and not value) or
                any(not isinstance(n, str) or not re.fullmatch(r'building-\d{3,}', n) for n in value) or
                len(value) != len(set(value))):
            raise ValueError('Invalid authored node list: '+label)

    for patch, review in reviews.items():
        if (not isinstance(review, dict) or review.get('version') != 1 or
                review.get('reviewed') is not True or review.get('patch_id') != patch):
            raise ValueError('Invalid or unreviewed authored projection: '+patch)
        for key in ('reviewer', 'evidence'):
            if not isinstance(review.get(key), str) or not review[key].strip():
                raise ValueError('Authored projection requires '+key)
        role = review.get('role', 'interior')
        if role not in ('interior', 'non-interior'):
            raise ValueError('Invalid authored projection role')
        if role == 'non-interior':
            if any(review.get(key) != [] for key in ('receiver_nodes', 'retained_occluder_nodes',
                                                     'partial_cover_nodes', 'exclude_occluder_components')):
                raise ValueError('Non-interior classification cannot assign projection nodes')
            if review.get('receiver_components') != {} or review.get('occluder_additions', {}) != {}:
                raise ValueError('Non-interior classification cannot assign projection components')
            continue
        for key in ('source_sha256', 'alpha_sha256'):
            if not isinstance(review.get(key), str) or not re.fullmatch('[0-9a-f]{64}', review[key]):
                raise ValueError('Authored projection requires an exact '+key)
        for key in ('receiver_nodes', 'retained_occluder_nodes', 'partial_cover_nodes'):
            nodes(review.get(key), key, nonempty=key == 'receiver_nodes')
        exclusions = review.get('exclude_occluder_components')
        if not isinstance(exclusions, list):
            raise ValueError('Authored projection requires explicit cover exclusions')
        seen = set()
        for selector in exclusions:
            if (not isinstance(selector, dict) or
                    set(selector) != {'source_node', 'projection_component', 'patch_id'} or
                    selector['patch_id'] != patch or
                    not isinstance(selector['projection_component'], str) or not selector['projection_component']):
                raise ValueError('Invalid authored cover selector')
            nodes([selector['source_node']], 'cover selector')
            identity = (selector['source_node'], selector['projection_component'])
            if identity in seen:
                raise ValueError('Duplicate authored cover selector')
            seen.add(identity)
        components = review.get('receiver_components')
        if not isinstance(components, dict):
            raise ValueError('Authored projection requires explicit receiver components')
        for label, selectors in components.items():
            if label not in ('exterior', 'interior-'+patch) or not isinstance(selectors, list):
                raise ValueError('Invalid authored receiver projection layer')
            selected_nodes = set()
            for selector in selectors:
                if (not isinstance(selector, dict) or
                        set(selector) != {'source_node', 'projection_components', 'patch_id'} or
                        selector['patch_id'] != patch):
                    raise ValueError('Invalid authored receiver selector')
                node = selector['source_node']
                nodes([node], 'receiver selector')
                parts = selector['projection_components']
                if (node in selected_nodes or not isinstance(parts, list) or not parts or
                        any(not isinstance(p, str) or not p for p in parts) or len(parts) != len(set(parts))):
                    raise ValueError('Invalid or duplicate authored receiver components')
                if label == 'interior-'+patch and node not in review['receiver_nodes']:
                    raise ValueError('Interior component is outside reviewed receivers')
                selected_nodes.add(node)
        additions = review.get('occluder_additions', {})
        if not isinstance(additions, dict):
            raise ValueError('Invalid authored occluder additions')
        for label, values in additions.items():
            if label not in ('exterior', 'interior-'+patch):
                raise ValueError('Invalid authored occluder projection layer')
            nodes(values, 'occluder additions')
    return reviews


def validate_projection_reviews(manifest, directory):
    """Bind changed ownership to the exact revealed artwork and patch alpha."""
    for patch,review in projection_reviews(manifest).items():
        if review.get('role', 'interior') == 'non-interior':
            continue
        record=next(p for p in manifest['patches'] if p['id']==patch)
        for key,path in [('source_sha256',manifest['sources']['interior']),
                         ('alpha_sha256',record['graphic']['alpha'])]:
            actual=hashlib.sha256((Path(directory)/path).read_bytes()).hexdigest()
            if review.get(key)!=actual:raise ValueError('Reviewed projection source changed: '+key)


def projection_component_exclusions(manifest):
    return {patch:review['exclude_occluder_components']
            for patch,review in projection_reviews(manifest).items()}


def projection_receiver_components(manifest):
    result={}
    for review in projection_reviews(manifest).values():
        for label,selectors in review['receiver_components'].items():
            result.setdefault(label,[]).extend(selectors)
    return result


def projection_occluder_additions(manifest):
    result={}
    for review in projection_reviews(manifest).values():
        for label,nodes in review.get('occluder_additions',{}).items():
            result.setdefault(label,[]).extend(nodes)
    return result


def annotate_layers(manifest_path):
    import bpy
    path = Path(manifest_path).resolve()
    manifest = json.loads(path.read_text())
    receivers = projection_receivers(manifest)
    component_receivers=projection_receiver_components(manifest)
    working = bpy.data.collections.get(f"{manifest['map']} Working")
    if working is None:
        raise ValueError(f"Missing working collection for {manifest['map']}")
    objects = [o for o in working.all_objects if o.type == 'MESH' and o.get('source_node')]
    available = {o['source_node'] for o in objects}
    missing = {n for nodes in receivers.values() for n in nodes} - available
    if missing:
        raise ValueError(f"Missing authored interior receivers: {sorted(missing)}")
    if manifest['map'].casefold() != 'derby':
        validate_projection_reviews(manifest, path.parent)
        reviews = projection_reviews(manifest)
        declared = {node for review in reviews.values()
                    for key in ('receiver_nodes', 'retained_occluder_nodes', 'partial_cover_nodes')
                    for node in review[key]}
        declared.update(node for nodes in projection_occluder_additions(manifest).values() for node in nodes)
        if declared - available:
            raise ValueError(f'Missing authored projection nodes: {sorted(declared - available)}')
    occluders = projection_occluders(manifest, available)
    working['reveal_manifest_path'] = str(path)
    annotated = []
    for obj in objects:
        node = obj['source_node']
        interior=[]
        for patch,nodes in receivers.items():
            if node not in nodes:continue
            selector=next((s for s in component_receivers.get('interior-'+patch,[])
                           if s['source_node']==node),None)
            if selector is None or obj.get('projection_component') in selector['projection_components']:
                interior.append(patch)
        candidates = [p['id'] for p in manifest['patches']
                      if any(c['source_node'] == node for c in p['coverage_candidates'])]
        before = [p['id'] for p in manifest['patches'] if node in p['sight_before']]
        after = [p['id'] for p in manifest['patches'] if node in p['sight_after']]
        obj['projection_layer'] = 'interior' if interior else 'exterior'
        obj['reveal_role'] = 'interior' if interior else ('ambiguous' if candidates else 'shared')
        obj['reveal_patch_ids'] = interior
        obj['reveal_candidate_patch_ids'] = candidates
        obj['sight_patch_before_ids'] = before
        obj['sight_patch_after_ids'] = after
        obj['projection_layer_manifest'] = str(path)
        if interior:
            annotated.append({'name': obj.name, 'source_node': node, 'patches': interior})
    bpy.context.scene['projection_layer_manifest'] = str(path)
    report = {'map': manifest['map'], 'interior_receivers': receivers,
              'projection_occluders': occluders,
              'projection_occluder_audit': projection_occluder_audit(manifest),
              'annotated_meshes': annotated,
              'notes': 'Sight activation and rendered cutaway geometry are independent. Candidate overlap does not authorize removal.'}
    (path.parent / 'receiver-assignments.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def interior_preview(manifest_path, patch_id):
    """Temporary diagnostic view of reviewed receivers, restoring all visibility.

    Use `with interior_preview(path, 'patch-000'):` around render_views(...).
    This is an isolated furniture/interior inspection, not a proposed in-game
    cutaway: exterior candidate walls are intentionally not classified as removed.
    """
    from contextlib import contextmanager

    @contextmanager
    def preview():
        import bpy
        manifest = json.loads(Path(manifest_path).read_text())
        nodes = set(projection_receivers(manifest)[patch_id])
        # This upper slab encloses the dining hall; omit it only for inspection.
        if manifest['map'].casefold() == 'derby' and patch_id == 'patch-000':
            nodes.discard('building-228')
        working = bpy.data.collections[f"{manifest['map']} Working"]
        objects = [o for o in working.all_objects if o.type == 'MESH']
        visibility = [(o, o.hide_render) for o in objects]
        try:
            for obj, hidden in visibility:
                obj.hide_render = hidden or obj.get('source_node') not in nodes
            bpy.context.view_layer.update()
            yield nodes
        finally:
            for obj, hidden in visibility:
                obj.hide_render = hidden
            bpy.context.view_layer.update()
    return preview()
