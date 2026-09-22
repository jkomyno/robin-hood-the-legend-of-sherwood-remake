"""Source-measured secondary castle corrections and reproducible packet audit.

Run in background Blender with --threads 2. The default renders every assigned
workspace; --finalize records the coordinator's completed visual inspection.
No geometry or texture approval is implied by the worker review.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

EDITOR = Path(__file__).resolve().parents[2]
WORK = EDITOR / "work/nottingham-refinement"
ASSETS = ["castle-east-courtyard-wall", "castle-west-courtyard-wall", "castle-gate-west-tower",
          "castle-approach-ramp", "castle-west-stair", "castle-southwest-stair",
          "castle-east-round-tower", "castle-upper-wall", "castle-courtyard-shelter",
          "castle-entry-steps", "churchyard-wall", "churchyard-graves", "castle-watchtower"]
TAG = "nottingham-secondary-castle-measured-v2"
LIMITS = {
    "castle-east-courtyard-wall": "Curtain follows the source bend but remains a continuous parapet: visible merlons and loopholes are not modeled; no repeated-element phase/count approval.",
    "castle-west-courtyard-wall": "Upper courtyard curtain has the correct structural bend but lacks the visible alternating merlons; source-count and phase correction remains required.",
    "castle-gate-west-tower": "Octagonal tower and adjacent gate supports remain coarse collision volumes. The source shows a curved drum and separate alternating crown merlons; this packet is not ready for geometry approval.",
    "castle-approach-ramp": "The broad ramp and two side walls follow the source incline and landing. Rounded coping and its repeated stone divisions remain unmodeled; contacts below the ramp remain inferred.",
    "castle-west-stair": "Seven source-visible risers replace a ramp whose lower endpoint incorrectly projected into the tower shaft. Hidden stair support depth remains inherited; outer parapet/tower battlements belong to adjacent groups and are not reconstructed here.",
    "castle-southwest-stair": "The source visibly contains a descending stepped flight. The two assigned flat volumes do not represent it. Footprint/elevation ownership is insufficient to replace them reliably; explicit receiver and endpoint review remains required.",
    "castle-east-round-tower": "Five roof facets retain measured source-facing caps, with two inferred rear sectors closing the missing envelope and a two-unit shell. The drum remains polygonal; finial and arrow-loop geometry still require refinement.",
    "castle-upper-wall": "Source includes crenellation along the upper wall and rounded corner towers. Current source volumes preserve broad height/footprint but omit the repeated merlons and finer cylindrical silhouette.",
    "castle-courtyard-shelter": "The source shows a lean-to with three closed timber doors and masonry dividers. Its inherited wall prisms represent those closed bays; roof eaves, narrow door recesses and concealed contacts remain coarse.",
    "castle-entry-steps": "Landing373 underside meets courtyard elevation100. Side components374–376 now form two source-visible risers between heights100 and115. Equal intermediate tread depth is inferred; shared corner endpoints are normalized to remove the overlapping native slivers.",
    "churchyard-wall": "Two coarse wall runs follow the source boundary. Roofs and foliage obscure large sections; no hidden-wall reshaping is justified. Upper coping and adjacent ground contacts remain coarse.",
    "churchyard-graves": "Three source-owned rectangular graves remain coarse prisms. Visible tapered/rounded headstone silhouettes and plinth profiles are not resolved, so no-change inspection is not geometry approval.",
    "castle-watchtower": "Tall source volumes preserve the tower position and height but lack the source crown crenellation, slit openings and fine cap/finial silhouette. Hidden backing remains a coarse depth hypothesis.",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + "\n")


def replace_mesh(obj, vertices, faces):
    import bpy
    import bmesh
    mesh = bpy.data.meshes.new(obj.name + " / measured secondary refinement")
    mesh.from_pydata(vertices, [], faces)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.00001)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    invalid = sum(not edge.is_manifold for edge in bm.edges)
    degenerate = sum(face.calc_area() < 1e-8 for face in bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    if invalid or degenerate:
        raise ValueError(f"Invalid replacement topology {obj.name}: {invalid}/{degenerate}")
    material = bpy.data.materials.get("Nottingham secondary / unknown source")
    if material is None:
        material = bpy.data.materials.new("Nottingham secondary / unknown source")
        material.diffuse_color = (.32, .32, .32, 1)
    mesh.materials.append(material)
    mesh.uv_layers.new(name="UVMap")
    obj.data = mesh
    obj["secondary_castle_recipe"] = TAG
    return {"vertices": len(mesh.vertices), "faces": len(mesh.polygons),
            "nonmanifold_edges": invalid, "degenerate_faces": degenerate}


def native_prism(obj, points, bottom=None, thickness=None):
    from mathutils import Vector
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    inverse = obj.matrix_world.inverted()
    top = [Vector((p["x"], -p["y"] / sine, p["z_top"] / cosine)) for p in points]
    low = [Vector((p.x, p.y, p.z - thickness if thickness is not None else bottom / cosine)) for p in top]
    vertices = [inverse @ p for p in top + low]
    n = len(top)
    faces = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))]
    faces.extend((i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n))
    return replace_mesh(obj, vertices, faces)


def measured_stair(obj, points):
    from mathutils import Vector
    count, lower = 7, 195.0
    points = sorted(points, key=lambda p: p["z_top"])
    low = sorted(points[:2], key=lambda p: p["x"])
    high = sorted(points[2:], key=lambda p: p["x"])
    upper = sum(p["z_top"] for p in high) / 2
    profile = [(0, 0), (0, lower)]
    for i in range(count):
        z = lower + (upper - lower) * (i + 1) / count
        profile.extend([(i / count, z), ((i + 1) / count, z)])
    profile.append((1, 0))
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    inverse = obj.matrix_world.inverted()
    vertices = []
    for a, b in zip(low, high):
        for t, z in profile:
            x, y = a["x"] + t * (b["x"] - a["x"]), a["y"] + t * (b["y"] - a["y"])
            vertices.append(inverse @ Vector((x, -y / sine, z / cosine)))
    n = len(profile)
    faces = [tuple(range(n)), tuple(reversed(range(n, n * 2)))]
    faces.extend((i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n))
    report = replace_mesh(obj, vertices, faces)
    obj["step_count"] = count
    return {**report, "risers": count, "native_lower_before": 100, "native_lower_after": lower,
            "native_upper_after": upper, "source_low_right_anchor": [337, 1313],
            "source_high_right_anchor": [304, 1201],
            "anchor_confidence": "medium; lower boundary traced from the source stair/landing contact"}


def entry_treads(obj, points):
    """Two painted step edges replace the continuous perimeter bevel."""
    from mathutils import Vector
    ordered = sorted(points, key=lambda p: p["z_top"])
    low, high = ordered[:2], ordered[2:]
    def distance(a, b):
        return (a["x"]-b["x"])**2 + (a["y"]-b["y"])**2
    if sum(distance(a,b) for a,b in zip(low,high)) > sum(distance(a,b) for a,b in zip(low,reversed(high))):
        high.reverse()
    lower, upper = 100., 115.
    profile = [(0,lower), (0,107.5), (.5,107.5), (.5,upper), (1,upper), (1,lower)]
    sine, cosine = math.sin(math.radians(35)), math.cos(math.radians(35))
    inverse = obj.matrix_world.inverted()
    vertices=[]
    for a,b in zip(low,high):
        for t,z in profile:
            vertices.append(inverse @ Vector((a["x"]+t*(b["x"]-a["x"]), -(a["y"]+t*(b["y"]-a["y"]))/sine, z/cosine)))
    n=len(profile)
    faces=[tuple(range(n)),tuple(reversed(range(n,n*2)))]
    faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
    result=replace_mesh(obj,vertices,faces)
    obj["step_count"]=2
    return {**result,"risers":2,"native_support_height":100,"native_landing_height":115,
            "source_evidence":"castle-secondary-audit/castle-entry-steps-zoom.png",
            "inference":"Equal depth intermediate tread between measured outer and landing boundaries"}


def apply(workspace):
    import bpy
    from refinement_workspace import _geometry, validate, modified, initialize_working_masks
    config = json.loads((workspace / "workspace.json").read_text())
    asset = config["asset_id"]
    short = asset.removeprefix("nottingham-")
    if short not in ASSETS:
        raise ValueError("Asset outside secondary castle custody")
    initialize_working_masks(workspace)
    validate(workspace)
    objects = list(bpy.data.collections[config["collection_name"]].all_objects)
    targets = [o for o in objects if o.type == "MESH" and o.get("asset_group") == asset]
    before = {o.name: _geometry(o) for o in objects}
    matrices = {o.name: o.matrix_world.copy() for o in targets}
    native = json.loads((WORK / "baseline/nottingham.rhp.json").read_text())["sight_obstacles"]
    changes = []
    for obj in targets:
        number = int(obj["source_node"][9:])
        if obj.get("secondary_castle_recipe") == TAG:
            continue
        result = None
        if short == "castle-west-stair" and number == 351:
            result = measured_stair(obj, native[number]["points"])
            result["change"] = "Correct lower contact elevation and replace continuous ramp with seven measured risers"
        elif short == "castle-east-round-tower" and 355 <= number <= 359:
            points = native[number]["points"]
            if number in (357, 359):
                ring = native[354]["points"]
                peak = {"x": 1348.68, "y": 1281.66, "z_top": 415.79}
                sequence = (6, 5, 4) if number == 357 else (2, 3, 4)
                points = [dict(ring[i], z_top=330.295) for i in sequence] + [peak]
            result = native_prism(obj, points, thickness=2)
            result["change"] = "Replace below-eave roof collision column with two-unit closed roof shell"
        elif short == "castle-entry-steps" and number in (374,375,376):
            landing = native[373]["points"]
            outer_right = {"x": 695.7143, "y": 1292.2926, "z_top": 100.0}
            outer_left = {"x": 555.01337, "y": 1342.6981, "z_top": 100.0}
            if number == 374:
                points = [outer_right, outer_left, landing[2], landing[1]]
            elif number == 375:
                points = [outer_left, {"x": 524.0745, "y": 1314.5175, "z_top": 100.0}, landing[3], landing[2]]
            else:
                points = [outer_right, landing[1], landing[0], {"x": 655.8461, "y": 1256.6023, "z_top": 100.0}]
            result = entry_treads(obj, points)
            result["change"] = "Replace continuous bevel with two measured entry risers at courtyard support elevation100"
        elif short == "castle-entry-steps" and number == 373:
            result = native_prism(obj, native[number]["points"], bottom=100)
            result["change"] = "Raise landing underside from ground0 to adjacent courtyard elevation100"
        if result:
            changes.append({"source_node": obj["source_node"], "object": obj.name, **result,
                            "before_sha256": before[obj.name], "after_sha256": _geometry(obj)})
    if any(before[o.name] != _geometry(o) for o in objects if o not in targets):
        raise ValueError("Outside asset geometry/identity changed")
    drift = max((abs(o.matrix_world[r][c] - matrices[o.name][r][c])
                 for o in targets for r in range(4) for c in range(4)), default=0)
    if drift:
        raise ValueError("World transform drift")
    geometry_report = workspace / "geometry-report.json"
    if changes or not geometry_report.exists():
        write(geometry_report, {"version": 1, "asset_id": asset, "recipe": str(Path(__file__).resolve()),
            "recipe_sha256": sha(__file__), "changes": changes, "world_transform_drift": drift,
            "outside_objects_preserved": len(objects) - len(targets), "native_source_sha256": sha(WORK / "baseline/nottingham.rhp.json"),
            "limitations": [LIMITS[short]], "idempotence": "Replacement tag prevents duplicate geometry on subsequent recipe runs"})
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / "model.blend"))
    modified(workspace)
    review = ("# " + asset + "\n\nSource context and all fixed cameras require visual review before handoff.\n\n" +
              LIMITS[short] + "\n\nSource-only projection is masked; unknown regions remain neutral. No synthesized textures or publication.\n")
    (workspace / "review.md").write_text(review)
    candidate(workspace, reviewed=False)


def candidate(workspace, reviewed):
    config = json.loads((workspace / "workspace.json").read_text())
    asset = config["asset_id"]
    short = asset.removeprefix("nottingham-")
    report = json.loads((workspace / "geometry-report.json").read_text())
    changed = bool(report["changes"])
    data = {"version": 1, "asset_id": asset, "geometry_reviewed": reviewed,
        "geometry_refined": changed, "status": "fix-needed" if reviewed else "refinement-in-progress",
        "inspected_views": list(range(8)) if reviewed else [], "recipe": str(Path(__file__).resolve()),
        "model_sha256": sha(workspace / "model.blend"), "modified_views_sha256": sha(workspace / "modified/views.json"),
        "changes": [row["change"] for row in report["changes"]], "limitations": [LIMITS[short]],
        "no_change_reason": None if changed else "Source crop and eight solid/textured views inspected; remaining mismatch is documented rather than inventing unsupported hidden geometry.",
        "user_approval": "pending"}
    write(workspace / "candidate.json", data)
    if reviewed:
        (workspace / "review.md").write_text("# " + asset + "\n\nInspected original source context plus all eight fixed solid and source-only textured views.\n\n" +
            LIMITS[short] + "\n\n" + ("Changes: " + "; ".join(data["changes"]) if changed else "No geometry change accepted in this pass.") +
            "\n\nSource masks constrain known pixels; neutral-only assignments remain unknown. Remaining limitations prevent ready-for-approval status.\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", nargs="*", choices=ASSETS)
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from render_slots import acquire
    acquire()
    from freeze_tooling import select_tooling
    select_tooling()
    for short in args.assets or ASSETS:
        workspace = WORK / "round-1/assets" / ("nottingham-" + short)
        if args.finalize:
            candidate(workspace, reviewed=True)
        else:
            import bpy
            bpy.ops.wm.open_mainfile(filepath=str(workspace / "model.blend"))
            apply(workspace)
        print("SECONDARY COMPLETE " + short, flush=True)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
