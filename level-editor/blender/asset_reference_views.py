"""Build focused worker evidence without altering frozen projection references."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image

from interior_layers import projection_receivers


def state_objects(objects, asset_id, patch_id, review, state):
    """Select an authored display state without inferring cutaways from projection roles."""
    if (review.get('version') != 1 or review.get('reviewed') is not True or
            any(not isinstance(review.get(k), str) or not review[k].strip()
                for k in ('reviewer', 'evidence'))):
        raise ValueError('State visibility requires explicit reviewed evidence')
    if state not in ('covered', 'revealed'):
        raise ValueError('Unknown display state')
    definition = review.get(state)
    if not isinstance(definition, dict) or set(definition) != {'hidden_nodes', 'hidden_components'}:
        raise ValueError('State visibility requires explicit node and component lists')
    nodes, components = definition['hidden_nodes'], definition['hidden_components']
    if (not isinstance(nodes, list) or any(not isinstance(n, str) or not n for n in nodes) or
            len(nodes) != len(set(nodes)) or not isinstance(components, list)):
        raise ValueError('Invalid state visibility selection')
    meshes = [o for o in objects if o.type == 'MESH']
    if set(nodes) - {o.get('source_node') for o in meshes}:
        raise ValueError('State visibility references missing source nodes')
    excluded = {o for o in meshes if o.get('source_node') in nodes}
    seen = set()
    for selector in components:
        if (not isinstance(selector, dict) or
                set(selector) != {'source_node', 'projection_component', 'patch_id'} or
                selector['patch_id'] != patch_id):
            raise ValueError('Invalid state component selector')
        identity = (selector['source_node'], selector['projection_component'])
        if identity in seen or not all(isinstance(v, str) and v for v in identity):
            raise ValueError('Invalid or duplicate state component selector')
        seen.add(identity)
        matches = [o for o in meshes if (o.get('source_node'), o.get('projection_component')) == identity]
        if len(matches) != 1 or matches[0].get('reveal_component_patch_id') != patch_id:
            raise ValueError('State selector must identify one authored patch component')
        excluded.add(matches[0])
    selected = [o for o in meshes if o.get('asset_group') == asset_id and not o.hide_render and o not in excluded]
    if not selected:
        raise ValueError('State visibility leaves no visible asset geometry')
    return selected


def render_states(workspace, output, *, frame_manifest=None):
    """Render supplemental paired sheets using explicit state display authority.

    Frozen input cameras/crop are retained. This does not replace modified/ or
    assign materials, and refuses missing visibility reviews instead of treating
    retained projection occluders as authorization to hide surrounding shells.
    """
    import bpy
    import copy
    from refinement_workspace import _review_layers, _validated_projection, _validated_masks
    from refinement_review import render_review
    from interior_layers import projection_reviews, validate_projection_reviews

    workspace, output = Path(workspace).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    config = json.loads((workspace / 'workspace.json').read_text())
    path = Path(config['projection_manifest'])
    manifest = _validated_projection(config)
    mask_evidence = _validated_masks(config)
    validate_projection_reviews(manifest, path.parent)
    owned = set(config['part_ids'])
    patches = [patch for patch, nodes in projection_receivers(manifest).items() if owned.intersection(nodes)]
    if not patches:
        raise ValueError('Asset has no reviewed interior state')
    objects = list(bpy.data.collections[config['collection_name']].all_objects)
    reviews = projection_reviews(manifest)
    selections = {}
    for patch in patches:
        visibility = reviews[patch].get('render_visibility', {})
        for state in ('covered', 'revealed'):
            selections[patch, state] = state_objects(objects, config['asset_id'], patch, visibility, state)
    definitions = _review_layers(config)
    framing_path = Path(frame_manifest) if frame_manifest else workspace / 'input/views.json'
    framing = json.loads(framing_path.read_text())
    output.mkdir(parents=True)
    records = []
    for patch in patches:
        for state, source_key in (('covered', 'exterior'), ('revealed', 'interior')):
            source = (path.parent / manifest['sources'][source_key]).resolve(strict=True)
            frame = copy.deepcopy(framing)
            # Only context artwork changes; camera transforms and crop stay frozen.
            frame['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
            target = output / patch / state
            result = render_review(target, scene_name=config['scene_name'],
                                   collection_name=config['collection_name'], asset_id=config['asset_id'],
                                   source_path=source, frame_manifest=frame,
                                   projection_layers=definitions,
                                   source_mask_manifest=config.get('source_mask_manifest'),
                                   render_object_names=[o.name for o in selections[patch, state]],
                                   allow_projection_revision=True,
                                   allow_mask_revision=bool(mask_evidence))
            records.append(dict(patch_id=patch, state=state, path=str(target),
                                visibility_review=reviews[patch]['render_visibility'],
                                view_sha256=hashlib.sha256((target/'views.json').read_bytes()).hexdigest(),
                                object_names=result['object_names']))
    report = dict(version=1, asset_id=config['asset_id'], states=records,
                  projection_manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  working_mask_evidence=mask_evidence,
                  framing_manifest=str(framing_path),
                  framing_sha256=hashlib.sha256(framing_path.read_bytes()).hexdigest(),
                  limitations=['Display visibility is authored separately from texture ownership.',
                               'Pending partial-shell geometry remains visible unless explicitly excluded.'])
    (output/'states.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def prepare(workspace):
    workspace = Path(workspace).resolve()
    config = json.loads((workspace / 'workspace.json').read_text())
    views = json.loads((workspace / 'input/views.json').read_text())
    reference = workspace / 'reference'
    layers = json.loads((reference / 'layers.json').read_text())
    owned = set(config['part_ids'])
    roles = projection_receivers(layers)
    selected = {patch for patch, nodes in roles.items() if owned.intersection(nodes)}
    bounds = views['context_crop']
    box = tuple(bounds[k] for k in ('left', 'top', 'right', 'bottom'))
    output = workspace / 'asset-reference'
    output.mkdir(exist_ok=False)
    evidence = []

    def crop(source, name, role):
        source = Path(source).resolve(strict=True)
        with Image.open(source) as original:
            if not (0 <= box[0] < box[2] <= original.width and
                    0 <= box[1] < box[3] <= original.height):
                raise ValueError(f'Invalid source bounds for {source}')
            original.crop(box).save(output / name)
        evidence.append(dict(file=name, role=role, source=str(source),
                             source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                             source_crop=list(box)))

    crop(views['source_image'], 'source-context.png', 'source state used for exterior review')
    crop(reference / layers['sources']['exterior'], 'covered.png', 'covered exterior')
    if selected:
        crop(reference / layers['sources']['interior'], 'revealed.png', 'revealed interior')
    patches = []
    for patch in layers['patches']:
        if patch['id'] not in selected:
            continue
        graphic = patch.get('graphic')
        if not graphic:
            raise ValueError(f'Missing graphic for reviewed interior {patch["id"]}')
        directory = output / patch['id']
        directory.mkdir()
        for kind in ('image', 'alpha'):
            source = reference / graphic[kind]
            destination = directory / f'{kind}.png'
            shutil.copy2(source, destination)
        patches.append(dict(id=patch['id'], name=patch['name'],
                            bbox=graphic['bbox'],
                            owned_interior_nodes=sorted(owned.intersection(roles[patch['id']])),
                            image=f'{patch["id"]}/image.png',
                            alpha=f'{patch["id"]}/alpha.png'))
    # Mission state membership is separate from authored interior receiver roles.
    # Preserve explicit cross-asset state dependencies as links, not ownership.
    mission_states = []
    for patch in layers.get('mission_patches', []):
        affected = owned.intersection(patch.get('sight_before', []) + patch.get('sight_after', []))
        if affected:
            mission_states.append(dict(id=patch['id'], name=patch['name'],
                                       affected_owned_nodes=sorted(affected),
                                       relation='sight-state dependency; not inferred visual ownership',
                                       backing_manifest=str(reference / 'layers.json')))
    report = dict(asset_id=config['asset_id'], source_origin=list(box[:2]),
                  evidence=evidence, interior_patches=patches,
                  mission_state_dependencies=mission_states,
                  backing_reference=str(reference),
                  limitations=['A crop can include neighboring context; pixels are not an ownership mask.',
                               'Interior patch selection uses reviewed receiver assignments, not bounding-box overlap.',
                               'Mission visual dependencies still require review of the backing manifest.'])
    (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    (output / 'README.md').write_text(
        f'# Focused reference: {config["asset_id"]}\n\n'
        'Start with source-context.png and covered.png. For interior assets, compare\n'
        'revealed.png and the listed patch image/alpha pairs. Crops keep original\n'
        'pixels and share the same map-space origin in manifest.json.\n\n'
        'Only patches with reviewed interior receivers belonging to this asset\n'
        'are included. Neighboring artwork in a crop is context, not owned geometry.\n'
        'The full reference/ folder is projection backing data, not a list of\n'
        'assets or patches assigned to this worker. Consult its layers.json for\n'
        'mission-state dependencies and any additional occlusion investigation.\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.workspace), indent=2))
