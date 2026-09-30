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
outlines overlapping in that plane by a region at least 0.25 px wide, and a plane gap of at most 1.5 px at every corner of the overlap
region. A region z-fights only where it can be seen, so each region is tested for exposure on both
sides of its plane: rays from points of the region, lifted past both faces, into a hemisphere of
directions on that side, against every mesh near the hall (the pair's own two polygons are
transparent to the test). A side is exposed when any ray leaves the neighbourhood. Contacts enclosed
on both sides (stacked volumes, undersides standing on the rock) stay flush on purpose so no gaps
open. Pairs overlapping by more than 0.5 px² with any exposed region are fixed.

For each pair one polygon gives way: the part of it lying on the other polygon is cut out
(split along the other polygon's triangle edges, pieces inside removed). The other surface already
draws that area, so nothing else moves: round 8 inset faces by translating their vertices, which
bent and skewed neighbouring faces and opened slivers; this round moves no vertex.

- which side gives way, as agreed with lincoln-states: 237 behind 272; 270 behind 253 and 240; 256
  behind 261, 262 (spire, never edited) and 233; otherwise the polygon with fewer source-projected
  texels, ties the smaller volume.

Iterates until the detector finds nothing. Only great-hall meshes change. Writes
inspection/overlaps-r9.json.
"""
import hashlib
import json
import logging
import math
from collections import defaultdict
from pathlib import Path
import sys

TOLERANCE, MIN_AREA, SLIVER = 1.5, 0.5, 0.25  # SLIVER: minimum mean width (px) of an overlap region
logger = logging.getLogger('round9')
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
        perimeter = sum(math.dist(p, q) for p, q in zip(region, region[1:] + region[:1]))
        if 2 * area(region) / perimeter < SLIVER:
            continue  # a seam where two walls meet at a slight angle: narrower than a pixel, nothing to fight over
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


def remove_covered(obj, polygons):
    """Delete the parts of each listed polygon that lie on (within TOLERANCE of) the given world triangles.

    The polygon is triangulated and split along every triangle edge (bisect keeps UVs and splits the shared edges of
    neighbouring faces without moving them) and the pieces inside a triangle are removed: the other
    surface already draws that area, so the pair no longer z-fights and nothing else moves.
    Returns {polygon index: removed area}.
    """
    import bmesh
    inverse = obj.matrix_world.inverted()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    tag = bm.faces.layers.int.new('round9_piece')
    for index in polygons:
        bm.faces[index][tag] = index + 1
    # round 8 bent some polygons; triangles are planar, so each cut piece lies in one plane
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if f[tag]])
    removed = {}
    for index, triangles in polygons.items():
        for world in triangles:
            local = [inverse @ p for p in world]
            normal = (local[1] - local[0]).cross(local[2] - local[0])
            if normal.length < 1e-9:
                continue
            normal.normalize()
            for a, b in ((local[0], local[1]), (local[1], local[2]), (local[2], local[0])):
                pieces = [f for f in bm.faces if f[tag] == index + 1]
                edges = {e for f in pieces for e in f.edges}
                verts = {v for f in pieces for v in f.verts}
                bmesh.ops.bisect_plane(bm, geom=list(pieces) + list(edges) + list(verts), dist=1e-4,
                                       plane_co=a, plane_no=(b - a).cross(normal).normalized())
        doomed = []
        for face in [f for f in bm.faces if f[tag] == index + 1]:
            centre = face.calc_center_median()
            for world in triangles:
                local = [inverse @ p for p in world]
                normal = (local[1] - local[0]).cross(local[2] - local[0])
                if normal.length < 1e-9:
                    continue
                normal.normalize()
                if abs((centre - local[0]).dot(normal)) > TOLERANCE:
                    continue
                signs = [((q - p).cross(centre - p)).dot(normal) for p, q in ((local[0], local[1]), (local[1], local[2]), (local[2], local[0]))]
                if all(s >= -1e-6 for s in signs):
                    doomed.append(face)
                    break
        removed[index] = sum(f.calc_area() for f in doomed)
        if not doomed:
            logger.warning('nothing removed from %s#%d: pieces %s', obj.get('source_node'), index,
                      [(tuple(round(c, 2) for c in obj.matrix_world @ f.calc_center_median()), round(f.calc_area(), 2))
                       for f in bm.faces if f[tag] == index + 1][:12])
        bmesh.ops.delete(bm, geom=doomed, context='FACES')
    bm.faces.layers.int.remove(tag)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return removed


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
    from global_reproject import Scene
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
    volume = {o: o.dimensions.x * o.dimensions.y * o.dimensions.z for o in meshes}
    node = lambda side: f"{side[0].get('source_node')}#{side[1]}"
    log, trimmed_faces, texels = [], defaultdict(float), {}
    for iteration in range(15):
        pairs = overlapping_pairs(meshes, hall_surroundings(bpy, meshes))
        editable = {k: v for k, v in pairs.items() if ASSET in (k[0][0].get('asset_group'), k[1][0].get('asset_group'))}
        log.append({'iteration': iteration, 'pairs': len(editable),
                    'spire_internal_pairs': sorted(f'{node(a)}/{node(b)}' for a, b in pairs if (a, b) not in editable)})
        print('ITERATION', iteration, len(editable), flush=True)
        if not editable:
            break
        cuts = defaultdict(lambda: defaultdict(list))  # mover object -> mover polygon -> fixed triangles (world)
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
                    reason = 'equal source texels; smaller volume gives way'
            if mover[0].get('asset_group') != ASSET:
                mover, fixed, reason = fixed, mover, 'the slate spire is never edited'
            mesh, matrix = fixed[0].data, fixed[0].matrix_world
            mesh.calc_loop_triangles()
            cuts[mover[0]][mover[1]].extend([matrix @ mesh.vertices[i].co for i in t.vertices]
                                            for t in mesh.loop_triangles if t.polygon_index == fixed[1])
            log.append({'removed_from': node(mover), 'behind': node(fixed), 'kind': kind, 'exposed_sides': len(exposed),
                        'overlap_px2': round(overlap, 1), 'reason': reason})
        for obj, polygons in cuts.items():
            removed = remove_covered(obj, polygons)
            for index, area in removed.items():
                trimmed_faces[(obj.get('source_node'), index)] += area
        texels = {}
    remaining = {k: v for k, v in overlapping_pairs(meshes, hall_surroundings(bpy, meshes)).items()
                 if ASSET in (k[0][0].get('asset_group'), k[1][0].get('asset_group'))}
    (workspace / 'inspection').mkdir(exist_ok=True)
    if remaining:
        debug = [{'a': node(a), 'b': node(b), 'kind': kind, 'overlap_px2': round(o, 1)} for (a, b), (o, kind, _) in remaining.items()]
        (workspace / 'inspection' / 'overlaps-r9-failed.json').write_text(json.dumps({'log': log, 'remaining': debug}, indent=2))
        bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'inspection' / 'model-r9-failed.blend'), copy=True)
        raise RuntimeError(f'{len(remaining)} visible near-coplanar pairs remain')
    report = {'tolerance_px': TOLERANCE, 'min_overlap_px2': MIN_AREA, 'approved_round8_model_sha256': approved_sha, 'log': log,
              'trimmed_faces': {f'{n}#{p}': round(a, 1) for (n, p), a in sorted(trimmed_faces.items())}, 'remaining_pairs': 0}
    for obj in meshes:
        if obj.get('asset_group') == ASSET:
            obj['round9_overlap_fix'] = json.dumps({'faces_trimmed': sum(1 for (n, _) in trimmed_faces if n == obj.get('source_node'))})
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(model))
    (workspace / 'inspection' / 'overlaps-r9.json').write_text(json.dumps(report, indent=2) + '\n')
    print('ROUND9 OVERLAPS', json.dumps({'trimmed_faces': len(report['trimmed_faces']),
                                         'trimmed_px2': round(sum(trimmed_faces.values()), 1),
                                         'iterations': [r['pairs'] for r in log if 'iteration' in r]}), flush=True)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    args = sys.argv[sys.argv.index('--') + 1:]
    main(args[0], args[1])
