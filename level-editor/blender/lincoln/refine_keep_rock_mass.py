"""Round-8 recipe: one continuous rock mass under the great hall and its approach ramp.

    /usr/bin/blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/refine_keep_rock_mass.py -- <workspace>

The artwork paints one continuous rock face from the keep plateau straight up to the base of the
castle walls. The approved scene instead leaves open space between the rock and the castle: great
hall volumes (233 at ~170 px, 268/258/272/237 at ~240 px) and approach-ramp parts (287/288 at
60-100 px) float above the rock, so oblique views look into a tunnel under the hall.

The recipe starts from the prepared workspace model (`baseline.blend`) and fills that space:

1. Every flat underside (|n.z| > 0.95) of a castle part standing on this rock (great hall, slate
   spire, approach ramp, south terrace, keep annex and its turrets) in the hall/ramp window is
   sampled on an 8 px grid and probed straight down. A sample counts when that underside is the
   first surface above the rock (this asset, the terrain or the ground) and hangs more than 3 px
   above it. Roofs and eaves are never flat undersides; a part standing on another castle part
   never has rock right below it.
2. Each underside with at least 30 % counting samples becomes a rock prism: its outline, 0.5 px
   inside the castle part (2 px below an upward-facing open sheet), extruded straight down to 6 px below the lowest rock under it. Prism
   sides therefore continue the walls above them flush down into the rock. Sides shared by two
   prisms are left out (hidden between them).
3. Sides facing open air are split into ~12 px cells and displaced along their outward normal by
   rock-scale noise of at most ±8 px, weighted to zero at the underside, the bottom and the ends
   of each side, so the rock meets walls and plateau exactly.

The prisms are appended to 465 as separate shells (an exact boolean union with the sculpted,
non-manifold rock returns an empty mesh). Only 465 is edited; the workspace packet bakes its
ownership atlas. Writes inspection/round8-fill.json.
"""
import json
import math
from pathlib import Path
import shutil
import sys

CASTLE = ('lincoln-great-hall', 'lincoln-great-hall-slate-spire', 'lincoln-hall-approach-ramp',
          'lincoln-hall-south-terrace', 'lincoln-keep-annex', 'lincoln-keep-annex-cone-turret',
          'lincoln-keep-annex-round-turret')
ROCK = 'lincoln-castle-hill-keep-plateau'
SUPPORT = (ROCK, 'lincoln-terrain')
REGION = ((1000.0, 1900.0), (-3000.0, -2050.0))  # x, y window around the hall/ramp front
MIN_GAP, SAMPLE, MIN_SHARE, CELL, AMPLITUDE = 3.0, 8.0, 0.3, 12.0, 8.0
TOP_EMBED, SHEET_GAP, BOTTOM_EMBED = 0.5, 2.0, 6.0


def inside(point, polygon):
    x, y = point
    result = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            result = not result
    return result


def main(workspace):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'refinement'))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from render_slots import acquire
    acquire()
    import bpy
    import bmesh
    from mathutils import Vector, noise
    from mathutils.bvhtree import BVHTree
    from global_reproject import covered_state_mesh
    workspace = Path(workspace).resolve()
    shutil.copyfile(workspace / 'baseline.blend', workspace / 'model.blend')
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'))
    working = bpy.data.collections['lincoln Working']
    meshes = [o for o in working.all_objects if o.type == 'MESH' and not o.hide_render and covered_state_mesh(o)]
    targets = [o for o in meshes if o.get('source_node') == 'building-465']
    if len(targets) != 1 or targets[0].get('asset_group') != ROCK:
        raise ValueError('Expected one visible 465 mesh of the merged rock asset')
    target = targets[0]
    vertices, triangles, owners = [], [], []
    for obj in meshes:
        mesh = obj.data
        mesh.calc_loop_triangles()
        offset = len(vertices)
        vertices.extend(obj.matrix_world @ v.co for v in mesh.vertices)
        for tri in mesh.loop_triangles:
            triangles.append(tuple(offset + i for i in tri.vertices))
            owners.append((obj, tri.polygon_index))
    tree = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
    down = Vector((0, 0, -1))

    def is_support(obj):
        return obj.get('asset_group') in SUPPORT or obj.get('source_node') == 'ground'

    def probe(x, y):
        """(surfaces right above the rock as {(object, polygon)}, their z, rock z), or None without rock.

        Coincident undersides (duplicated volumes share one bottom plane) are all returned: the ray
        reports only one of them.
        """
        position, previous, z = Vector((x, y, 4000.0)), set(), None
        for _ in range(64):
            hit, normal, index, _ = tree.ray_cast(position, down)
            if hit is None:
                return None
            owner = owners[index]
            if is_support(owner[0]):
                return (previous, z, hit.z) if previous else None
            # every flat face within 1 px of this hit (a coincident duplicate is never hit separately)
            previous = {owners[i] for _, n, i, _ in tree.find_nearest_range(hit, 1.0) if abs(n.z) > 0.95} | {owner}
            z = hit.z
            position = hit + down * 0.01
        raise RuntimeError(f'Probe at {x},{y} did not reach the rock')

    def floor_below(point):
        """z of whatever lies straight below a point (rock, ground or a lower castle part)."""
        hit, _, _, _ = tree.ray_cast(point + down * 0.01, down)
        if hit is None:
            raise RuntimeError(f'Nothing below {tuple(round(c) for c in point)}')
        return hit.z

    golden = math.pi * (3 - math.sqrt(5))
    sideways = []  # directions from horizontal down to 60 degrees below it
    for k in range(48):
        dz = -0.87 * (k + .5) / 48
        r = math.sqrt(1 - dz * dz)
        sideways.append(Vector((r * math.cos(golden * k), r * math.sin(golden * k), dz)))

    def exposed(point):
        """True when open air around the point reaches out of the castle (walls do not enclose it)."""
        return any(tree.ray_cast(point, direction, 3000)[0] is None for direction in sideways)

    (xlo, xhi), (ylo, yhi) = REGION
    prisms, considered, enclosed = [], 0, []
    for obj in meshes:
        if obj.get('asset_group') not in CASTLE:
            continue
        matrix, normal_matrix = obj.matrix_world, obj.matrix_world.to_3x3().inverted().transposed()
        for polygon in obj.data.polygons:
            normal = (normal_matrix @ polygon.normal).normalized()
            if abs(normal.z) < 0.95 or polygon.area < 1.0:
                continue
            corners = [matrix @ obj.data.vertices[i].co for i in polygon.vertices]
            outline = [(p.x, p.y) for p in corners]
            centre = sum(corners, Vector()) / len(corners)
            if not (xlo < centre.x < xhi and ylo < centre.y < yhi):
                continue
            considered += 1
            x0, x1 = min(p[0] for p in outline), max(p[0] for p in outline)
            y0, y1 = min(p[1] for p in outline), max(p[1] for p in outline)
            samples = [(centre.x, centre.y)] + [
                (x0 + (i + .5) * SAMPLE, y0 + (j + .5) * SAMPLE)
                for i in range(max(1, int((x1 - x0) / SAMPLE))) for j in range(max(1, int((y1 - y0) / SAMPLE)))]
            samples = [s for s in samples if inside(s, outline)]
            if not samples:
                continue
            counting = []
            for x, y in samples:
                found = probe(x, y)
                if found and (obj, polygon.index) in found[0] and found[1] - found[2] > MIN_GAP:
                    counting.append(Vector((x, y, found[1] - 0.5 * (found[1] - found[2]))))
            if not counting or len(counting) < MIN_SHARE * len(samples):
                continue
            # hollow buildings standing on the rock enclose the space under their floors: nothing to fill
            if not any(exposed(point) for point in counting[::max(1, len(counting) // 24)]):
                enclosed.append(f"{obj.get('source_node')}#{polygon.index}")
                continue
            area2 = sum(ax * by - bx * ay for (ax, ay), (bx, by) in zip(outline, outline[1:] + outline[:1]))
            prisms.append({'object': obj, 'polygon': polygon.index, 'corners': corners, 'normal': normal,
                           'ccw': area2 > 0, 'share': round(len(counting) / len(samples), 2)})
    if not prisms:
        raise ValueError('No exposed castle underside hangs over the rock in the window')
    edge_key = lambda a, b: frozenset(((round(a.x, 2), round(a.y, 2)), (round(b.x, 2), round(b.y, 2))))
    edge_use = {}
    for prism in prisms:
        c = prism['corners']
        for i in range(len(c)):
            key = edge_key(c[i], c[(i + 1) % len(c)])
            edge_use[key] = edge_use.get(key, 0) + 1

    block = bmesh.new()
    exterior = displaced = covered_cells = 0
    for prism in prisms:
        # the top sits TOP_EMBED inside the castle part above a downward underside; under an upward-facing
        # sheet (a walkable surface with nothing below it) it stays SHEET_GAP below so the two never z-fight
        lift = Vector((0, 0, TOP_EMBED if prism['normal'].z < 0 else -SHEET_GAP))
        corners = [p + lift for p in prism['corners']]
        bottoms = [floor_below(p) - BOTTOM_EMBED for p in prism['corners']]
        prism['bottom'] = round(min(bottoms), 1)
        top = [block.verts.new(p) for p in corners]
        base = [block.verts.new((p.x, p.y, z)) for p, z in zip(corners, bottoms)]
        block.faces.new(top)
        block.faces.new(list(reversed(base)))
        nv = max(1, round((max(p.z for p in corners) - min(bottoms)) / CELL))  # one row count per prism
        for i in range(len(corners)):
            j = (i + 1) % len(corners)
            a, b = corners[i], corners[j]
            if edge_use[edge_key(prism['corners'][i], prism['corners'][j])] > 1:
                continue  # shared with the neighbouring prism: hidden between them
            length = Vector((b.x - a.x, b.y - a.y)).length
            if length < 0.5:
                block.faces.new((top[j], top[i], base[i], base[j]))
                continue
            outward = Vector((b.y - a.y, -(b.x - a.x), 0)).normalized()
            if not prism['ccw']:
                outward = -outward
            exterior += 1
            nu = max(1, round(length / CELL))
            # column bottoms follow whatever lies below the outline
            column_bottom = [bottoms[i] if iu == 0 else bottoms[j] if iu == nu else floor_below(a.lerp(b, iu / nu)) - BOTTOM_EMBED
                             for iu in range(nu + 1)]
            flat = [[a.lerp(b, iu / nu).lerp(Vector((a.lerp(b, iu / nu).x, a.lerp(b, iu / nu).y, column_bottom[iu])), iv / nv)
                     for iv in range(nv + 1)] for iu in range(nu + 1)]
            # a cell already covered by an existing surface in its plane (a wall reaching down) is left out
            covered = [[tree.ray_cast((flat[iu][iv] + flat[iu + 1][iv + 1]) / 2 + outward * 3, -outward, 3.6)[0] is not None
                        for iv in range(nv)] for iu in range(nu)]
            grid = []
            for iu in range(nu + 1):
                column = []
                for iv in range(nv + 1):
                    if iu in (0, nu) and iv in (0, nv):
                        column.append((top[i] if iu == 0 else top[j]) if iv == 0 else (base[i] if iu == 0 else base[j]))
                        continue
                    point = flat[iu][iv].copy()
                    touching = [covered[cu][cv] for cu in (iu - 1, iu) for cv in (iv - 1, iv) if 0 <= cu < nu and 0 <= cv < nv]
                    weight = math.sin(math.pi * iu / nu) * math.sin(math.pi * iv / nv)
                    if weight > 1e-9 and not any(touching):
                        offset = max(-AMPLITUDE, min(AMPLITUDE, noise.noise(point * 0.06) * AMPLITUDE * 1.6)) * weight
                        point += outward * offset
                        displaced += 1
                    column.append(block.verts.new(point))
                grid.append(column)
            for iu in range(nu):
                for iv in range(nv):
                    if covered[iu][iv]:
                        covered_cells += 1
                        continue
                    block.faces.new((grid[iu + 1][iv], grid[iu][iv], grid[iu][iv + 1], grid[iu + 1][iv + 1]))
    # side cells along an edge share the prism's top/base verts only at the corners; fuse the seams
    bmesh.ops.remove_doubles(block, verts=block.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(block, faces=list(block.faces))
    block.transform(target.matrix_world.inverted())
    faces_before = len(target.data.polygons)
    merged = bmesh.new()
    merged.from_mesh(target.data)
    lookup = {vert: merged.verts.new(vert.co) for vert in block.verts}
    for face in block.faces:
        merged.faces.new([lookup[v] for v in face.verts]).material_index = 0
    block.free()
    merged.to_mesh(target.data)
    merged.free()
    target.data.update()
    co = [target.matrix_world @ v.co for v in target.data.vertices]
    report = {'undersides_considered': considered, 'prisms': len(prisms), 'enclosed_undersides': enclosed,
              'exterior_sides': exterior, 'side_cells_covered_by_walls': covered_cells, 'displaced_vertices': displaced, 'faces_before': faces_before, 'faces_after': len(target.data.polygons),
              'bounds_min': [round(min(p[i] for p in co), 2) for i in range(3)],
              'bounds_max': [round(max(p[i] for p in co), 2) for i in range(3)],
              'castle_assets': CASTLE, 'region': REGION, 'min_gap': MIN_GAP, 'cell': CELL, 'amplitude': AMPLITUDE,
              'undersides': [{'part': p['object'].get('source_node'), 'face': p['polygon'], 'share': p['share'],
                              'bottom': round(p['bottom'], 1), 'top': round(p['corners'][0].z, 1)} for p in prisms]}
    target['round8_rock_prisms'] = json.dumps({k: report[k] for k in ('prisms', 'exterior_sides', 'displaced_vertices')})
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
    (workspace / 'inspection').mkdir(exist_ok=True)
    (workspace / 'inspection' / 'round8-fill.json').write_text(json.dumps(report, indent=2) + '\n')
    print('ROUND8 ROCK', json.dumps({k: report[k] for k in ('undersides_considered', 'prisms', 'enclosed_undersides', 'exterior_sides',
                                                           'side_cells_covered_by_walls',
                                                           'faces_before', 'faces_after')}), flush=True)
    print('ROUND8 PRISMS', json.dumps([f"{u['part'][9:]}#{u['face']} {u['share']} {u['top']}->{u['bottom']}"
                                       for u in report['undersides']]), flush=True)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1])
