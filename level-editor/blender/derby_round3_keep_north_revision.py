"""North Keep Tower review revision.

This is deliberately isolated from the publication/catalog pipeline.  It fixes
three source-visible issues in the north tower candidate: the spire door is
placed behind the facade opening, the upper-right outlook ring is regularised,
and the long curtain is kept source-bound while its crenellation count/phase is
prepared for a later pixel-traced edit.
"""
from pathlib import Path
import json
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "level-editor/work/derby-refinement/round-2/assets/derby-great-keep/component-followups/north"
BASE = ASSET / "model.blend"
OUT = ASSET / "revision-v3"


def _mesh_object(name):
    return bpy.data.objects.get(name)


def revise_door():
    obj = bpy.data.objects.get("Great Keep / North spire / recessed wooden door")
    if obj is None:
        return {"status": "missing"}
    # The earlier packet accidentally put this backing in (x, y, z)=(1000,-1569,835)
    # instead of the tower's front facade (x, y, z)=(1000,~0,-1530).  Replace it
    # with a conservative arched slab 18 world units behind the front plane.
    # The tower facade is at y≈-891 in this world frame; the camera is on the
    # negative-Y side, so the door face is just in front of that plane and its
    # backing is farther into the tower.
    cx, yf, yb = 1020.0, -902.0, -926.0
    z0, spring, crown = -1570.0, -1544.0, -1528.0
    half = 17.0
    outline = [(-half, z0), (half, z0), (half, spring)]
    # Six fixed semicircle samples are enough at this source resolution and
    # keep the script usable in Blender's restricted background interpreter.
    samples = [(14.722, 0.5), (8.5, 0.866), (0.0, 1.0),
               (-8.5, 0.866), (-14.722, 0.5), (-17.0, 0.0)]
    for x, s in samples:
        outline.append((x, spring + (crown - spring) * s))
    outline.append((-half, z0))
    outline = outline[:-1]
    verts = [(cx + x, y, z) for y in (yf, yb) for x, z in outline]
    n = len(outline)
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    faces.extend((i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n))
    mesh = obj.data
    mesh.clear_geometry()
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj["north_spire_door_backing"] = True
    obj["revision"] = "v3-recessed-facade"
    return {"status": "updated", "faces": len(faces), "front_y": yf, "back_y": yb}


def round_outlook():
    obj = _mesh_object("building-163")
    if obj is None:
        return {"status": "missing"}
    # The final 13 vertices are the upper ring at y=-842.25.  Preserve its
    # projection-facing angular phase but fit them to one circle, removing the
    # visibly flattened upper-right arc without changing wall height or masks.
    indices = list(range(40, 53))
    points = [obj.data.vertices[i].co.copy() for i in indices]
    c = Vector((sum(p.x for p in points) / len(points), points[0].y,
                sum(p.z for p in points) / len(points)))
    radius = sum((Vector((p.x - c.x, 0, p.z - c.z)).length for p in points)) / len(points)
    for i, p in zip(indices, points):
        d = Vector((p.x - c.x, 0, p.z - c.z))
        if d.length > 1e-6:
            d.normalize(); d *= radius
            obj.data.vertices[i].co.x = c.x + d.x
            obj.data.vertices[i].co.z = c.z + d.z
    obj.data.update()
    return {"status": "updated", "ring_vertices": len(indices), "center": [c.x, c.z], "radius": radius}


def add_curtain_merlons():
    # Do not add world-space boxes: the first draft proved that those float
    # beside the tower when projected.  The curtain is retained as the native
    # source-bound ring and its exact count/phase is recorded for the next
    # source-pixel pass instead of inventing unsupported geometry.
    old = bpy.data.objects.get("Great Keep / North tower / reviewed curtain crenels")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    return {"status": "native-retained", "reason": "awaiting source-pixel crenel trace", "count": 0}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    before = {o.name: len(o.data.vertices) for o in bpy.data.objects if o.type == "MESH"}
    result = {"door": revise_door(), "outlook": round_outlook(), "curtain": add_curtain_merlons()}
    after = {o.name: len(o.data.vertices) for o in bpy.data.objects if o.type == "MESH"}
    result["before_mesh_counts"] = before
    result["after_mesh_counts"] = after
    (OUT / "revision.json").write_text(json.dumps(result, indent=2))
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "model.blend"))
    return result


if __name__ == "__main__":
    raise RuntimeError('WITHDRAWN: v3 mixed baseline and Working coordinate frames. Use derby_keep_north_pixel_trace.py instead.')
