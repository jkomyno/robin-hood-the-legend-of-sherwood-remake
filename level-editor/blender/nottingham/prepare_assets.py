"""Prepare frozen Nottingham packets in a disposable background Blender process.

Example (append one or more asset IDs to restrict a worker lane)::

    blender --background --python prepare_assets.py -- \
      --source-blend source.blend --output assets --source-path covered.png \
      --grouping-manifest catalog.json --inventory-path inventory.json \
      --review-path grouping-review.json nottingham-market-house

Each asset reopens the frozen source. Existing workspaces are never overwritten.
The initial modified packet establishes a reproducible comparison; it does not
claim that geometry has been refined or approved. Run refinement_workspace.py's
modified command again after the asset's geometry recipe.
Use --prepare-only to render only frozen input, then run modified after edits.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def preflight_source(scene_name, collection_name, catalog):
    """Check the entire projection context before creating any worker files."""
    import bpy
    scene = bpy.data.scenes.get(scene_name)
    collection = bpy.data.collections.get(collection_name)
    if scene is None or collection is None:
        raise ValueError(f"Missing source scene/working collection: {scene_name}/{collection_name}")
    bpy.context.window.scene = scene
    bpy.context.view_layer.update()
    expected = {f"building-{part['obstacle']:03d}": group["id"]
                for group in catalog["groups"] for part in group["parts"]}
    meshes = [obj for obj in collection.all_objects if obj.type == "MESH" and not obj.hide_render]
    errors, checked = [], 0
    if not meshes:
        errors.append("No visible working meshes")
    for obj in meshes:
        node = obj.get("source_node")
        if node == "ground":
            continue
        checked += 1
        prefix = f"{obj.name} ({node!r}): "
        if not node or node not in expected:
            errors.append(prefix + "missing or unknown stable source_node")
        elif obj.get("asset_group") != expected[node]:
            errors.append(prefix + "asset_group differs from reviewed catalog")
        if any(mod.show_render or mod.show_viewport for mod in obj.modifiers):
            errors.append(prefix + "active modifiers must be baked before reprojection")
        mesh = obj.data
        if not mesh.vertices or not mesh.polygons:
            errors.append(prefix + "empty geometry")
        if not mesh.uv_layers or mesh.uv_layers.active is None:
            errors.append(prefix + "missing fallback UV layer")
        if not mesh.materials or any(material is None for material in mesh.materials):
            errors.append(prefix + "missing fallback material")
        if any(face.material_index >= len(mesh.materials) for face in mesh.polygons):
            errors.append(prefix + "invalid face material index")
        fallback = mesh.attributes.get("reprojection_fallback_material")
        if fallback is not None:
            if fallback.domain != "FACE" or fallback.data_type != "INT":
                errors.append(prefix + "invalid fallback material attribute")
            elif any(item.value < 0 or item.value >= len(mesh.materials) for item in fallback.data):
                errors.append(prefix + "invalid fallback material attribute index")
    if errors:
        raise ValueError("Source preflight failed before creating any workspace:\n" + "\n".join(errors))
    return {"status": "PASS", "visible_meshes": len(meshes), "checked_nonground_meshes": checked}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-blend", "output", "source-path", "grouping-manifest",
                 "inventory-path", "review-path"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--projection-manifest", type=Path,
                        help="Reviewed projection layers; raw patch inventories are unsupported")
    parser.add_argument("--source-mask-manifest", type=Path,
                        help="Reviewed receiver assignments, not the native mask inventory")
    parser.add_argument("--scene-name", default="nottingham Refinement")
    parser.add_argument("--collection-name", default="nottingham Working")
    parser.add_argument("--width", type=int, default=384)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--elevation-degrees", type=float, default=35)
    parser.add_argument("--context-padding", type=int, default=24)
    parser.add_argument("--prepare-only", action="store_true",
                        help="Create frozen input and model only; render modified after worker geometry edits")
    parser.add_argument("--tooling-dir", type=Path,
                        help="Frozen helper snapshot; defaults to tooling/current.json")
    parser.add_argument("assets", nargs="*", help="Selected catalog IDs; omit to prepare every asset")
    args = parser.parse_args(argv)
    if min(args.width, args.height) <= 0 or args.context_padding < 0:
        parser.error("Render dimensions must be positive and context padding nonnegative")

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'refinement'))
    from render_slots import acquire
    acquire()
    from freeze_tooling import select_tooling
    tooling = select_tooling(args.tooling_dir)
    import bpy
    from refinement_inventory import validate_catalog
    from refinement_workspace import prepare, modified, validate

    for name in ("source_blend", "source_path", "grouping_manifest", "inventory_path",
                 "review_path", "projection_manifest", "source_mask_manifest"):
        if getattr(args, name) is not None:
            setattr(args, name, getattr(args, name).resolve(strict=True))
    output = args.output.resolve()
    catalog = json.loads(args.grouping_manifest.read_text())
    if catalog.get("map") != "nottingham":
        raise ValueError("This recipe requires a nottingham catalog")
    validate_catalog(args.inventory_path, args.grouping_manifest)
    review = json.loads(args.review_path.read_text())
    if (review.get("status") != "reviewed" or not review.get("reviewer")
            or review.get("catalog_sha256") != sha256(args.grouping_manifest)
            or review.get("inventory_sha256") != sha256(args.inventory_path)):
        raise ValueError("Grouping review is missing or does not match catalog/inventory bytes")
    available = {group["id"] for group in catalog["groups"]}
    assets = args.assets or [group["id"] for group in catalog["groups"]]
    if len(assets) != len(set(assets)) or set(assets) - available:
        raise ValueError("Asset subset contains duplicate or unknown catalog IDs")
    for asset in assets:
        if Path(asset).name != asset or asset in (".", ".."):
            raise ValueError(f"Unsafe workspace ID: {asset}")
        if (output / asset).exists():
            raise FileExistsError(f"Refuse to overwrite existing worker: {output / asset}")

    if args.projection_manifest:
        from interior_layers import validate_projection_reviews
        layers = json.loads(args.projection_manifest.read_text())
        if layers.get("map") != catalog["map"] or layers.get("version") != 1:
            raise ValueError("Projection manifest map/version does not match catalog")
        try:
            validate_projection_reviews(layers, args.projection_manifest.parent)
        except (KeyError, ValueError) as error:
            raise ValueError("Projection manifest requires complete reviewed patch ownership; "
                             "raw coverage candidates are unsupported") from error
    if args.source_mask_manifest:
        from occlusion_constraints import SourceMaskConstraints, evidence_record
        image = bpy.data.images.load(str(args.source_path), check_existing=False)
        try:
            dimensions = tuple(image.size)
        finally:
            bpy.data.images.remove(image)
        constraints = SourceMaskConstraints(args.source_mask_manifest, "exterior",
                                            sha256(args.source_path), dimensions)
        if not constraints.active or not (constraints.assignment_by_node
                or constraints.assignment_by_group or constraints.assignment_by_component):
            raise ValueError("Source-mask manifest requires reviewed exterior assignments")
        evidence_record(args.source_mask_manifest)

    source_hash = sha256(args.source_blend)
    bpy.ops.wm.open_mainfile(filepath=str(args.source_blend))
    preflight = preflight_source(args.scene_name, args.collection_name, catalog)
    scope = ("reviewed projection layers" if args.projection_manifest else
             "static exterior only; revealed and animated state ownership is not validated")
    print(json.dumps({"assets": assets, "scope": scope,
                      "source_blend_sha256": source_hash, "preflight": preflight}), flush=True)
    for asset in assets:
        print(f"PREPARE START {asset}", flush=True)
        if sha256(args.source_blend) != source_hash:
            raise RuntimeError("Frozen source changed during batch")
        bpy.ops.wm.open_mainfile(filepath=str(args.source_blend))
        preflight_source(args.scene_name, args.collection_name, catalog)
        workspace = output / asset
        prepared = prepare(workspace, asset_id=asset,
            scene_name=args.scene_name, collection_name=args.collection_name,
            source_path=args.source_path, grouping_manifest=args.grouping_manifest,
            inventory_path=args.inventory_path, review_path=args.review_path,
            projection_manifest=args.projection_manifest,
            source_mask_manifest=args.source_mask_manifest,
            width=args.width, height=args.height,
            elevation_degrees=args.elevation_degrees, context_padding=args.context_padding)
        validation = validate(workspace) if args.prepare_only else modified(workspace)
        if sha256(args.source_blend) != source_hash:
            raise RuntimeError("Frozen source changed during preparation")
        report = {"version": 1, "asset_id": asset, "scope": scope,
                  "status": "baseline-ready-for-refinement", "user_approval": "pending",
                  "geometry_refined": False, "source_blend_sha256": source_hash,
                  "prepare_only": args.prepare_only, "source_preflight": preflight,
                  "tooling": tooling,
                  "recipe_sha256": sha256(__file__), "argv": sys.argv,
                  "prepared": prepared, "validation": validation}
        (workspace / "preparation.json").write_text(json.dumps(report, indent=2) + "\n")
        print("PREPARE COMPLETE " + json.dumps(report), flush=True)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
