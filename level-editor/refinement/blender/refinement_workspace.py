"""Prepare and validate independent, source-only Blender refinement workspaces.

Run in a background Blender process, never the shared interactive scene. A worker
owns one logical asset; the surrounding scene remains available for occlusion.
"""
import sys as _refinement_sys
from pathlib import Path as _RefinementPath
_refinement_legacy = str(_RefinementPath(__file__).resolve().parents[2] / 'blender')
if _refinement_legacy not in _refinement_sys.path:
    _refinement_sys.path.append(_refinement_legacy)

import argparse
import hashlib
import json
import shutil
import shlex
import sys
import uuid
from pathlib import Path


def _json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _files(directory):
    return {str(p.relative_to(directory)): _sha(p)
            for p in sorted(Path(directory).rglob("*")) if p.is_file()}


def _copy_manifest_images(value, source_dir, destination_dir):
    """Copy every referenced patch/frame image, including nested mission assets."""
    if isinstance(value, dict):
        return {key: _copy_manifest_images(item, source_dir, destination_dir)
                for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_manifest_images(item, source_dir, destination_dir) for item in value]
    if isinstance(value, str) and Path(value).suffix.lower() in (".png", ".webp", ".jpg", ".jpeg"):
        relative = Path(value)
        source = (source_dir / relative).resolve(strict=True)
        if relative.is_absolute() or ".." in relative.parts:
            relative = Path("external") / (_sha(source)[:12] + "-" + source.name)
        destination = destination_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and _sha(destination) != _sha(source):
            raise ValueError(f"Conflicting reference image name: {relative}")
        shutil.copy2(source, destination)
        return relative.as_posix()
    return value


def _absolute_manifest_images(value, directory):
    if isinstance(value, dict):
        return {key: _absolute_manifest_images(item, directory) for key, item in value.items()}
    if isinstance(value, list):
        return [_absolute_manifest_images(item, directory) for item in value]
    if isinstance(value, str) and Path(value).suffix.lower() in (".png", ".webp", ".jpg", ".jpeg"):
        return str((directory / value).resolve(strict=True))
    return value


def initialize_working_projection(workspace_dir):
    """Migrate an existing worker to editable reviews while retaining frozen references."""
    workspace = Path(workspace_dir).resolve()
    config_path = workspace / 'workspace.json'
    config = json.loads(config_path.read_text())
    if not config.get('projection_manifest'):
        raise ValueError('Workspace has no projection manifest')
    frozen = workspace / 'reference/layers.json'
    destination = workspace / 'projection-layers.json'
    if Path(config['projection_manifest']).resolve() == destination:
        return str(destination)
    if Path(config['projection_manifest']).resolve() != frozen:
        raise ValueError('Cannot migrate an unexpected projection manifest')
    if config.get('reference_files') and _files(workspace/'reference') != config['reference_files']:
        raise ValueError('Immutable reference files changed before migration')
    if destination.exists():
        raise FileExistsError(destination)
    _json(destination, _absolute_manifest_images(json.loads(frozen.read_text()), frozen.parent))
    config['projection_manifest'] = str(destination)
    _json(config_path, config)
    return str(destination)


def _validated_projection(config):
    """Allow authored review edits only; source/state inventory remains frozen."""
    path = Path(config['projection_manifest']).resolve()
    manifest = json.loads(path.read_text())
    absolute = _absolute_manifest_images(manifest, path.parent)
    frozen_path = Path(config['source_path']).parent / 'layers.json'
    frozen = _absolute_manifest_images(json.loads(frozen_path.read_text()), frozen_path.parent)
    if ({k: v for k, v in absolute.items() if k != 'projection_reviews'} !=
            {k: v for k, v in frozen.items() if k != 'projection_reviews'}):
        raise ValueError('Working projection changed frozen source or state inventory')
    from interior_layers import validate_projection_reviews
    validate_projection_reviews(manifest, path.parent)
    def assignments(value, trail=(), result=None):
        result = {} if result is None else result
        if isinstance(value, dict):
            if 'source_node' in value:
                result.setdefault(value['source_node'], []).append((trail, json.dumps(value, sort_keys=True)))
            else:
                for key, item in value.items():
                    assignments(item, trail+(key,), result)
        elif isinstance(value, list):
            for item in value:
                assignments(item, trail, result)
        elif isinstance(value, str) and value.startswith('building-') and value[9:].isdigit():
            result.setdefault(value, []).append((trail, value))
        return {node: sorted(records) for node, records in result.items()}
    before = assignments(frozen.get('projection_reviews', {}))
    after = assignments(absolute.get('projection_reviews', {}))
    changed_foreign = {node for node in before.keys() | after.keys()
                       if before.get(node) != after.get(node)} - set(config['part_ids'])
    if changed_foreign:
        raise ValueError('Working projection reassigned outside-asset nodes: '+str(sorted(changed_foreign)))
    from workspace_components import validated_scope, owns_assignment
    scope = validated_scope(config)
    if scope:
        def scoped_records(value, trail=(), result=None):
            result = {} if result is None else result
            if isinstance(value, dict):
                if 'source_node' in value:
                    selectors = value.get('projection_components', [value.get('projection_component')])
                    for component in selectors:
                        key = (value['source_node'], component)
                        normalized = dict(value)
                        if 'projection_components' in normalized:
                            normalized['projection_components'] = [component]
                        result.setdefault(key, []).append((trail, json.dumps(normalized, sort_keys=True)))
                else:
                    for key, item in value.items():
                        scoped_records(item, trail+(key,), result)
            elif isinstance(value, list):
                for item in value:
                    scoped_records(item, trail, result)
            elif isinstance(value, str) and value in scope['split_sources']:
                result.setdefault((value, None), []).append((trail, value))
            return {key: sorted(records) for key, records in result.items()}
        old_records = scoped_records(frozen.get('projection_reviews', {}))
        new_records = scoped_records(absolute.get('projection_reviews', {}))
        for key in old_records.keys() | new_records.keys():
            if (old_records.get(key) != new_records.get(key) and
                    not owns_assignment(config, 'source_node', key[0], key[1])):
                raise ValueError('Working projection changed foreign or node-wide component assignment')
    return manifest


def _freeze_masks(workspace, config):
    """Freeze assignment origin plus every native bitmap, including unused masks."""
    path = Path(config['source_mask_manifest']).resolve()
    manifest = json.loads(path.read_text())
    inventory_path = (path.parent / manifest['mask_inventory']).resolve(strict=True)
    inventory = json.loads(inventory_path.read_text())
    native = {str(inventory_path): _sha(inventory_path)}
    for record in inventory['masks']:
        relative = record.get('png') if 'png' in record else record['folder']+'/mask.png'
        if relative is not None:
            bitmap = (inventory_path.parent / relative).resolve(strict=True)
            native[str(bitmap)] = _sha(bitmap)
    manifest['mask_inventory'] = str(inventory_path)
    directory = Path(workspace)/'mask-reference'
    directory.mkdir(exist_ok=False)
    _json(directory/'assignments.json', manifest)
    _json(directory/'native-hashes.json', native)
    config['mask_reference_files'] = _files(directory)
    config['mask_reference'] = str(directory)


def initialize_working_masks(workspace_dir):
    """Freeze legacy mask evidence only if the current assignments still match input."""
    workspace = Path(workspace_dir).resolve()
    config = json.loads((workspace/'workspace.json').read_text())
    if config.get('mask_reference'):
        _validated_masks(config)
        return config['mask_reference']
    path = Path(config['source_mask_manifest']).resolve()
    views = json.loads((workspace/'input/views.json').read_text())
    expected = views.get('source_mask_evidence', {})
    from occlusion_constraints import evidence_record
    if expected != evidence_record(path):
        raise ValueError('Cannot freeze legacy masks after initial evidence changed')
    _freeze_masks(workspace, config)
    _json(workspace/'workspace.json', config)
    return config['mask_reference']


def _validated_masks(config, objects=None):
    if not config.get('source_mask_manifest'):
        return None
    if not config.get('mask_reference'):
        raise ValueError('Initialize immutable mask evidence before editing this legacy workspace')
    directory = Path(config['mask_reference'])
    if _files(directory) != config['mask_reference_files']:
        raise ValueError('Immutable mask assignment origin changed')
    native = json.loads((directory/'native-hashes.json').read_text())
    if any(_sha(path) != digest for path, digest in native.items()):
        raise ValueError('Native mask inventory or bitmap changed')
    frozen = json.loads((directory/'assignments.json').read_text())
    path = Path(config['source_mask_manifest'])
    working = json.loads(path.read_text())
    working['mask_inventory'] = str((path.parent/working['mask_inventory']).resolve(strict=True))
    def authority(value):
        return {**value, 'projections': {label: {k: v for k, v in projection.items() if k != 'assignments'}
                                        for label, projection in value['projections'].items()}}
    if authority(working) != authority(frozen):
        raise ValueError('Working masks changed native inventory, projection source or state')
    records = {record['index']: record for record in json.loads(Path(working['mask_inventory']).read_text())['masks']}
    def assignments(projection, validate_objects=False):
        result = {}
        for entry in projection['assignments']:
            targets = [key for key in ('source_node', 'asset_group') if key in entry]
            if (entry.get('reviewed') is not True or len(targets) != 1 or
                    not isinstance(entry[targets[0]], str) or not entry[targets[0]]):
                raise ValueError('Mask assignments require one reviewed explicit target')
            key = (targets[0], entry[targets[0]], entry.get('projection_component'))
            if key[2] is not None and (targets[0] != 'source_node' or not isinstance(key[2], str) or not key[2].strip()):
                raise ValueError('Invalid mask component selector')
            if key in result:
                raise ValueError('Duplicate mask target')
            if validate_objects and objects is not None and key[2] is not None:
                matches = [obj for obj in objects if obj.type == 'MESH' and
                           obj.get('source_node') == key[1] and obj.get('projection_component') == key[2]]
                if len(matches) != 1:
                    raise ValueError('Mask component must identify exactly one scene mesh')
            indices, exclusions = entry.get('mask_indices'), entry.get('exclude_mask_indices', [])
            if not isinstance(indices, list) or not indices or not isinstance(exclusions, list):
                raise ValueError('Mask assignment requires explicit indices')
            if exclusions and (entry.get('exclusions_reviewed') is not True or not str(entry.get('exclusion_reason', '')).strip()):
                raise ValueError('Mask exclusions require explicit review and reason')
            for index in indices+exclusions:
                if type(index) is not int or index not in records or records[index].get('png', 'legacy') is None:
                    raise ValueError('Unknown or degenerate native mask index')
            result[key] = entry
        return result
    for label, projection in working['projections'].items():
        before, after = assignments(frozen['projections'][label]), assignments(projection, validate_objects=True)
        for key in before.keys() | after.keys():
            from workspace_components import owns_assignment
            owned = owns_assignment(config, key[0], key[1], key[2])
            if not owned and before.get(key) != after.get(key):
                raise ValueError('Working masks changed another asset assignment')
    return {'working_sha256': _sha(path), 'native_hashes_sha256': _sha(directory/'native-hashes.json'),
            'initial_assignments_sha256': _sha(directory/'assignments.json')}


def _geometry(obj, protect_appearance=False, appearance_cache=None):
    value = {"type": obj.type, "matrix": [list(row) for row in obj.matrix_world],
             "parent": obj.parent.name if obj.parent else None,
             "hide_render": obj.hide_render, "hide_viewport": obj.hide_viewport,
             "source_node": obj.get("source_node"), "asset_group": obj.get("asset_group")}
    if protect_appearance:
        from workspace_components import appearance_state
        value["projection_component"] = obj.get("projection_component")
        value["appearance"] = appearance_state(obj, appearance_cache)
    if obj.type == "MESH":
        value["vertices"] = [list(v.co) for v in obj.data.vertices]
        value["faces"] = [list(p.vertices) for p in obj.data.polygons]
        value["edges"] = [list(e.vertices) for e in obj.data.edges]
        # Active modifiers alter effective geometry without changing base vertices.
        value["modifiers"] = [(m.name, m.type, m.show_viewport, m.show_render)
                              for m in obj.modifiers]
        if any(m.show_viewport or m.show_render for m in obj.modifiers):
            import bpy
            evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = evaluated.to_mesh()
            try:
                value["evaluated_vertices"] = [list(v.co) for v in mesh.vertices]
                value["evaluated_faces"] = [list(p.vertices) for p in mesh.polygons]
            finally:
                evaluated.to_mesh_clear()
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _objects(config):
    import bpy
    return list(bpy.data.collections[config["collection_name"]].all_objects)


def _ownership(config):
    import bpy
    objects = _objects(config)
    from workspace_components import validated_scope
    scope = validated_scope(config, objects)
    if scope is None and not config.get('source_path'):
        scope = config.get('component_ownership')  # freshly parsed prepare() catalog
    target = [o for o in objects if o.type == "MESH" and o.get("asset_group") == config["asset_id"]
              and not (scope and o.get('source_node') in scope['split_sources']
                       and not o.get('projection_component'))]
    if not target:
        raise ValueError("Asset has no meshes in the reviewed working collection")
    if any(not o.get("source_node") for o in target):
        raise ValueError("Every asset component must retain a stable source_node")
    appearance_cache = {}
    return target, {o.name: _geometry(o, protect_appearance=scope is not None, appearance_cache=appearance_cache) for o in bpy.data.scenes[config["scene_name"]].objects
                    if o not in target}


def _review_layers(config):
    if not config.get("projection_manifest"):
        return None
    from interior_layers import (projection_receivers, projection_occluders,
                                 validate_projection_reviews, projection_component_exclusions,
                                 projection_receiver_components, projection_occluder_additions)
    path = Path(config["projection_manifest"])
    manifest = _validated_projection(config)
    validate_projection_reviews(manifest,path.parent)
    exclusions=projection_component_exclusions(manifest)
    receiver_components=projection_receiver_components(manifest)
    additions=projection_occluder_additions(manifest)
    interior = projection_receivers(manifest)
    available = {o.get("source_node") for o in _objects(config)
                 if o.type == "MESH" and not o.hide_render}
    exterior = (available - {node for nodes in interior.values() for node in nodes}) | {
        selector['source_node'] for selector in receiver_components.get('exterior',[])}
    occluders = projection_occluders(manifest, available)
    exterior_occluders=exterior | (set(additions.get('exterior',[])) & available)
    partitions = [("exterior", "exterior", sorted(exterior), sorted(exterior_occluders))]
    partitions.extend(("interior", "interior-" + patch, sorted(nodes), occluders[patch]) for patch, nodes in interior.items())
    exterior_source = _mission_review_source(config) or str((path.parent / manifest['sources']['exterior']).resolve())
    from projection_regions import region_record
    return [{"source_path": exterior_source if source == 'exterior' else str((path.parent / manifest["sources"][source]).resolve()),
             "receiver_nodes": nodes, "occluder_nodes": blockers,
             **({'receiver_components':receiver_components[label]} if label in receiver_components else {}),
             **({'exclude_occluder_components':exclusions[label.removeprefix('interior-')],
                 'projection_label':label} if label.startswith('interior-') and label.removeprefix('interior-') in exclusions else {}),
             **({'projection_region': region_record(manifest,path.parent,label.removeprefix('interior-'),
                 (path.parent / manifest['sources']['interior']).resolve(), exterior_source,
                 exterior_occluders | set(nodes),covered_components=exclusions.get(label.removeprefix('interior-')))} if source == 'interior' else {}),
             **({"projection_label": label} if config.get('source_mask_manifest') else {})}
            for source, label, nodes, blockers in partitions]


def _mission_review_source(config):
    """Use an explicitly modeled mission endpoint, never unrelated base pixels."""
    if not config.get('projection_manifest'):
        return None
    path = Path(config['projection_manifest'])
    manifest = _validated_projection(config)
    sources = set()
    for obj in _objects(config):
        if obj.type != 'MESH' or obj.hide_render or not obj.get('mission_patch_profile'):
            continue
        mission, profile = obj.get('mission_patch_mission'), obj['mission_patch_profile']
        state = obj.get('drawbridge_state', 'initial')
        if state not in ('initial', 'applied'):
            raise ValueError('Review transition poses with an explicit matching source frame; endpoint artwork is not valid')
        records = [p for p in manifest.get('mission_patches', [])
                   if p['mission'] == mission and p['name'] == profile]
        if len(records) != 1 or state not in records[0].get('projection_sources', {}):
            raise ValueError(f'Missing declared mission projection source for {mission}/{profile}/{state}')
        sources.add(str((path.parent / records[0]['projection_sources'][state]).resolve(strict=True)))
    if len(sources) > 1:
        raise ValueError('Mixed mission endpoints require an explicitly composed matching reference state')
    return next(iter(sources), None)


def _active_owned_nodes(config, objects):
    owned = [obj for obj in objects if obj.type == 'MESH' and obj.get('asset_group') == config['asset_id']]
    canonical = {obj.get('source_node') for obj in owned}
    if canonical != set(config['part_ids']):
        raise ValueError('Canonical owned source parts changed before projection')
    active = sorted({obj.get('source_node') for obj in owned if not obj.hide_render})
    if not active:
        raise ValueError('Projection state has no visible owned mesh')
    return active


def _reproject(config, report_dir):
    objects = _objects(config)
    active_nodes = _active_owned_nodes(config, objects)
    _validated_masks(config, objects)
    from reproject_map import restore_projection, reproject_layers, reproject_map
    # Layered projection owns its full receiver partition. Keep context meshes
    # render-visible, even though only the worker asset is selectable.
    ownership_scope = {"receiver_asset_id": config["asset_id"]} if config.get("component_ownership") else {}
    restore_projection(config["map_name"], **ownership_scope)
    if config.get("projection_manifest"):
        # The projection annotator writes beside its manifest. Keep its changing
        # receiver report out of the immutable reference directory.
        source = Path(config["projection_manifest"])
        manifest = _absolute_manifest_images(_validated_projection(config), source.parent)
        report_dir = Path(report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        _json(report_dir / "layers.json", manifest)
        return reproject_layers(report_dir / "layers.json", report_dir,
                                ownership_nodes=active_nodes, preserve_authored=False,
                                exterior_source=_mission_review_source(config),
                                source_mask_manifest=config.get('source_mask_manifest'),
                                **({'ownership_asset_id': config['asset_id']} if config.get('component_ownership') else {}))
    report = reproject_map(config["map_name"], config["source_path"],
                           Path(report_dir) / "source.json",
                           elevation_deg=config["elevation_degrees"], **ownership_scope)
    from source_projection_bake import bake
    report['ownership'] = bake(config['map_name'], config['source_path'],
                               Path(report_dir) / 'ownership.json',
                               projection_label='exterior',
                               receiver_nodes=active_nodes,
                               elevation_deg=config['elevation_degrees'],
                               preserve_authored=False,
                               source_mask_manifest=config.get('source_mask_manifest'), **ownership_scope)
    return report


def _render(config, output, baseline=None):
    from refinement_review import render_review
    mask_evidence = _validated_masks(config, _objects(config))
    result = render_review(output, scene_name=config["scene_name"],
                         collection_name=config["collection_name"], asset_id=config["asset_id"],
                         source_path=_mission_review_source(config) or config["source_path"], frame_manifest=baseline,
                         width=config["width"], height=config["height"],
                         elevation_degrees=config["elevation_degrees"],
                         context_padding=config["context_padding"],
                         framing_padding=config.get('framing_padding', 1.04),
                         projection_layers=_review_layers(config),
                         source_mask_manifest=config.get('source_mask_manifest'),
                         allow_projection_revision=bool(baseline and config.get('projection_manifest')),
                         allow_mask_revision=bool(baseline and mask_evidence))
    if config.get('component_ownership'):
        result['component_ownership'] = config['component_ownership']
    if mask_evidence:
        result['working_mask_evidence'] = mask_evidence
    if config.get('projection_manifest'):
        result['projection_manifest_sha256'] = _sha(config['projection_manifest'])
        result['projection_manifest'] = str(config['projection_manifest'])
    _json(Path(output)/'views.json', result)
    return result


def prepare(workspace_dir, *, asset_id, scene_name, collection_name, source_path,
            grouping_manifest, inventory_path, review_path, projection_manifest=None, width=384, height=512,
            elevation_degrees=35.0, context_padding=24, source_mask_manifest=None,
            framing_padding=1.04):
    """Create a new workspace from the loaded scene; refuse an existing directory.

    Call from a disposable Blender process opened on the accepted full scene.
    The baseline includes context but only the chosen asset is editable in UI.
    """
    import bpy
    workspace = Path(workspace_dir).resolve()
    if workspace.exists():
        raise FileExistsError(workspace)
    if not collection_name.endswith(" Working"):
        raise ValueError("Projection expects '<map> Working' collection naming")
    grouping_path = Path(grouping_manifest).resolve()
    grouping = json.loads(grouping_path.read_text())
    review = json.loads(Path(review_path).read_text())
    if review.get("status") != "reviewed" or not review.get("reviewer"):
        raise ValueError("Finish and mark the grouping inventory reviewed before dispatch")
    if (review.get("catalog_sha256") != _sha(grouping_path)
            or review.get("inventory_sha256") != _sha(inventory_path)):
        raise ValueError("Grouping review does not match the catalog/inventory bytes")
    from refinement_inventory import validate_catalog
    validate_catalog(inventory_path, grouping_path)
    entry = next((a for a in grouping["groups"] if a["id"] == asset_id), None)
    if entry is None:
        raise ValueError(f"Asset absent from reviewed inventory: {asset_id}")
    config = dict(version=1, asset_id=asset_id, scene_name=scene_name,
                  collection_name=collection_name, map_name=collection_name[:-8],
                  width=width, height=height, elevation_degrees=elevation_degrees,
                  context_padding=context_padding, framing_padding=framing_padding,
                  source_blend=str(Path(bpy.data.filepath).resolve()),
                  source_blend_sha256=_sha(bpy.data.filepath),
                  grouping_manifest_sha256=_sha(grouping_path))
    bpy.context.window.scene = bpy.data.scenes[scene_name]
    bpy.context.view_layer.update()
    if grouping.get("version") == 2:
        from catalog_schema import parse_catalog
        from workspace_components import scope_for
        index = parse_catalog(grouping)
        meshes = [o for o in _objects(config) if o.type == "MESH" and o.get("source_node") != "ground"]
        index.validate_meshes([{"source_node": o.get("source_node"), "projection_component": o.get("projection_component"), "hide_render": o.hide_render} for o in meshes])
        for obj in meshes:
            owner, _ = index.owner_for(obj.get("source_node"), obj.get("projection_component"))
            if obj.get("asset_group") != owner["id"]:
                raise ValueError("Loaded component ownership differs from reviewed catalog")
        config["component_ownership"] = scope_for(index, asset_id)
    targets, outside = _ownership(config)
    parts = sorted({o["source_node"] for o in targets})
    if sorted(f"building-{p['obstacle']:03d}" for p in entry["parts"]) != parts:
        raise ValueError("Current asset parts differ from the grouping review")
    workspace.mkdir(parents=True)
    reference = workspace / "reference"
    reference.mkdir()
    shutil.copy2(grouping_path, reference / "grouping.json")
    shutil.copy2(inventory_path, reference / "inventory.json")
    shutil.copy2(review_path, reference / "grouping-review.json")
    shutil.copy2(source_path, reference / "source.png")
    config["source_path"] = str(reference / "source.png")
    config["projection_manifest"] = None
    if source_mask_manifest:
        # Keep editable receiver assignments local; referenced inventories remain read-only.
        path = Path(source_mask_manifest).resolve(strict=True)
        masks = json.loads(path.read_text())
        masks['mask_inventory'] = str((path.parent / masks['mask_inventory']).resolve(strict=True))
        _json(workspace / 'source-masks.json', masks)
        config['source_mask_manifest'] = str(workspace / 'source-masks.json')
        _freeze_masks(workspace, config)
    if projection_manifest:
        path = Path(projection_manifest).resolve()
        layers = _copy_manifest_images(json.loads(path.read_text()), path.parent, reference)
        _json(reference / "layers.json", layers)
        _json(workspace / 'projection-layers.json', _absolute_manifest_images(layers, reference))
        config["projection_manifest"] = str(workspace / 'projection-layers.json')
    for obj in _objects(config):
        obj.hide_select = obj not in targets
        obj.select_set(obj in targets)
    bpy.context.view_layer.objects.active = targets[0]
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / "baseline.blend"), copy=True)
    config["baseline_sha256"] = _sha(workspace / "baseline.blend")
    config["part_ids"] = parts
    if config.get("component_ownership"):
        targets, outside = _ownership(config)
    config["outside_geometry"] = outside
    _reproject(config, workspace / "projection" / "input")
    _render(config, workspace / "input")
    config["input_files"] = _files(workspace / "input")
    config["reference_files"] = _files(reference)
    _json(workspace / "workspace.json", config)
    if projection_manifest:
        from asset_reference_views import prepare as prepare_asset_reference
        prepare_asset_reference(workspace)
    instructions = f'''# Refinement worker: {asset_id}

Own only this logical asset. Its stable source parts are {", ".join(parts)}.
Earlier refinements are hypotheses, not constraints. Remove or rebuild any owned
geometry that conflicts with original artwork or authored occlusion silhouettes.
Do not preserve a bad roof profile merely because a previous worker created it.
Preserve stable part identities, not inherited shapes; the baseline is your backup.
Edit `model.blend` in your own Blender process. All scene context remains in the
file for accurate occlusion; it is not selectable and is outside your scope.
Do not delete, transform, rename or edit other assets. Preserve source_node and
asset_group on every component; new component meshes must use one of the owned
source parts. Keep group-first, part-second editor selection intact.

`baseline.blend`, `reference/` and `input/` are immutable evidence. `context.png`
is an unmasked source-image crop, including background. `solid.png` and
`textured.png` show eight fixed views in a 4x2 sheet. Neutral gray means the
source view provides no reliable texture. Generated textures are never evidence.
Check actual silhouette against the context: terrain painted onto a roof means
geometry needs correction. Do not compensate for shape errors with generated art.

Feel free to generate zoomed-in detail views, additional camera angles, lower or
higher elevations, and section views whenever they help you understand or refine
the model. Do not limit your inspection to the eight standard views. Save these
extra renders in `inspection/` with descriptive names; include matching before
and after views when useful. The standard input/modified sheets remain the fixed
comparison, and extra views supplement them.

After each meaningful geometry pass run the modified command below. It reapplies
source projection and renders `modified/` with exactly the input camera framing
and file layout. Do not change the frozen framing to hide geometry differences.
Apply active modifiers before reprojection. Keep a reusable recipe and a short
`review.md` describing changes, checks, unresolved defects and inferred geometry.

```sh
blender --background "{workspace / 'model.blend'}" --python "{Path(__file__).resolve()}" -- modified "{workspace}"
```

Handoff `model.blend`, the recipe, `review.md`, and `modified/` only after validation
passes and you inspect context, solid and textured sheets. Do not publish the
whole copied scene: the coordinator imports only this asset into the main map.
Texture synthesis is a separate step after geometry review.
Start with asset-reference/ for focused original source crops and reviewed
asset-specific patches. The full reference/ directory is projection backing data;
its unrelated images are not assigned worker evidence.
For assets with interiors or changing outer patches, inspect reference/layers.json,
but edit reviewed receivers/components and display states only in projection-layers.json.
The reference manifest and images remain immutable; changing source/state inventory
or assignments of another asset fails validation. Modified packets record the
working manifest hash while retaining the original eight cameras and crop.
reference/covered.png, reference/revealed.png, each relevant patch PNG and alpha,
and the relevant reference/mission-patches/ state frames before refining. These
are original reference views, not synthesized textures. Record which states and
patch IDs were inspected in review.md. Render source-context crops and matching
solid/source-textured closeups for the exterior-covered and interior-revealed
states; hide only the covering geometry identified by that state. Keep interior
receivers, exterior receivers and their occluders separate during reprojection.
Do not mark an interior building reviewed from exterior eight-view sheets alone.
Save extra evidence in inspection/ without changing immutable input/reference.
Do not run GPT Sunburst texture generation yourself. The coordinator must show
the current solid and source-only textured views to the user and receive explicit
approval for this geometry revision before any Sunburst texture-fill request.
'''
    (workspace / "INSTRUCTIONS.md").write_text(instructions)
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / "model.blend"))
    return {"workspace": str(workspace), "asset_id": asset_id, "part_ids": parts,
            "input": str(workspace / "input"), "status": "prepared"}


def validate(workspace_dir):
    """Validate ownership of the loaded worker file and immutable input evidence."""
    import bpy
    workspace = Path(workspace_dir).resolve()
    config = json.loads((workspace / "workspace.json").read_text())
    bpy.context.window.scene = bpy.data.scenes[config["scene_name"]]
    bpy.context.view_layer.update()
    targets, outside = _ownership(config)
    errors = []
    if outside != config["outside_geometry"]:
        names = set(outside) | set(config["outside_geometry"])
        errors.append("Outside-asset geometry or identity changed: " + ", ".join(
            sorted(n for n in names if outside.get(n) != config["outside_geometry"].get(n))))
    if sorted({o["source_node"] for o in targets}) != config["part_ids"]:
        errors.append("Owned stable source parts changed")
    for name, expected in (("input", config["input_files"]),
                           ("reference", config["reference_files"])):
        if _files(workspace / name) != expected:
            errors.append(f"Immutable {name} files changed")
    if _sha(workspace / "baseline.blend") != config["baseline_sha256"]:
        errors.append("Immutable baseline.blend changed")
    if errors:
        raise ValueError("\n".join(errors))
    if config.get('projection_manifest'):
        _validated_projection(config)
    masks = _validated_masks(config, _objects(config))
    return {"status": "PASS", "asset_id": config["asset_id"],
            "part_ids": config["part_ids"], "meshes": len(targets),
            **({"component_ownership": config["component_ownership"]} if config.get("component_ownership") else {}),
            "projection_manifest_sha256": _sha(config['projection_manifest']) if config.get('projection_manifest') else None,
            "working_mask_evidence": masks,
            "protected_objects": len(outside)}


def modified(workspace_dir):
    """Reproject, render and validate; retain the last accepted packet on failure."""
    import bpy
    workspace = Path(workspace_dir).resolve()
    if Path(bpy.data.filepath).resolve() != workspace / "model.blend":
        raise ValueError("Open this workspace's model.blend before regenerating modified")
    report = validate(workspace)
    config = json.loads((workspace / "workspace.json").read_text())
    token = uuid.uuid4().hex[:12]
    stage = workspace / (".modified-" + token)
    try:
        _reproject(config, workspace / "projection" / token)
        _render(config, stage, workspace / "input" / "views.json")
        validate(workspace)
        if set(_files(stage)) != set(config["input_files"]):
            raise ValueError("Modified packet layout differs from immutable input")
        bpy.ops.wm.save_as_mainfile(filepath=str(workspace / "model.blend"))
        if (workspace / "modified").exists():
            history = workspace / "history"
            history.mkdir(exist_ok=True)
            (workspace / "modified").rename(history / token)
        stage.rename(workspace / "modified")
    except Exception:
        # Keep failed artifacts for diagnosis, never replace the previous packet.
        raise
    _json(workspace / "validation.json", report)
    return {**report, "modified": str(workspace / "modified")}


def dispatch(output_dir, *, source_blend, max_concurrency=4, **prepare_options):
    """Write one independently runnable preparation/refinement job per catalog asset.

    This plans jobs, not agent execution. The coordinator starts at most the
    declared concurrency and hands each agent only its matching workspace.
    """
    if max_concurrency < 1:
        raise ValueError("Concurrency must be positive")
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "dispatch.json"
    if destination.exists():
        raise FileExistsError(destination)
    catalog = json.loads(Path(prepare_options["grouping_manifest"]).read_text())
    review = json.loads(Path(prepare_options["review_path"]).read_text())
    if (review.get("status") != "reviewed" or not review.get("reviewer")
            or review.get("catalog_sha256") != _sha(prepare_options["grouping_manifest"])
            or review.get("inventory_sha256") != _sha(prepare_options["inventory_path"])):
        raise ValueError("Dispatch requires matching reviewed grouping evidence")
    from refinement_inventory import validate_catalog
    validate_catalog(prepare_options["inventory_path"], prepare_options["grouping_manifest"])
    script = str(Path(__file__).resolve())
    source_blend = str(Path(source_blend).resolve(strict=True))
    jobs = []
    for asset in catalog["groups"]:
        asset_id = asset["id"]
        if Path(asset_id).name != asset_id or asset_id in (".", ".."):
            raise ValueError(f"Unsafe asset workspace name: {asset_id}")
        workspace = output / asset_id
        argv = ["blender", "--background", source_blend, "--python", script,
                "--", "prepare", str(workspace), "--asset-id", asset_id]
        for key, value in prepare_options.items():
            if value is not None:
                argv.extend(["--" + key.replace("_", "-"), str(value)])
        jobs.append({"asset_id": asset_id, "name": asset["name"],
                     "workspace": str(workspace),
                     "state": "existing_workspace" if workspace.exists() else "planned",
                     "prepare_argv": argv, "prepare_command": shlex.join(argv),
                     "agent_instructions": str(workspace / "INSTRUCTIONS.md"),
                     "handoff": ["model.blend", "modified/", "review.md", "recipe"]})
    result = {"version": 1, "max_concurrency": max_concurrency,
              "source_blend": source_blend, "source_blend_sha256": _sha(source_blend),
              "jobs": jobs, "review_scope": review.get("scope"),
              "unresolved": review.get("unresolved", []),
              "patch_asset_audit_status": review.get("patch_asset_audit_status"),
              "mission_patch_candidates": review.get("mission_patch_candidates", []),
              "known_missing_patch_assets": review.get("known_missing_patch_assets", []),
              "terrain": review.get("terrain", "Separate terrain worker required")}
    _json(destination, result)
    return {"dispatch": str(destination), "jobs": len(jobs), "max_concurrency": max_concurrency}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "dispatch"):
        p = sub.add_parser(command)
        p.add_argument("workspace")
        if command == "prepare":
            p.add_argument("--asset-id", required=True)
        else:
            p.add_argument("--source-blend", required=True)
            p.add_argument("--max-concurrency", type=int, default=4)
        for option in ("scene-name", "collection-name", "source-path", "grouping-manifest", "inventory-path", "review-path"):
            p.add_argument("--" + option, required=True)
        p.add_argument("--projection-manifest")
        p.add_argument("--source-mask-manifest")
        p.add_argument("--width", type=int, default=384)
        p.add_argument("--height", type=int, default=512)
        p.add_argument("--elevation-degrees", type=float, default=35)
        p.add_argument("--context-padding", type=int, default=24)
        p.add_argument("--framing-padding", type=float, default=1.04,
                       help="Initial camera fit multiplier; modified packets retain frozen input cameras")
    for command in ("modified", "validate"):
        sub.add_parser(command).add_argument("workspace")
    args = vars(parser.parse_args(argv))
    command, workspace = args.pop("command"), args.pop("workspace")
    result = globals()[command](workspace, **args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
