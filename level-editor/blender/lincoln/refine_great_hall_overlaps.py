"""Round-8 recipe: remove coplanar (z-fighting) overlaps between great-hall volumes.

    /usr/bin/blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/refine_great_hall_overlaps.py -- <workspace>

Same-facing faces of two different great-hall volumes (or a great-hall volume and the slate-spire
body 262) that lie within 1.5 px of one plane and overlap by more than 0.5 px² z-fight in every
view. For each such pair one side is inset behind the other; the drawn outer face never moves:

- explicit decisions agreed with lincoln-states (their state cuts key on these volumes): 237 moves
  behind 272; 270 behind 253 and 240; 256 behind 261, 262 (spire, never edited) and 233;
- otherwise the face holding fewer source-projected texels moves (the drawn face keeps its place);
  ties move the smaller volume (a nested or duplicate piece).

Moving a face translates its vertices along its inward normal until it sits 2 px behind the
other face, so closed volumes stay closed (lincoln-states' manifold cuts need that). Opposed
coplanar contacts (a volume's top touching the bottom of the one above it) and coincident
downward undersides standing on one support plane are hidden, not z-fighting, and are kept flush
so no gaps open under or between stacked volumes. Only great-hall meshes
change; source_node, asset_group and projection_component stay. Pairs inside the slate spire
asset itself are reported, not edited (a separate asset card). Iterates until no same-facing
pair remains, then writes inspection/overlaps.json and runs nothing else (run `modified` next).
"""
import json
from collections import defaultdict
from pathlib import Path
import sys

TOLERANCE, MIN_AREA, GAP = 1.5, 0.5, 2.0  # editor depth precision z-fights faces ~1 px apart
ASSET, SPIRE = 'lincoln-great-hall', 'lincoln-great-hall-slate-spire'
EXPLICIT = {  # (moving node, fixed node)
    ('building-237', 'building-272'), ('building-270', 'building-253'), ('building-270', 'building-240'),
    ('building-256', 'building-261'), ('building-256', 'building-262'), ('building-256', 'building-233')}


def area(points):
    return 0.5 * abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])))


def clip(subject, clipper):
    """Sutherland-Hodgman against a triangle."""
    if area(clipper) == 0:
        return []
    if sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(clipper, clipper[1:] + clipper[:1])) < 0:
        clipper = clipper[::-1]
    inside = lambda p, a, b: (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-9

    def cross(p, q, a, b):
        (x1, y1), (x2, y2), (x3, y3), (x4, y4) = p, q, a, b
        den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(den) < 1e-12:
            return q
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    output = subject
    for a, b in zip(clipper, clipper[1:] + clipper[:1]):
        points, output = output, []
        if not points:
            break
        previous = points[-1]
        for point in points:
            if inside(point, a, b):
                if not inside(previous, a, b):
                    output.append(cross(previous, point, a, b))
                output.append(point)
            elif inside(previous, a, b):
                output.append(cross(previous, point, a, b))
            previous = point
    return output


def fans(points):
    return [[points[0], points[i], points[i + 1]] for i in range(1, len(points) - 1)]


def faces_of(objects):
    rows = []
    for obj in objects:
        matrix, normal_matrix = obj.matrix_world, obj.matrix_world.to_3x3().inverted().transposed()
        for polygon in obj.data.polygons:
            if polygon.area < 1e-4:
                continue
            points = [matrix @ obj.data.vertices[i].co for i in polygon.vertices]
            normal = (normal_matrix @ polygon.normal).normalized()
            rows.append((obj, polygon.index, normal, points, normal.dot(points[0])))
    return rows


def same_facing_pairs(objects):
    import numpy as np
    rows = faces_of(objects)
    normals = np.array([list(r[2]) for r in rows])
    offsets = np.array([r[4] for r in rows])
    low = np.array([[min(p[i] for p in r[3]) for i in range(3)] for r in rows])
    high = np.array([[max(p[i] for p in r[3]) for i in range(3)] for r in rows])
    candidates = ((normals @ normals.T > 1 - 1e-3) & (np.abs(offsets[:, None] - offsets[None, :]) <= TOLERANCE)
                  & np.all(low[:, None, :] <= high[None, :, :] + TOLERANCE, axis=2)
                  & np.all(low[None, :, :] <= high[:, None, :] + TOLERANCE, axis=2))
    candidates &= (normals[:, 2] >= -0.99)[:, None]  # downward undersides resting on one support plane stay flush
    pairs = []
    for a, b in zip(*np.nonzero(np.triu(candidates, 1))):
        A, B = rows[a], rows[b]
        axis = (A[3][1] - A[3][0]).normalized()
        other = A[2].cross(axis)
        pa = [(p.dot(axis), p.dot(other)) for p in A[3]]
        pb = [(p.dot(axis), p.dot(other)) for p in B[3]]
        overlap = sum(area(c) for ta in fans(pa) for tb in fans(pb) for c in [clip(ta, tb)] if len(c) >= 3)
        if overlap > MIN_AREA:
            pairs.append((A, B, overlap))
    return pairs


def known_texels(obj):
    """Interior texels per face that hold source projection (not the neutral shade)."""
    from global_reproject import Scene, read_image, islands, slot_uvs, neutral_mask
    import numpy as np
    counts = {}
    record = next(r for r in known_texels.scene.meshes if r['object'] is obj)
    for slot in np.unique(record['slots']):
        binding = known_texels.scene.slot_binding(obj, int(slot))
        if not binding or binding['kind'] != 'ownership':
            continue
        atlas = read_image(binding['image'])
        uv = slot_uvs(obj, binding['uv'])
        faces = record['slots'] == slot
        for face, ty, tx, _, normals, inner in islands(record, uv, (atlas.shape[1], atlas.shape[0]),
                                                       lambda group: faces[group[0]]):
            mask = neutral_mask(atlas, ty, tx, normals, record['face_normals'][face])
            counts[face] = int((~mask & inner).sum())
    return counts


def main(workspace):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'refinement'))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from render_slots import acquire
    acquire()
    import bpy
    from global_reproject import Scene
    workspace = Path(workspace).resolve()
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'))
    bpy.context.window.scene = bpy.data.scenes['lincoln Refinement']
    meshes = [o for o in bpy.data.collections['lincoln Working'].all_objects
              if o.type == 'MESH' and not o.hide_render and o.get('asset_group') in (ASSET, SPIRE)]
    if any(o.get('round8_overlap_fix') for o in meshes):
        raise ValueError('Round-8 overlap fix already applied; start from the prepared model')
    known_texels.scene = Scene()
    texels = {}
    volume = {o: o.dimensions.x * o.dimensions.y * o.dimensions.z for o in meshes}
    log, moved_faces = [], defaultdict(int)
    for iteration in range(10):
        pairs = same_facing_pairs(meshes)
        log.append({'iteration': iteration, 'same_facing_pairs': len(pairs)})
        if not pairs:
            break
        shifts = defaultdict(lambda: None)
        spire_only = [(A, B) for A, B, _ in pairs if ASSET not in (A[0].get('asset_group'), B[0].get('asset_group'))]
        pairs = [row for row in pairs if ASSET in (row[0][0].get('asset_group'), row[1][0].get('asset_group'))]
        log[-1]['spire_internal_pairs'] = sorted({f"{A[0].get('source_node')}/{B[0].get('source_node')}" for A, B in spire_only})
        if not pairs:
            break
        for A, B, overlap in pairs:
            na, nb = A[0].get('source_node'), B[0].get('source_node')
            if (na, nb) in EXPLICIT:
                mover, fixed, reason = A, B, 'agreed with lincoln-states'
            elif (nb, na) in EXPLICIT:
                mover, fixed, reason = B, A, 'agreed with lincoln-states'
            else:
                for side in (A, B):
                    if side[0] not in texels:
                        texels[side[0]] = known_texels(side[0])
                ka, kb = texels[A[0]].get(A[1], 0), texels[B[0]].get(B[1], 0)
                if ka != kb:
                    mover, fixed = (A, B) if ka < kb else (B, A)
                    reason = f'fewer source texels ({min(ka, kb)} vs {max(ka, kb)})'
                else:
                    mover, fixed = (A, B) if volume[A[0]] <= volume[B[0]] else (B, A)
                    reason = 'equal source texels; smaller volume moves'
            if mover[0].get('asset_group') != ASSET:
                mover, fixed, reason = fixed, mover, 'the slate spire is never edited'
            depth = GAP + (mover[4] - fixed[4])  # ends exactly GAP behind the fixed face
            key = (mover[0], mover[1])
            if shifts[key] is None or shifts[key][1] < depth:
                shifts[key] = (mover[2], depth)
            log.append({'moving': f"{mover[0].get('source_node')}#{mover[1]}", 'fixed': f"{fixed[0].get('source_node')}#{fixed[1]}",
                        'overlap_px2': round(overlap, 1), 'inset': round(depth, 3), 'reason': reason})
        displacement = defaultdict(dict)
        for (obj, polygon), (normal, depth) in shifts.items():
            inverse = obj.matrix_world.to_3x3().inverted()
            for vertex in obj.data.polygons[polygon].vertices:
                current = displacement[obj].get(vertex)
                step = inverse @ (-normal * depth)
                displacement[obj][vertex] = step if current is None else current + step
            moved_faces[(obj.get('source_node'), polygon)] += 1
        for obj, vertices in displacement.items():
            for index, step in vertices.items():
                obj.data.vertices[index].co += step
            obj.data.update()
        texels = {}
    remaining = [row for row in same_facing_pairs(meshes)
                 if ASSET in (row[0][0].get('asset_group'), row[1][0].get('asset_group'))]
    spire_internal = sorted({f"{A[0].get('source_node')}/{B[0].get('source_node')}" for A, B, _ in same_facing_pairs(meshes)
                             if ASSET not in (A[0].get('asset_group'), B[0].get('asset_group'))})
    if remaining:
        debug = [{'a': f"{A[0].get('source_node')}#{A[1]}", 'b': f"{B[0].get('source_node')}#{B[1]}",
                  'normal': [round(c, 3) for c in A[2]], 'offsets': [round(A[4], 3), round(B[4], 3)], 'overlap': round(o, 1)}
                 for A, B, o in remaining]
        (workspace / 'inspection').mkdir(exist_ok=True)
        (workspace / 'inspection' / 'overlaps-failed.json').write_text(json.dumps({'log': log, 'remaining': debug}, indent=2))
        raise RuntimeError(f'{len(remaining)} same-facing coplanar pairs remain')
    report = {'tolerance_px': TOLERANCE, 'min_overlap_px2': MIN_AREA, 'gap_px': GAP, 'log': log,
              'moved_faces': [f'{n}#{p}' for (n, p) in sorted(moved_faces)], 'remaining_same_facing_pairs': 0,
              'spire_internal_pairs_not_edited': spire_internal}
    for obj in meshes:
        if obj.get('asset_group') == ASSET:
            obj['round8_overlap_fix'] = json.dumps({'faces_moved': sum(1 for (n, _) in moved_faces
                                                                      if n == obj.get('source_node'))})
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
    (workspace / 'inspection').mkdir(exist_ok=True)
    (workspace / 'inspection' / 'overlaps.json').write_text(json.dumps(report, indent=2) + '\n')
    print('ROUND8 OVERLAPS', json.dumps({k: report[k] for k in ('moved_faces', 'remaining_same_facing_pairs')}), flush=True)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1])
