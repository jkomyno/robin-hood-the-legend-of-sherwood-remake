"""Prepare immutable staged or live library inputs for the private browser audit.

Preserves the live editor document when canonical group and part identities match.
The scope lists asset_ids, already_published, and optional required_patches.
"""
import argparse
import hashlib
import json
from pathlib import Path
from scene_manifest import scene_metadata


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(stage, scope_path, output, *, map_name="leicester", live=False, migration_path=None, document_path=None):
    if document_path is not None and (live or migration_path is not None):
        raise ValueError("Explicit staged document cannot replace live or migration authority")
    stage, output = Path(stage).resolve(), Path(output).resolve()
    scope = json.loads(Path(scope_path).read_text())
    library = Path("level-editor/library").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    live_document = library / f"scenes/{map_name}.level3d.json"
    source_document = Path(document_path).resolve(strict=True) if document_path is not None else live_document
    document = json.loads(source_document.read_text())
    asset_library = library if live else stage / 'map-assets'
    staged_document = document if live else json.loads((stage / f"{map_name}.level3d.json").read_text())
    model = scene_metadata(asset_library, staged_document)
    nodes = model["nodes"]
    map_node = next(node for node in nodes if node.get("name") == "map")
    groups = [nodes[index] for index in map_node["children"] if nodes[index].get("name") != "ground"]
    part_names = {nodes[index]["name"] for group in groups for index in group.get("children", [])}
    if migration_path is not None and not live:
        migration = json.loads(Path(migration_path).read_text())
        if sha(live_document) != migration["prior_document_sha256"]:
            raise ValueError("Editor document changed after migration preparation")
        for evidence in migration.get("evidence", []):
            if sha(Path(evidence["path"])) != evidence["sha256"]:
                raise ValueError("Migration evidence changed")
        group_records = {group["id"]: group for group in document["groups"]}
        objects = {obj["id"]: obj for obj in document["objects"]}
        for transfer in migration.get("group_transfers", []):
            obj = objects[transfer["id"]]
            if obj["group"] != transfer["from"]:
                raise ValueError("Unexpected previous part ownership")
            if group_records[transfer["from"]]["transform"] != group_records[transfer["to"]]["transform"]:
                raise ValueError("Ownership transfer needs explicit world-transform migration")
            obj["group"] = transfer["to"]
            if "name" in transfer:
                obj["name"] = transfer["name"]
        for obj in migration.get("new_objects", []):
            if obj["id"] in objects or obj["node"] not in part_names:
                raise ValueError("New editor part is duplicated or absent from staged scene")
            if obj["group"] not in group_records:
                raise ValueError("New editor part has unknown ownership")
            document["objects"].append(obj)
            objects[obj["id"]] = obj
    if {obj["node"] for obj in document["objects"]} != part_names:
        raise ValueError("Canonical part identities changed; explicit editor document migration required")
    if {group["id"] for group in document["groups"]} != {group["extras"]["asset_group"] for group in groups}:
        raise ValueError("Canonical group identities changed; explicit editor document migration required")
    part_groups = {nodes[index]["name"]: group["extras"]["asset_group"]
                   for group in groups for index in group.get("children", [])}
    if any(obj["group"] != part_groups[obj["node"]] for obj in document["objects"]):
        raise ValueError("Editor part ownership differs from staged canonical hierarchy")
    document_path = live_document
    if not live:
        document["sceneAssets"] = staged_document["sceneAssets"]
        document.pop("glb", None)
        document.setdefault("provenance", {}).pop("glb_sha256", None)
        document_path = stage / "browser-document.level3d.json"
        if document_path.exists():
            if json.loads(document_path.read_text()) != document:
                raise ValueError("Existing staged document differs from current canonical editor state")
        else:
            document_path.write_text(json.dumps(document, indent=2) + "\n")
    sources = {entry["id"]: (entry, library / "3d-assets") for entry in
               json.loads((library / "3d-assets/index.json").read_text())["assets"]}
    if not live:
        sources.update({entry["id"]: (entry, stage / "assets") for entry in
                        json.loads((stage / "assets/index.json").read_text())["assets"]})
    expected_ids = set(scope["asset_ids"]) | set(scope["already_published"])
    if not expected_ids <= sources.keys():
        raise ValueError("Missing expected assets: " + repr(sorted(expected_ids - sources.keys())))
    entries = [sources[identity][0] for identity in sorted(expected_ids)]
    private_index = output.with_name("private-index.json")
    private_index.write_text(json.dumps({"version": 1, "assets": entries}, indent=2) + "\n")
    files, seen = [], set()

    def add(path, source):
        if path in seen:
            return
        source = source.resolve(strict=True)
        files.append({"path": path, "url": "/@fs/" + str(source), "sha256": sha(source)})
        seen.add(path)

    for reference in document["sceneAssets"]:
        add(reference["model"], asset_library / reference["model"])
        for resource in reference["resources"]:
            add(resource["path"], asset_library / resource["path"])
    add(f"scenes/{map_name}.level3d.json", document_path)
    add("3d-assets/index.json", private_index)
    expanded = []
    for entry in entries:
        source = sources[entry["id"]][1]
        descriptor = json.loads((source / entry["descriptor"]).read_text())
        add("3d-assets/" + entry["descriptor"], source / entry["descriptor"])
        add("3d-assets/" + entry["model"], source / entry["model"])
        if entry.get("preview_model"):
            add("3d-assets/" + entry["preview_model"], source / entry["preview_model"])
        variants = descriptor.get("state_variants") or descriptor.get("standalone_variants")
        if not variants:
            expanded.append(entry)
            continue
        if descriptor.get("standalone_variants"):
            expanded.append(entry)
        for state in ("initial", "applied"):
            if state not in variants:
                continue
            variant = variants[state]
            model_path = str(Path(entry["descriptor"]).parent / variant["model"])
            add("3d-assets/" + model_path, source / model_path)
            expanded.append({**entry, "id": entry["id"] + "--state-" + state,
                             "name": entry["name"] + " — " + variant["name"] + " (static)",
                             "model": model_path, "state_variant": state, "base_id": entry["id"],
                             **({"model_scene": variant["model_scene"]} if "model_scene" in variant else {})})
    generated, patches = {}, set()
    for material in model.get("materials", []):
        identity = material.get("extras", {}).get("generated_source_sha256")
        if identity:
            generated[identity] = generated.get(identity, 0) + 1
    for node in nodes:
        extras = node.get("extras", {})
        if extras.get("reveal_material_patch"):
            patches.add(extras["reveal_material_patch"])
        for key in ("reveal_hide_when_applied", "reveal_show_when_applied"):
            patches.update(extras.get(key, []))
    required = scope.get("required_patches", sorted(patches))
    if not set(required) <= patches:
        raise ValueError("Required runtime state triggers missing")
    protected = {str(path): sha(path) for path in library.rglob("*")
                 if path.is_file() and path.suffix in (".json", ".gltf", ".glb", ".bin", ".png", ".jpg")}
    config = {"map": map_name, "mode": "live" if live else "staged", "files": files,
              "expected": {"groups": len(document["groups"]), "parts": len(document["objects"]),
                           "width": document["size"][0], "assets": expanded,
                           "base_asset_ids": sorted(expected_ids), "new_asset_ids": scope["asset_ids"],
                           "generated_materials": generated, "required_patches": required},
              "stage": str(stage), "protected_live_files": protected}
    output.write_text(json.dumps(config, indent=2) + "\n")
    return {"config": str(output), "groups": len(document["groups"]),
            "parts": len(document["objects"]), "palette": len(expanded),
            "files": len(files), "patches": sorted(patches)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", type=Path)
    parser.add_argument("scope", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--map", default="leicester")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--migration", type=Path)
    parser.add_argument("--document", type=Path, help="Explicit canonical staged document for first publication")
    args = parser.parse_args()
    print(json.dumps(prepare(args.stage, args.scope, args.output, map_name=args.map,
                             live=args.live, migration_path=args.migration,
                             document_path=args.document)))
