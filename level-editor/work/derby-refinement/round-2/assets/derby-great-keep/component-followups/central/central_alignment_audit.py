"""Audit Central Turret/Gallery crenellation and bridge slope.

This is deliberately an audit-only script.  It does not alter meshes, catalog
entries, or projection assignments.  Run it from Blender with ``model.blend``
loaded.  The source landmark coordinates are in the native 1920x2752 artwork
and describe the two visible bridge/deck edges; they are not generic regions.
"""
from __future__ import annotations

import json, math, sys
from pathlib import Path

import bpy
from mathutils import Vector

W = Path(__file__).resolve().parent
OUT = W / "alignment-audit"
OUT.mkdir(exist_ok=True)
OWNED = {f"building-{n:03}" for n in set(range(152, 163)) | {"170", "181"}}

# Exact visible source landmarks selected on the covered source grid.  The
# paired points are the same deck edge at the two ends of the bridge.  They
# constrain image slope while leaving the 3-D mesh untouched.
SOURCE_BRIDGE_LANDMARKS = {
    "upper_edge": {"a": [548, 559], "b": [781, 424],
                   "receiver": "covered central gallery / upper deck edge"},
    "lower_edge": {"a": [559, 586], "b": [792, 452],
                   "receiver": "covered central gallery / lower deck edge"},
}


def _objects(node):
    return [o for o in bpy.data.objects if o.type == "MESH" and
            o.get("source_node") == node and not o.hide_render]


def _world_vertices(objects):
    return [o.matrix_world @ v.co for o in objects for v in o.data.vertices]


def _fit_slope(points):
    """Fit z against the horizontal principal axis (diagnostic only)."""
    if len(points) < 2:
        return {"status": "insufficient-points"}
    centre = sum(points, Vector()) / len(points)
    xy = [Vector((p.x - centre.x, p.y - centre.y)) for p in points]
    # Principal axis of the horizontal footprint.
    xx = sum(v.x * v.x for v in xy); yy = sum(v.y * v.y for v in xy)
    xyv = sum(v.x * v.y for v in xy)
    angle = .5 * math.atan2(2 * xyv, xx - yy)
    axis = Vector((math.cos(angle), math.sin(angle)))
    vals = [((p.x - centre.x) * axis.x + (p.y - centre.y) * axis.y, p.z)
            for p in points]
    mx = sum(v[0] for v in vals) / len(vals)
    mz = sum(v[1] for v in vals) / len(vals)
    den = sum((x - mx) ** 2 for x, _ in vals)
    slope = sum((x - mx) * (z - mz) for x, z in vals) / den if den else 0.0
    residual = math.sqrt(sum((z - (mz + slope * (x - mx))) ** 2
                             for x, z in vals) / len(vals))
    return {"principal_axis_xy": [axis.x, axis.y], "slope_dz_per_world_unit": slope,
            "rms_residual_world_units": residual, "point_count": len(points),
            "range_world_units": [min(x for x, _ in vals), max(x for x, _ in vals)]}


def _profile(node):
    """Return the top-profile samples so a reviewer can count merlons.

    We retain every top-facing vertex and its world position; no attempt is
    made to infer a target count from the artwork.  The prior broad mask audit
    could prove pixel ownership but could not prove that the zigzag phase was
    correct, so this explicit profile is required before a geometry edit.
    """
    obs = _objects(node)
    verts = _world_vertices(obs)
    if not verts:
        return {"node": node, "point_count": 0}
    zmax = max(v.z for v in verts)
    # Keep the upper 3 world units; this captures merlon tops while excluding
    # the long wall body.  The complete samples are still written for review.
    top = [v for v in verts if v.z >= zmax - 3.0]
    return {"node": node, "point_count": len(top),
            "world_points": [[round(v.x, 5), round(v.y, 5), round(v.z, 5)]
                             for v in top], "zmax": zmax}


def main():
    raise RuntimeError('WITHDRAWN: initial bridge landmark lines crossed the courtyard and were invalid. Use trace-v2/review.md and trace-v2/trace-and-slope.json, generated from measured mesh vertices. This script must not be used for a geometry decision.')
    bridge = _world_vertices(_objects("building-160"))
    result = {
        "status": "AUDIT_ONLY",
        "source_landmarks": SOURCE_BRIDGE_LANDMARKS,
        "bridge_world_fit": _fit_slope(bridge),
        "profiles": [_profile("building-153"), _profile("building-158")],
        "interpretation": {
            "bridge": "Image-space diagonal is not evidence of a sloped deck. Review the world fit and both source edge pairs before changing node 160.",
            "zigzag": "Compare profile samples with the two source silhouettes. Do not change merlon count or phase from pixel ownership alone.",
        },
    }
    (OUT / "central-alignment-audit.json").write_text(json.dumps(result, indent=2))
    (OUT / "README.md").write_text(
        "# Central Turret/Gallery alignment audit\n\n"
        "This packet is audit-only. It records the source bridge edge pairs, "
        "the fitted world-space deck slope, and the exact top-profile vertices "
        "for crenellation nodes 153 and 158. A diagonal in the source camera "
        "can arise from orthographic camera elevation, so node 160 is changed "
        "only when the world fit and both source edge pairs disagree. Likewise, "
        "the merlon count/phase is changed only after profile comparison.\n\n"
        "## Existing visual evidence\n\n"
        "- [covered source context](../input/context.png)\n"
        "- [covered source-textured eight views](../input/textured.png)\n"
        "- [covered gray eight views](../input/solid.png)\n"
        "- [current revealed/covered textured views](../modified/textured.png)\n"
        "- [current gray views](../modified/solid.png)\n"
        "- [source bridge landmark check](../source-bridge-landmarks.png)\n\n"
        "The central deck appears diagonal in the source camera.  Review both "
        "edge pairs and the world-space fit before treating that diagonal as a "
        "physical bridge slope.\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
