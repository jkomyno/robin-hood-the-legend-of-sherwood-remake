"""Freeze conservative terrace/background ownership into a new evidence revision.

The ground mask authorizes a flat background receiver, not a terrain heightfield.
Earlier ownership directories are immutable and are never reused or overwritten.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def generate(root, revision="ownership-v2"):
    root = Path(root).resolve()
    if Path(revision).name != revision:
        raise ValueError("Revision must be a directory name")
    output = root / "terrain-inspection" / revision
    if output.exists():
        raise FileExistsError(output)
    source = root / "layers/covered.png"
    image = Image.open(source).convert("RGB")
    size = image.size
    native = root / "source-audit/native-masks/manifest.json"
    inventory = json.loads(native.read_text())
    level_path = root / "source-audit/Leicester.rhp.json"
    level = json.loads(level_path.read_text())
    layers_path = root / "layers/layers.json"
    layers = json.loads(layers_path.read_text())
    states_path = root / "bridge-evidence/native-states/states.json"
    states = json.loads(states_path.read_text())
    forbidden = np.zeros((size[1], size[0]), dtype=bool)
    inputs = []

    def exclude(path, origin, reason):
        path = Path(path)
        mask = Image.open(path).convert("L")
        canvas = Image.new("L", size)
        canvas.paste(mask, tuple(int(value) for value in origin))
        forbidden[:] |= np.asarray(canvas) > 0
        inputs.append({"path": str(path), "sha256": sha(path), "origin": origin, "reason": reason})

    for mask in inventory["masks"]:
        exclude(native.parent / mask["png"], mask["box_top_left"], "native-scenery-occlusion")
    for patch in layers["patches"]:
        if patch.get("graphic"):
            graphic = patch["graphic"]
            exclude(root / "layers" / graphic["alpha"], graphic["bbox"][:2], "base-patch-graphic")
    frame_count = 0
    for patch in states["patches"]:
        for state in patch["states"].values():
            for frame in state["frames"]:
                exclude(states_path.parent / patch["id"] / frame["alpha"], frame["bbox"][:2], "bridge-mechanism-animation-frame")
                frame_count += 1
    if frame_count != 218 or len(states["patches"]) != 6:
        raise ValueError("Expected six reviewed bridge/mechanism profiles and all 218 frames")

    def volume(obstacle):
        canvas = Image.new("L", size)
        draw = ImageDraw.Draw(canvas)
        points = obstacle["points"]
        if len(points) < 3:
            raise ValueError("Terrain exclusion requires a nonempty native volume")
        bottom = [(p["x"], p["y"]-p["z_bottom"]) for p in points]
        top = [(p["x"], p["y"]-p["z_top"]) for p in points]
        draw.polygon(bottom, fill=255)
        draw.polygon(top, fill=255)
        for a in range(len(points)):
            b = (a+1) % len(points)
            draw.polygon([bottom[a], bottom[b], top[b], top[a]], fill=255)
        return np.asarray(canvas) > 0

    others = np.zeros_like(forbidden)
    for index, obstacle in enumerate(level["sight_obstacles"]):
        if index != 123:
            others |= volume(obstacle)
    terrace_obstacle = level["sight_obstacles"][123]
    heights = [p["z_top"] for p in terrace_obstacle["points"]]
    if max(heights)-min(heights) > 1e-4:
        raise ValueError("Terrace is no longer the reviewed constant-height plateau")
    top = Image.new("L", size)
    ImageDraw.Draw(top).polygon([(p["x"], p["y"]-p["z_top"]) for p in terrace_obstacle["points"]], fill=255)

    def erode(mask):
        return np.asarray(Image.fromarray(mask.astype("uint8")*255).filter(ImageFilter.MinFilter(5))) > 0

    terrace = erode((np.asarray(top) > 0) & ~forbidden & ~others)
    ground = erode(~forbidden & ~others & ~volume(terrace_obstacle))
    if (terrace & ground).any() or (terrace & forbidden).any() or (ground & forbidden).any():
        raise RuntimeError("Terrain ownership intersects an excluded source")
    output.mkdir(parents=True)
    masks = []
    for index, (name, accepted) in enumerate((("terrace", terrace), ("ground", ground)), start=9000):
        path = output / (name+".png")
        Image.fromarray(accepted.astype("uint8")*255).save(path)
        masks.append({"index": index, "png": path.name, "box_top_left": [0, 0],
                      "box_size": list(size), "sha256": sha(path)})
        preview = Image.new("RGB", size, (115, 115, 115))
        preview.paste(image, (0, 0), Image.fromarray(accepted.astype("uint8")*255))
        preview.thumbnail((1254, 794))
        preview.save(output / (name+"-known-preview.png"))
    write_json(output / "inventory.json", {"version": 1, "masks": masks})
    assignments = [{"source_node": node, "mask_indices": [index], "reviewed": True,
                    "evidence": "provenance.json; source previews; explicit native volume and scenery exclusions with all bridge/mechanism frames",
                    "review_note": "Planar source receiver only; no hidden depth or semantic object segmentation inferred."}
                   for node, index in (("building-123", 9000), ("ground", 9001))]
    write_json(output / "source-masks.json", {"version": 1, "mask_inventory": "inventory.json",
               "projections": {"exterior": {"state": "Covered Day source; all native scenery masks, all base patch alpha and all 218 bridge/mechanism animation frames excluded conservatively",
                                              "source_sha256": sha(source), "assignments": assignments}}})
    report = {"version": 2, "source_sha256": sha(source), "native_inventory_sha256": sha(native),
              "level_sha256": sha(level_path), "layers_sha256": sha(layers_path),
              "bridge_states_sha256": sha(states_path), "script_sha256": sha(__file__), "inputs": inputs,
              "native_mask_count": len(inventory["masks"]), "animated_frame_count": frame_count,
              "terrace_native_top_height": heights[0], "terrace_outline_points": len(heights),
              "method": "Terrace native top polygon; background complement of every native volume. Both exclude every scenery mask, base-patch alpha and complete bridge/mechanism frame union; eroded two pixels.",
              "accepted_pixels": {"terrace": int(terrace.sum()), "ground": int(ground.sum())},
              "duplicate_ownership": int((terrace & ground).sum()), "excluded_source_overlap": 0,
              "geometry_approval": "pending", "texture_generation": "not-started",
              "limitations": ["Ground is a planar background-artwork receiver, not recovered terrain geometry or semantic segmentation.",
                              "Unmodeled scenery and painted banks may remain in background artwork; they are not approved independent geometry.",
                              "Terrace retaining sides have no accepted pixels; no retaining-wall geometry is authorized by this mask.",
                              "Hidden elevation, water depth and sculpted relief are not inferred from shading.",
                              "Non-bridge ambient animation sequences have not been exported here; current scenery masks remain their only exclusion evidence."]}
    write_json(output / "provenance.json", report)
    for path in output.iterdir():
        path.chmod(0o444)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("level-editor/work/leicester-refinement"))
    parser.add_argument("--revision", default="ownership-v2")
    args = parser.parse_args()
    report = generate(args.root, args.revision)
    print(json.dumps({"accepted_pixels": report["accepted_pixels"], "animated_frames": report["animated_frame_count"]}))


if __name__ == "__main__":
    main()
