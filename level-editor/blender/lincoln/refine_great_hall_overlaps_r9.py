"""Round-9 recipe: remove the visible near-coplanar great-hall overlaps the round-8 detector missed.

    /usr/bin/blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/refine_great_hall_overlaps_r9.py -- <workspace> <approved-model-sha256>

Starts from the approved round-8 model (`model.blend` must match the given hash). Round 8 compared
whole polygons by the plane offset at their first vertex and only same-facing normals, which missed:

- faces made non-planar when a neighbouring face's shared vertices moved (256#76 lies 0.2 px from
  261#74 over most of its area but 2.3 px at its first vertex);
- open sheets (270, 253, 240, ...) whose normals point into the volume they cover: the pair is
  opposed by normal, yet both sides render (double-sided materials), so it z-fights.

Detection is per triangle: two triangles of different polygons with parallel planes (either sign),
outlines overlapping in that plane, and a plane gap of at most 1.5 px at every corner of the overlap
region. A region z-fights only where it can be seen, so each region is tested for exposure on both
sides of its plane: rays from points of the region, lifted past both faces, into a hemisphere of
directions on that side, against every mesh near the hall (the pair's own two polygons are
transparent to the test). A side is exposed when any ray leaves the neighbourhood. Contacts enclosed
on both sides (stacked volumes, undersides standing on the rock) stay flush on purpose so no gaps
open. Pairs overlapping by more than 0.5 px² with any exposed region are fixed.

For each pair one polygon (the mover) is inset so its whole outline ends 2 px behind the fixed plane
as seen from the exposed side (from the source camera's side when both are exposed):

- mover and fixed as agreed with lincoln-states: 237 behind 272; 270 behind 253 and 240; 256 behind
  261, 262 (spire, never edited) and 233; otherwise the polygon with fewer source-projected texels
  moves, ties move the smaller volume.

Moving a polygon translates its vertices (closed volumes stay closed for lincoln-states' manifold
cuts), iterating until the detector finds nothing. Only great-hall meshes change. Writes
inspection/overlaps-r9.json.
"""
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
import sys

TOLERANCE, MIN_AREA, GAP = 1.5, 0.5, 2.0
PARALLEL = 1 - 1e-3
NEIGHBOURHOOD = 900.0  # px around the hall meshes that can enclose a contact
ASSET, SPIRE = 'lincoln-great-hall', 'lincoln-great-hall-slate-spire'


def triangles(objects):
    rows = []
    for obj in objects:
        mesh, matrix = obj.data, obj.matrix_world
        mesh.calc_loop_triangles()
        for triangle in mesh.loop_triangles:
            points = [matrix @ mesh.vertices[i].co for i in triangle.vertices]
            normal = (points[1] - points[0]).cross(points[2] - points[0])
            if normal.length < 1e-6:
                continue
            rows.append((obj, triangle.polygon_index, normal.normalized(), points))
    return rows


class Surroundings:
    """BVH of every visible mesh near the hall, mapping triangles back to (object name, polygon)."""

    def __init__(self, objects, low, high):
        from mathutils import Vector
        from mathutils.bvhtree import BVHTree
        vertices, faces, self.owner = [], [], []
        for obj in objects:
            box = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
            if any(min(p[i] for p in box) > high[i] or max(p[i] for p in box) < low[i] for i in range(3)):
                continue
            mesh, matrix = obj.data, obj.matrix_world
            mesh.calc_loop_triangles()
            base = len(vertices)
            vertices.extend(matrix @ v.co for v in mesh.vertices)
            for triangle in mesh.loop_triangles:
                faces.append([base + i for i in triangle.vertices])
                self.owner.append((obj.name, triangle.polygon_index))
        self.tree = BVHTree.FromPolygons(vertices, faces, all_triangles=True)
        self.low, self.high = low, high
        golden = math.pi * (3 - math.sqrt(5))
        self.directions = []
        for i in range(64):
            z = 1 - 2 * (i + 0.5) / 64
            r = math.sqrt(1 - z * z)
            self.directions.append((r * math.cos(golden * i), r * math.sin(golden * i), z))

    def escapes(self, origin, direction, transparent):
        position = origin
        for _ in range(16):
            location, _, index, _ = self.tree.ray_cast(position, direction, 4 * NEIGHBOURHOOD)
            if location is None:
                return True
            if self.owner[index] not in transparent:
                return False
            position = location + direction * 0.01
        return False

    def exposed(self, points, side, lift, transparent):
        from mathutils import Vector
        for point in points:
            origin = point + side * lift
            for d in self.directions:
                direction = Vector(d)
                if direction.dot(side) > 0.1 and self.escapes(origin, direction, transparent):
                    return True
        return False


def overlapping_pairs(objects, surroundings):
    """{(side A, side B): [overlap px², kind, exposed sides]} for pairs with an exposed region; a side is (object, polygon index)."""
    import numpy as np
    from refine_great_hall_overlaps import area, clip
    rows = triangles(objects)
    normals = np.array([list(r[2]) for r in rows])
    low = np.array([[min(p[i] for p in r[3]) for i in range(3)] for r in rows])
    high = np.array([[max(p[i] for p in r[3]) for i in range(3)] for r in rows])
    owner = np.array([id(r[0]) for r in rows])
    polygon = np.array([r[1] for r in rows])
    candidates = ((np.abs(normals @ normals.T) > PARALLEL)
                  & np.all(low[:, None, :] <= high[None, :, :] + TOLERANCE, axis=2)
                  & np.all(low[None, :, :] <= high[:, None, :] + TOLERANCE, axis=2)
                  & ~((owner[:, None] == owner[None, :]) & (polygon[:, None] == polygon[None, :])))
    found = {}
    for a, b in zip(*np.nonzero(np.triu(candidates, 1))):
        A, B = rows[a], rows[b]
        normal = A[2]
        axis = (A[3][1] - A[3][0]).normalized()
        other = normal.cross(axis)
        region = clip([(p.dot(axis), p.dot(other)) for p in A[3]], [(p.dot(axis), p.dot(other)) for p in B[3]])
        if len(region) < 3 or area(region) <= 1e-3:
            continue
        base, plane_b, offset_b = normal.dot(A[3][0]), B[2], B[2].dot(B[3][0])
        points, gaps = [], []
        for u, v in region:
            point = axis * u + other * v + normal * base
            points.append(point)
            gaps.append((offset_b - plane_b.dot(point)) / plane_b.dot(normal))
        if max(abs(g) for g in gaps) > TOLERANCE:
            continue
        centre = sum(points, points[0] * 0) / len(points)
        samples = [centre] + [centre + (p - centre) * 0.8 for p in points]
        transparent = {(A[0].name, A[1]), (B[0].name, B[1])}
        lift = max(max(gaps), 0) + 0.5, max(-min(gaps), 0) + 0.5
        sides = [side for side, up in ((normal, lift[0]), (-normal, lift[1]))
                 if surroundings.exposed(samples, side, up, transparent)]
        key = tuple(sorted(((A[0], A[1]), (B[0], B[1])), key=lambda s: (s[0].name, s[1])))
        record = found.setdefault(key, [0.0, 'same-facing' if A[2].dot(B[2]) > 0 else 'opposed', []])
        record[0] += area(region)  # whole overlap of the pair; any exposed region makes the pair visible
        # exposed sides relative to the key's first polygon normal
        first = normal if key[0] == (A[0], A[1]) else B[2]
        for side in sides:
            tag = 1 if side.dot(first) > 0 else -1
            if tag not in record[2]:
                record[2].append(tag)
    return {key: record for key, record in found.items() if record[0] > MIN_AREA and record[2]}


def polygon_normal(obj, index):
    return (obj.matrix_world.to_3x3().inverted().transposed() @ obj.data.polygons[index].normal).normalized()


def hall_surroundings(bpy, meshes):
    from mathutils import Vector
    corners = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    low = [min(p[i] for p in corners) - NEIGHBOURHOOD for i in range(3)]
    high = [max(p[i] for p in corners) + NEIGHBOURHOOD for i in range(3)]
    from global_reproject import covered_state_mesh
    scene_meshes = [o for o in bpy.data.collections['lincoln Working'].all_objects
                    if o is not None and o.type == 'MESH' and not o.hide_render and covered_state_mesh(o)]
    return Surroundings(scene_meshes, low, high)


def hall_meshes(bpy):
    from global_reproject import covered_state_mesh
    return [o for o in bpy.data.collections['lincoln Working'].all_objects
            if o is not None and o.type == 'MESH' and not o.hide_render and o.get('asset_group') in (ASSET, SPIRE)
            and covered_state_mesh(o)]


def main(workspace, approved_sha):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'refinement'))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from render_slots import acquire
    acquire()
    import bpy
    from global_reproject import Scene, TOWARD
    from mathutils import Vector
    import refine_great_hall_overlaps as round8
    workspace = Path(workspace).resolve()
    model = workspace / 'model.blend'
    if hashlib.sha256(model.read_bytes()).hexdigest() != approved_sha:
        raise ValueError('model.blend is not the approved round-8 great-hall model')
    bpy.ops.wm.open_mainfile(filepath=str(model))
    bpy.context.window.scene = bpy.data.scenes['lincoln Refinement']
    meshes = hall_meshes(bpy)
    if any(o.get('round9_overlap_fix') for o in meshes):
        raise ValueError('Round-9 overlap fix already applied; start from the approved round-8 model')
    round8.known_texels.scene = Scene()
    toward = Vector(TOWARD.tolist())
    volume = {o: o.dimensions.x * o.dimensions.y * o.dimensions.z for o in meshes}
    node = lambda side: f"{side[0].get('source_node')}#{side[1]}"
    log, moved_faces, texels = [], defaultdict(int), {}
    for iteration in range(15):
        pairs = overlapping_pairs(meshes, hall_surroundings(bpy, meshes))
        editable = {k: v for k, v in pairs.items() if ASSET in (k[0][0].get('asset_group'), k[1][0].get('asset_group'))}
        log.append({'iteration': iteration, 'pairs': len(editable),
                    'spire_internal_pairs': sorted(f'{node(a)}/{node(b)}' for a, b in pairs if (a, b) not in editable)})
        print('ITERATION', iteration, len(editable), flush=True)
        if not editable:
            break
        shifts = {}
        for (A, B), (overlap, kind, exposed) in sorted(editable.items(), key=lambda kv: (node(kv[0][0]), node(kv[0][1]))):
            na, nb = A[0].get('source_node'), B[0].get('source_node')
            if (na, nb) in round8.EXPLICIT:
                mover, fixed, reason = A, B, 'agreed with lincoln-states'
            elif (nb, na) in round8.EXPLICIT:
                mover, fixed, reason = B, A, 'agreed with lincoln-states'
            else:
                for side in (A, B):
                    if side[0] not in texels:
                        texels[side[0]] = round8.known_texels(side[0])
                ka, kb = texels[A[0]].get(A[1], 0), texels[B[0]].get(B[1], 0)
                if ka != kb:
                    mover, fixed = (A, B) if ka < kb else (B, A)
                    reason = f'fewer source texels ({min(ka, kb)} vs {max(ka, kb)})'
                else:
                    mover, fixed = (A, B) if volume[A[0]] <= volume[B[0]] else (B, A)
                    reason = 'equal source texels; smaller volume moves'
            if mover[0].get('asset_group') != ASSET:
                mover, fixed, reason = fixed, mover, 'the slate spire is never edited'
            first = polygon_normal(*A)
            sides = [first * tag for tag in exposed]
            viewer = sides[0] if len(sides) == 1 else (first if first.dot(toward) > 0 else -first)
            direction = -viewer
            fixed_normal = polygon_normal(*fixed)
            fixed_corners = [fixed[0].matrix_world @ fixed[0].data.vertices[i].co for i in fixed[0].data.polygons[fixed[1]].vertices]
            corners = [mover[0].matrix_world @ mover[0].data.vertices[i].co for i in mover[0].data.polygons[mover[1]].vertices]
            # every mover corner ends GAP behind every corner of the (possibly non-planar) fixed polygon
            depth = max(0.0, GAP + max(q.dot(direction) for q in fixed_corners) - min(p.dot(direction) for p in corners))
            key = (mover[0], mover[1])
            if key not in shifts or shifts[key][1] < depth:
                shifts[key] = (direction, depth)
            log.append({'moving': node(mover), 'fixed': node(fixed), 'kind': kind, 'exposed_sides': len(sides),
                        'overlap_px2': round(overlap, 1), 'inset': round(depth, 3), 'reason': reason,
                        'direction': [round(c, 3) for c in direction], 'fixed_normal': [round(c, 3) for c in fixed_normal]})
        displacement = defaultdict(dict)
        for (obj, index), (direction, depth) in shifts.items():
            step = obj.matrix_world.to_3x3().inverted() @ (direction * depth)
            for vertex in obj.data.polygons[index].vertices:
                current = displacement[obj].get(vertex)
                displacement[obj][vertex] = step if current is None else current + step
            moved_faces[(obj.get('source_node'), index)] += 1
        for obj, vertices in displacement.items():
            for index, step in vertices.items():
                obj.data.vertices[index].co += step
            obj.data.update()
        texels = {}
    remaining = {k: v for k, v in overlapping_pairs(meshes, hall_surroundings(bpy, meshes)).items()
                 if ASSET in (k[0][0].get('asset_group'), k[1][0].get('asset_group'))}
    (workspace / 'inspection').mkdir(exist_ok=True)
    if remaining:
        debug = [{'a': node(a), 'b': node(b), 'kind': kind, 'overlap_px2': round(o, 1)} for (a, b), (o, kind, _) in remaining.items()]
        (workspace / 'inspection' / 'overlaps-r9-failed.json').write_text(json.dumps({'log': log, 'remaining': debug}, indent=2))
        raise RuntimeError(f'{len(remaining)} visible near-coplanar pairs remain')
    report = {'tolerance_px': TOLERANCE, 'min_overlap_px2': MIN_AREA, 'gap_px': GAP, 'approved_round8_model_sha256': approved_sha,
              'log': log, 'moved_faces': [f'{n}#{p}' for (n, p) in sorted(moved_faces)], 'remaining_pairs': 0}
    for obj in meshes:
        if obj.get('asset_group') == ASSET:
            obj['round9_overlap_fix'] = json.dumps({'faces_moved': sum(1 for (n, _) in moved_faces if n == obj.get('source_node'))})
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(model))
    (workspace / 'inspection' / 'overlaps-r9.json').write_text(json.dumps(report, indent=2) + '\n')
    print('ROUND9 OVERLAPS', json.dumps({'moved_faces': len(report['moved_faces']),
                                         'iterations': [r['pairs'] for r in log if 'iteration' in r]}), flush=True)


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:]
    main(args[0], args[1])
