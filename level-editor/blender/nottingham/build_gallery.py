"""Collect verified Nottingham worker packets without granting approval.

Run with Python, after workers produce packets. Defaults target
work/nottingham-refinement/{grouping/catalog-v7.json,round-1/assets,gallery}.
Workers provide candidate.json with version, asset_id, geometry_refined, status,
inspected_views, recipe, model_sha256, modified_views_sha256, changes, limitations.
Ready candidates also require review.md and all eight visually inspected views.
An unchanged candidate additionally requires geometry_reviewed=true and a
specific no_change_reason. --approvals accepts separate user decision records:
{"version":1,"approvals":[{"asset_id":"...","decision":"approved",
"exact_text":"...","model_sha256":"...","modified_views_sha256":"..."}]}.
Only decisions bound to the current model and packet can hide approved cards.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + "\n")


def file_hashes(directory):
    return {str(path.relative_to(directory)): sha(path)
            for path in sorted(directory.rglob("*")) if path.is_file()}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def projection_records(config, manifest, available):
    """Rebuild the frozen helper's static review partition without loading Blender."""
    from interior_layers import (projection_receivers, projection_occluders,
        projection_component_exclusions, projection_receiver_components, projection_occluder_additions)
    from projection_regions import region_record
    directory = Path(config["projection_manifest"]).parent
    interiors = projection_receivers(manifest)
    components = projection_receiver_components(manifest)
    exclusions = projection_component_exclusions(manifest)
    additions = projection_occluder_additions(manifest)
    exterior = (available - {node for nodes in interiors.values() for node in nodes}) | {
        row["source_node"] for row in components.get("exterior", [])}
    blockers = exterior | (set(additions.get("exterior", [])) & available)
    occluders = projection_occluders(manifest, available)
    partitions = [("exterior", "exterior", sorted(exterior), sorted(blockers))]
    partitions += [("interior", "interior-" + patch, sorted(nodes), occluders[patch])
                   for patch, nodes in interiors.items()]
    covered = (directory / manifest["sources"]["exterior"]).resolve()
    result = []
    for source, label, nodes, obscurers in partitions:
        path = (directory / manifest["sources"][source]).resolve()
        row = {"source_path": str(path), "source_sha256": sha(path),
               "receiver_nodes": nodes, "occluder_nodes": obscurers}
        if label in components:
            row["receiver_components"] = components[label]
        patch = label.removeprefix("interior-")
        if source == "interior":
            if patch in exclusions:
                row.update(exclude_occluder_components=exclusions[patch], projection_label=label)
            row["projection_region"] = region_record(manifest, directory, patch, path, covered,
                blockers | set(nodes), covered_components=exclusions.get(patch))
        if config.get("source_mask_manifest"):
            row["projection_label"] = label
        result.append(row)
    return result


def inspect(workspace, asset):
    config = read(workspace / "workspace.json")
    require(config["asset_id"] == asset["id"], "Workspace asset ID mismatch")
    expected_parts = (['ground'] if asset.get('role') == 'terrain' else
                      sorted(f"building-{p['obstacle']:03d}" for p in asset["parts"]))
    require(config["part_ids"] == expected_parts,
            "Workspace parts differ from current catalog")
    validation = read(workspace / "validation.json")
    require(validation.get("status") == "PASS" and validation.get("asset_id") == asset["id"],
            "Missing successful asset validation")
    require(validation.get("part_ids") == config["part_ids"], "Validation source parts differ")
    require(sha(workspace / "baseline.blend") == config["baseline_sha256"], "Frozen baseline changed")
    for folder, key in (("input", "input_files"), ("reference", "reference_files")):
        require(file_hashes(workspace / folder) == config[key], f"Immutable {folder} evidence changed")
    from refinement_workspace import _validated_masks, _validated_projection
    mask_revision = None
    if config.get("mask_reference"):
        mask_revision = _validated_masks(config)
    reviewed_projection = _validated_projection(config) if config.get("projection_manifest") else None
    required = {"solid.png", "textured.png", "context.png", "views.json"}
    required.update(f"views/view-{i}-{kind}.png" for i in range(8)
                    for kind in ("solid", "known", "textured"))
    packets, hashes = {}, {}
    for name in ("input", "modified"):
        folder = workspace / name
        hashes[name] = file_hashes(folder)
        require(required <= hashes[name].keys(), f"Incomplete {name} eight-view packet")
        packet = read(folder / "views.json")
        require(packet.get("asset_id") == asset["id"] and packet.get("version") == 1,
                f"Invalid {name} framing manifest")
        require(packet.get("layout") == {"columns": 4, "rows": 2}, "Expected fixed 4x2 layout")
        require([view["index"] for view in packet["views"]] == list(range(8)), "Expected all eight views")
        for view in packet["views"]:
            require(view["ownership_sha256"] == hashes[name][f"views/view-{view['index']}-known.png"],
                    f"{name} ownership bitmap hash mismatch")
        for path, digest in (packet.get("source_mask_evidence") or {}).items():
            check_path = Path(path)
            if (name == "input" and mask_revision and
                    check_path.resolve() == Path(config["source_mask_manifest"]).resolve()):
                check_path = Path(config["mask_reference"]) / "assignments.json"
            require(sha(check_path) == digest, f"Mask evidence changed: {path}")
        if name == "modified" and config.get("source_mask_manifest"):
            from occlusion_constraints import evidence_record
            require(packet.get("source_mask_evidence") == evidence_record(config["source_mask_manifest"]),
                    "Modified packet does not bind current working mask evidence")
        require(sha(packet["source_image"]) == packet["source_sha256"], "Source artwork changed")
        packets[name] = packet
    require(set(hashes["input"]) == set(hashes["modified"]), "Input/modified file layout differs")
    for key in ("tile_size", "elevation_degrees", "context_crop", "source_sha256", "lighting"):
        require(packets["input"].get(key) == packets["modified"].get(key), f"Frozen {key} differs")
    if not mask_revision:
        require(packets["input"].get("source_mask_evidence") == packets["modified"].get("source_mask_evidence"),
                "Unmigrated mask evidence differs from frozen input")
    if reviewed_projection is not None:
        before_layers = packets["input"]["projection_layers"]
        after_layers = packets["modified"]["projection_layers"]
        available = {node for row in before_layers for key in ("receiver_nodes", "occluder_nodes") for node in row[key]}
        expected_layers = projection_records(config, reviewed_projection, available)
        if asset['id'] in ('nottingham-upper-prison', 'nottingham-southwest-prison') and any(
                '-prison-door-' in row.get('projection_label', '') for row in after_layers):
            expected_layers = prison_endpoint_records(workspace, config, expected_layers)
        require(after_layers == expected_layers,
                "Modified projection layers do not match validated own-asset projection reviews")
    else:
        require(packets["input"]["projection_layers"] == packets["modified"]["projection_layers"],
                "Projection layers changed without reviewed working manifest")
    for before, after in zip(packets["input"]["views"], packets["modified"]["views"]):
        for key in ("camera_matrix_world", "camera_location", "camera_rotation_euler", "ortho_scale"):
            require(before[key] == after[key], f"Frozen camera {before['index']} {key} differs")
    changed = any(hashes["input"][f"views/view-{i}-solid.png"] !=
                  hashes["modified"][f"views/view-{i}-solid.png"] for i in range(8))
    model_hash = sha(workspace / "model.blend")
    candidate_path = workspace / "candidate.json"
    worker = read(candidate_path) if candidate_path.exists() else {}
    blockers = []
    bound = (worker.get("model_sha256") == model_hash and
             worker.get("modified_views_sha256") == hashes["modified"]["views.json"])
    if worker:
        require(worker.get("version") == 1 and worker.get("asset_id") == asset["id"],
                "Invalid candidate identity/version")
        require(isinstance(worker.get("limitations"), list) and isinstance(worker.get("changes"), list),
                "Candidate requires changes and limitations lists")
    if not bound:
        blockers.append("Worker report is absent or does not bind the current model and packet hashes.")
    recipe = Path(worker["recipe"]) if worker.get("recipe") else None
    if recipe and not recipe.is_absolute():
        recipe = workspace / recipe
    if recipe and recipe.is_file():
        recipe_evidence = {"path": str(recipe.resolve()), "sha256": sha(recipe)}
    else:
        recipe_evidence = None
        blockers.append("Reproducible geometry recipe missing.")
    review = workspace / "review.md"
    if not review.is_file() or not review.read_text().strip():
        blockers.append("Worker review and limitations missing.")
    if worker.get("inspected_views") != list(range(8)):
        blockers.append("Worker has not recorded inspection of all eight modified views.")
    refined = worker.get("geometry_refined") is True and changed and bound
    no_change_reason = worker.get("no_change_reason")
    reviewed_unchanged = (worker.get("geometry_reviewed") is True
                          and worker.get("geometry_refined") is False and not changed and bound
                          and isinstance(no_change_reason, str) and bool(no_change_reason.strip()))
    if refined and not worker.get("changes"):
        blockers.append("Worker has not described the geometry changes.")
    if not refined and not reviewed_unchanged:
        blockers.append("No completed geometry refinement or explicit unchanged-geometry audit is established.")
    status = "refinement-in-progress"
    if worker.get("status") == "fix-needed":
        status = "fix-needed"
    elif worker.get("status") == "ready-for-user" and not blockers:
        status = "ready-for-user"
    limitations = list(packets["modified"].get("limitations", [])) + worker.get("limitations", []) + blockers
    if reviewed_unchanged:
        limitations.append("Reviewed without geometry changes: " + no_change_reason.strip())
    if not config.get("projection_manifest"):
        limitations.append("Static exterior packet only; revealed and animated state ownership is not validated.")
    unconstrained = sorted({row["source_node"] for row in
                            packets["modified"].get("source_constraint_status", [])
                            if not row.get("constrained")})
    if unconstrained:
        limitations.append("No reviewed native mask constrains: " + ", ".join(unconstrained) + ".")
    mask_assignments = []
    if config.get("source_mask_manifest"):
        masks = read(config["source_mask_manifest"])
        for projection, definition in masks["projections"].items():
            for assignment in definition["assignments"]:
                if (assignment.get("source_node") in config["part_ids"]
                        or assignment.get("asset_group") == asset["id"]):
                    mask_assignments.append({"projection": projection, **assignment})
        active_labels = {row.get('projection_label') for row in packets['modified'].get('projection_layers', [])}
        unknown_nodes = sorted({row.get("source_node", asset["id"]) for row in mask_assignments
                                if row.get("constraint_kind") == "unknown-no-approved-source"
                                and row['projection'] in active_labels})
        if unknown_nodes:
            limitations.append("Explicit neutral-only source constraints, with no accepted native ownership: "
                               + ", ".join(unknown_nodes) + ". Black rejection masks are not native silhouette evidence.")
    preparation = workspace / "preparation.json"
    if preparation.exists() and read(preparation).get("scope"):
        limitations.append(read(preparation)["scope"])
    evidence = {"version": 1, "asset_id": asset["id"], "status": status,
                "geometry_refined": refined, "geometry_reviewed": refined or reviewed_unchanged,
                "review_outcome": "refined" if refined else "reviewed-no-change" if reviewed_unchanged else "baseline-only",
                "solid_views_changed": changed,
                "model_sha256": model_hash, "baseline_sha256": config["baseline_sha256"],
                "packet_hashes": hashes, "source_sha256": packets["modified"]["source_sha256"],
                "source_mask_evidence": packets["modified"].get("source_mask_evidence"),
                "source_constraints": packets["modified"].get("source_constraint_status"),
                "mask_assignments": mask_assignments,
                "reviewed_mutable_evidence": {
                    "mask_revision": mask_revision,
                    "projection_manifest": config.get("projection_manifest"),
                    "projection_manifest_sha256": sha(config["projection_manifest"]) if reviewed_projection is not None else None,
                    "projection_reviews": reviewed_projection.get("projection_reviews") if reviewed_projection is not None else None,
                    "guard": "Frozen helper validates immutable authority and rejects foreign assignment changes"},
                "recipe": recipe_evidence, "worker_report": worker,
                "candidate_sha256": sha(candidate_path) if worker else None,
                "validation": validation, "validation_sha256": sha(workspace / "validation.json"),
                "limitations": limitations}
    return status, limitations, evidence, review


def prison_endpoint_records(workspace, config, layers):
    """Validate the explicit closed/open door partition against frozen source authority."""
    upper = config['asset_id'] == 'nottingham-upper-prison'
    patch = 'patch-002' if upper else 'patch-007'
    prefix = 'upper-prison-door' if upper else 'southwest-prison-door'
    doors = ['building-453', 'building-455'] if upper else ['building-476', 'building-477']
    require(set(doors) <= set(config['part_ids']), 'Door endpoints are not owned by this prison')
    masks = read(config['source_mask_manifest'])
    references = read(workspace / 'door-reference/manifest.json')
    interior = next(row for row in layers if row['projection_label'] == 'interior-' + patch)
    for row in layers:
        row['receiver_nodes'] = [node for node in row['receiver_nodes'] if node not in doors]
        row['occluder_nodes'] = [node for node in row['occluder_nodes'] if node not in doors]
    for endpoint, node in zip(('initial', 'applied'), doors):
        label = prefix + '-' + endpoint
        source = Path(references[label]['source'])
        digest = sha(source)
        require(digest == references[label]['sha256'] == masks['projections'][label]['source_sha256'],
                'Prison endpoint artwork differs from immutable mask authority')
        layers.append({'source_path': str(source), 'source_sha256': digest,
                       'receiver_nodes': [node],
                       'occluder_nodes': sorted(set(interior['occluder_nodes']) | {node}),
                       'exclude_occluder_components': interior.get('exclude_occluder_components', []),
                       'projection_label': label})
    return layers


def supplemental_packet(directory, asset_id, framing, *, mask_origin=None):
    """Check state sheets against the same fixed cameras and their source bytes."""
    directory = Path(directory).resolve(strict=True)
    packet = read(directory / 'views.json')
    require(packet.get('asset_id') == asset_id, 'Supplemental packet asset differs')
    require(packet.get('layout') == {'columns': 4, 'rows': 2}, 'Supplemental layout differs')
    require(len(packet.get('views', [])) == 8, 'Supplemental state requires eight views')
    for key in ('tile_size', 'context_crop', 'elevation_degrees', 'lighting'):
        require(packet.get(key) == framing.get(key), 'Supplemental framing differs: ' + key)
    hashes = file_hashes(directory)
    for name in ('solid.png', 'textured.png', 'context.png', 'views.json'):
        require(name in hashes, 'Missing supplemental sheet: ' + name)
    for before, after in zip(framing['views'], packet['views']):
        for key in ('index', 'camera_matrix_world', 'camera_location', 'camera_rotation_euler', 'ortho_scale'):
            require(before[key] == after[key], 'Supplemental camera differs: ' + key)
        for kind in ('solid', 'textured', 'known'):
            require(f"views/view-{after['index']}-{kind}.png" in hashes, 'Incomplete state view')
        require(after['ownership_sha256'] == hashes[f"views/view-{after['index']}-known.png"],
                'Supplemental known-pixel bitmap differs')
    require(sha(packet['source_image']) == packet['source_sha256'], 'Supplemental source changed')
    for path, digest in (packet.get('source_mask_evidence') or {}).items():
        actual = Path(path)
        if mask_origin and actual.resolve() == mask_origin[0]:
            actual = mask_origin[1]
        require(sha(actual) == digest, 'Supplemental mask evidence changed: ' + path)
    return {'directory': str(directory), 'hashes': hashes, 'source_sha256': packet['source_sha256']}


def main(argv=None):
    root = Path(__file__).resolve().parents[2] / "work/nottingham-refinement"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=root / "grouping/catalog-v7.json")
    parser.add_argument("--assets", type=Path, default=root / "round-1/assets")
    parser.add_argument("--output", type=Path, default=root / "gallery")
    parser.add_argument('--workspace-map', type=Path, default=root / 'workspace-overrides.json',
                        help='Explicit newer revision paths; frozen older workspaces remain in place')
    parser.add_argument("--approvals", type=Path, help="Separate explicit user decisions bound to model/packet hashes")
    parser.add_argument("--tooling-dir", type=Path,
                        help="Frozen helper snapshot; defaults to tooling/current.json")
    args = parser.parse_args(argv)
    if args.approvals is None and (root / 'approvals.json').exists():
        args.approvals = root / 'approvals.json'
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from freeze_tooling import select_tooling
    tooling = select_tooling(args.tooling_dir)
    catalog = read(args.catalog)
    require(catalog.get("map") == "nottingham", "Expected Nottingham catalog")
    catalog = {**catalog, 'groups': [*catalog['groups'], {
        'id': 'nottingham-terrain-ground', 'name': 'Terrain and bridge stream bed',
        'role': 'terrain', 'parts': [],
    }]}
    ids = [asset["id"] for asset in catalog["groups"]]
    require(len(ids) == len(set(ids)), "Duplicate catalog asset IDs")
    overrides = {}
    if args.workspace_map.exists():
        override_record = read(args.workspace_map)
        require(override_record.get('version') == 1, 'Unknown workspace map version')
        overrides = override_record['assets']
        require(set(overrides) <= set(ids), 'Workspace overrides contain unknown assets')
    approvals = {}
    if args.approvals:
        records = read(args.approvals)
        require(records.get("version") == 1, "Unsupported approval record version")
        for record in records["approvals"]:
            identifier = record["asset_id"]
            require(identifier in ids and identifier not in approvals, "Unknown or duplicate approval asset ID")
            require(record.get("decision") in ("approved", "rejected", "revision-requested"), "Invalid user decision")
            require(isinstance(record.get("exact_text"), str) and record["exact_text"].strip(), "Exact user decision text missing")
            for key in ("model_sha256", "modified_views_sha256"):
                require(isinstance(record.get(key), str) and len(record[key]) == 64,
                        "User decision must bind exact model and packet hashes")
            approvals[identifier] = record
    output = args.output.resolve()
    evidence_dir = output.parent / (output.name + "-packet-evidence")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    items, progress = [], []
    for asset in catalog["groups"]:
        require(Path(asset["id"]).name == asset["id"] and asset["id"] not in (".", ".."), "Unsafe asset ID")
        workspace = (Path(overrides[asset['id']]).resolve() if asset['id'] in overrides else
                     args.assets.resolve() / asset["id"])
        row = {"id": asset["id"], "name": asset["name"], "workspace": str(workspace)}
        if not workspace.exists():
            progress.append({**row, "status": "missing"})
            continue
        try:
            status, limitations, evidence, review = inspect(workspace, asset)
            worker = evidence['worker_report']
            state_records = {}
            def local(path):
                path = Path(path)
                return path if path.is_absolute() else workspace / path
            framing = read(workspace / 'input/views.json')
            if worker.get('covered_solid'):
                folder = local(worker['covered_solid']).parent
                state_records['covered'] = supplemental_packet(folder, asset['id'], framing)
                require(local(worker['covered_textured']).resolve() == folder.resolve() / 'textured.png'
                        and local(worker['covered_context']).resolve() == folder.resolve() / 'context.png',
                        'Covered sheets must come from one validated packet')
            for state in worker.get('animation_states', []):
                identifier = state['id']
                require(isinstance(identifier, str) and identifier and
                        Path(identifier).name == identifier and identifier not in ('.', '..'),
                        'Invalid animation state ID')
                key = 'animation-' + identifier
                require(key not in state_records, 'Duplicate animation state ID')
                state_records[key] = supplemental_packet(local(state['directory']), asset['id'], framing)
            if worker.get('revealed_solid'):
                state_dir = local(worker['revealed_solid']).parent
                state_records['revealed'] = supplemental_packet(state_dir, asset['id'], framing)
                require(local(worker['revealed_textured']).resolve() == state_dir.resolve() / 'textured.png'
                        and local(worker['revealed_context']).resolve() == state_dir.resolve() / 'context.png',
                        'Revealed sheets must come from one validated packet')
                baseline_dir = local(worker.get('revealed_input', 'revealed/input'))
                config = read(workspace / 'workspace.json')
                origin = ((Path(config['source_mask_manifest']).resolve(),
                           Path(config['mask_reference']) / 'assignments.json')
                          if config.get('mask_reference') else None)
                state_records['revealed_input'] = supplemental_packet(
                    baseline_dir, asset['id'], framing, mask_origin=origin)
            evidence['state_packets'] = state_records
            evidence['state_bundle_sha256'] = (hashlib.sha256(json.dumps(
                state_records, sort_keys=True).encode()).hexdigest() if state_records else None)
        except (OSError, ValueError, KeyError, TypeError) as error:
            progress.append({**row, "status": "validation-pending", "reason": str(error)})
            continue
        evidence_path = evidence_dir / (asset["id"] + ".json")
        approval = approvals.get(asset["id"])
        approval_current = bool(approval and approval["model_sha256"] == evidence["model_sha256"]
                                and approval["modified_views_sha256"] == evidence["packet_hashes"]["modified"]["views.json"]
                                and (not evidence['state_bundle_sha256'] or
                                     approval.get('state_bundle_sha256') == evidence['state_bundle_sha256']))
        evidence["user_decision"] = approval
        evidence["user_decision_matches_revision"] = approval_current
        user_approval = "pending"
        if approval and approval.get('projection_review') == 'revision-requested':
            user_approval = 'geometry-approved; projection-pending'
            correction_path = evidence['worker_report'].get('projection_correction')
            correction = None
            if correction_path:
                correction_path = Path(correction_path)
                if not correction_path.is_absolute():
                    correction_path = workspace / correction_path
                correction = read(correction_path)
                require(correction.get('status') == 'PASS'
                        and correction['approved_model_sha256'] == approval['model_sha256']
                        and correction['model_sha256'] == evidence['model_sha256']
                        and correction['geometry_before_sha256'] == correction['geometry_after_sha256']
                        and len(correction['geometry_before_sha256']) == 64
                        and correction.get('inspected_views') == list(range(8)),
                        'Projection correction lacks proof that approved geometry was preserved')
                evidence['projection_correction'] = {**correction, 'report_sha256': sha(correction_path)}
            if correction is None:
                status = 'fix-needed'
            limitations.append('Geometry explicitly approved. ' + (
                'Projection corrected without geometry changes; projection review remains pending.' if correction else
                'The reported projection clipping is being corrected.'))
        elif approval_current:
            user_approval = approval["decision"]
            if user_approval == "approved":
                status = "approved"
            elif user_approval == "rejected":
                status = "rejected"
            else:
                status = "fix-needed"
        elif approval:
            limitations.append("Previous user decision applies to a different model/packet revision; current review is pending.")
        evidence["status"] = status
        write(evidence_path, evidence)
        item = {**row, "status": status, "user_approval": user_approval,
                "geometry_refined": evidence["geometry_refined"],
                "geometry_reviewed": evidence["geometry_reviewed"],
                "review_outcome": evidence["review_outcome"], "user_decision": approval,
                "notes": limitations,
                "model": str(workspace / "model.blend"),
                "solid": str(workspace / "modified/solid.png"),
                "textured": str(workspace / "modified/textured.png"),
                "context": str(workspace / "modified/context.png"),
                "validation": str(workspace / "validation.json"), "ownership": str(evidence_path)}
        if review.is_file():
            item["review"] = str(review)
        if evidence['state_packets'].get('covered'):
            folder = Path(evidence['state_packets']['covered']['directory'])
            item.update(solid=str(folder/'solid.png'), textured=str(folder/'textured.png'),
                        context=str(folder/'context.png'))
        if evidence['state_packets'].get('revealed'):
            folder = Path(evidence['state_packets']['revealed']['directory'])
            item.update(revealed_solid=str(folder/'solid.png'), revealed_textured=str(folder/'textured.png'),
                        revealed_context=str(folder/'context.png'))
        items.append(item)
        for key, packet in evidence['state_packets'].items():
            if not key.startswith('animation-'):
                continue
            folder = Path(packet['directory'])
            state_item = {**item, 'id': asset['id'] + '--' + key,
                          'name': asset['name'] + ' — ' + key.removeprefix('animation-').replace('-', ' '),
                          'parent_asset_id': asset['id'],
                          'notes': ['Additional state view for ' + asset['id'] + '.'] + list(item['notes']),
                          'solid': str(folder / 'solid.png'),
                          'textured': str(folder / 'textured.png'),
                          'context': str(folder / 'context.png')}
            for field in ('revealed_solid', 'revealed_textured', 'revealed_context'):
                state_item.pop(field, None)
            items.append(state_item)
        progress.append({**row, "status": status, "geometry_refined": evidence["geometry_refined"],
                         "geometry_reviewed": evidence["geometry_reviewed"],
                         "review_outcome": evidence["review_outcome"], "user_approval": user_approval})
    manifest = output.parent / (output.name + "-candidates.json")
    progress_path = output.parent / (output.name + "-progress.json")
    counts = dict(Counter(item["status"] for item in progress))
    shared_gallery = Path(__file__).resolve().parents[2] / 'refinement/blender/build_review_gallery.py'
    gallery_tooling = {'path': str(shared_gallery), 'sha256': sha(shared_gallery)}
    write(manifest, {"version": 1, "map": "Nottingham", "items": items, "tooling": tooling,
                     'gallery_tooling': gallery_tooling, 'total_groups': len(ids) - 1,
                     'supplemental_count': 1, 'status_counts': counts,
                     'without_packets': [row for row in progress if row['status'] in ('missing', 'validation-pending')]})
    write(progress_path, {"version": 1, "map": "Nottingham", "catalog": str(args.catalog.resolve()),
                         "catalog_sha256": sha(args.catalog), "total_assets": len(ids),
                         "gallery_assets": sum('parent_asset_id' not in item for item in items),
                         "gallery_cards": len(items), "counts": counts, "assets": progress,
                         "approval_records": str(args.approvals.resolve()) if args.approvals else None,
                         "approval_records_sha256": sha(args.approvals) if args.approvals else None,
                         "tooling": tooling,
                         "complete": len(progress) > 0 and all(row["status"] == "approved" for row in progress)})
    spec = importlib.util.spec_from_file_location('_shared_review_gallery', shared_gallery)
    gallery_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gallery_module)
    gallery_module.build(manifest, output, pending_only=True, map_name="Nottingham")
    print(json.dumps({"progress": str(progress_path), "counts": counts,
                      "gallery": str(output / "index.html")}))


if __name__ == "__main__":
    main()
