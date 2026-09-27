"""Round-8 recipe: one continuous rock mass under the great hall and its approach ramp.

    /usr/bin/blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/refine_keep_rock_mass.py -- <workspace>

The artwork paints one continuous rock face from the keep plateau straight up to the base of the
castle walls. The approved scene instead had open pockets: the great hall's front walls stop at
z 439.5 over nothing, the hall floor (512.7) and the forward hall part 268 overhang the raised
ground 465 (whose face is set back ~185 px), and the approach ramp floats above the plateau.

The recipe starts from the prepared workspace model (`baseline.blend`) and fills every pocket:

1. Every downward-facing face of a castle part standing on this rock (great hall, its slate spire,
   approach ramp, south terrace, keep annex and its turrets) is cut into 12 px cells clipped to the
   face outline; each cell is probed straight down and, where it hangs more than 3 px above
   whatever is below (plateau, ground, rock or another castle part such as the ramp), becomes a
   closed rock column from the face down to that support. Cell sides on the face outline are flush
   with the wall above: no recess or step between rock and walls.
2. Outline sides facing open air are split into ~12 px rows and displaced along their outward
   normal by rock-scale noise of at most ±8 px, weighted to zero at the wall base, the support and
   the ends of each outline edge, so the rock meets the walls exactly and the outline the source
   camera sees is unchanged.

The columns are added as closed shells of 465 (an exact boolean union with the sculpted,
non-manifold rock returns an empty mesh). Only 465 is edited. Writes inspection/round8-fill.json.
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
REGION = ((1000.0, 1900.0), (-3000.0, -2050.0))  # x, y window around the hall/ramp front
MIN_GAP, CELL, AMPLITUDE = 3.0, 12.0, 8.0


def main(workspace):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'refinement'))
    from render_slots import acquire
    acquire()
    import bpy
    import bmesh
    from mathutils import Vector, noise
    from mathutils.bvhtree import BVHTree
    workspace = Path(workspace).resolve()
    shutil.copyfile(workspace / 'baseline.blend', workspace / 'model.blend')
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'))
    working = bpy.data.collections['lincoln Working']
    meshes = [o for o in working.all_objects if o.type == 'MESH' and not o.hide_render]
    targets = [o for o in meshes if o.get('source_node') == 'building-465']
    if len(targets) != 1 or targets[0].get('asset_group') != ROCK:
        raise ValueError('Expected one visible 465 mesh of the merged rock asset')
    target = targets[0]
    # Whole-scene BVH for downward probes; remember each triangle's owner.
    vertices, triangles, owners = [], [], []
    for obj in meshes:
        mesh = obj.data
        mesh.calc_loop_triangles()
        offset = len(vertices)
        vertices.extend(obj.matrix_world @ v.co for v in mesh.vertices)
        for tri in mesh.loop_triangles:
            triangles.append(tuple(offset + i for i in tri.vertices))
            owners.append(obj)
    tree = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
    (xlo, xhi), (ylo, yhi) = REGION
    down = Vector((0, 0, -1))

    def support(x, y, z):
        hit, _, index, _ = tree.ray_cast(Vector((x, y, z - 0.05)), down)
        return (hit.z, owners[index]) if hit is not None else (None, None)

    def clip(polygon, x0, y0, x1, y1):
        """Sutherland-Hodgman of a 2D polygon against an axis-aligned cell."""
        def cut(points, inside, intersect):
            out = []
            for i, p in enumerate(points):
                q = points[i - 1]
                if inside(p):
                    if not inside(q):
                        out.append(intersect(q, p))
                    out.append(p)
                elif inside(q):
                    out.append(intersect(q, p))
            return out
        lerp_x = lambda xv: (lambda a, b: (xv, a[1] + (b[1] - a[1]) * (xv - a[0]) / (b[0] - a[0])))
        lerp_y = lambda yv: (lambda a, b: (a[0] + (b[0] - a[0]) * (yv - a[1]) / (b[1] - a[1]), yv))
        points = polygon
        for inside, intersect in ((lambda p: p[0] >= x0, lerp_x(x0)), (lambda p: p[0] <= x1, lerp_x(x1)),
                                  (lambda p: p[1] >= y0, lerp_y(y0)), (lambda p: p[1] <= y1, lerp_y(y1))):
            if not points:
                break
            points = cut(points, inside, intersect)
        return points

    columns, probes = [], []
    for obj in meshes:
        if obj.get('asset_group') not in CASTLE or obj.get('state_variant_of'):
            continue
        matrix, normal_matrix = obj.matrix_world, obj.matrix_world.to_3x3().inverted().transposed()
        for polygon in obj.data.polygons:
            normal = (normal_matrix @ polygon.normal).normalized()
            if normal.z > -0.7 or polygon.area < 1.0:
                continue
            corners = [matrix @ obj.data.vertices[i].co for i in polygon.vertices]
            centre = sum(corners, Vector()) / len(corners)
            if not (xlo < centre.x < xhi and ylo < centre.y < yhi):
                continue
            plane_d = normal.dot(corners[0])
            z_at = lambda x, y: (plane_d - normal.x * x - normal.y * y) / normal.z
            outline = [(p.x, p.y) for p in corners]
            edges = [(outline[i], outline[(i + 1) % len(outline)]) for i in range(len(outline))]
            gx0, gy0 = math.floor(min(p[0] for p in outline) / CELL) * CELL, math.floor(min(p[1] for p in outline) / CELL) * CELL
            gx1, gy1 = max(p[0] for p in outline), max(p[1] for p in outline)
            made = 0
            x = gx0
            while x < gx1:
                y = gy0
                while y < gy1:
                    piece = clip(outline, x, y, x + CELL, y + CELL)
                    if len(piece) >= 3:
                        cx = sum(p[0] for p in piece) / len(piece); cy = sum(p[1] for p in piece) / len(piece)
                        top_z = z_at(cx, cy)
                        bottom, owner = support(cx, cy, top_z)
                        if bottom is not None and top_z - bottom > MIN_GAP and not owner.get('state_variant_of'):
                            columns.append(([Vector((px, py, z_at(px, py))) for px, py in piece], bottom, edges))
                            made += 1
                    y += CELL
                x += CELL
            if made:
                probes.append({'part': obj.get('source_node'), 'asset': obj.get('asset_group'), 'face': polygon.index,
                               'cells': made})
    if not columns:
        raise ValueError('No overhanging castle faces found')
    # Cell sides on the castle face outline face open air (unless another face's outline shares them).
    outline_key = lambda a, b: frozenset(((round(a[0], 1), round(a[1], 1)), (round(b[0], 1), round(b[1], 1))))
    edge_use = {}
    for _, _, edges in {id(c[2]): c for c in columns}.values():
        for a, b in edges:
            edge_use[outline_key(a, b)] = edge_use.get(outline_key(a, b), 0) + 1

    def on_edge(p, edge):
        (ax, ay), (bx, by) = edge
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        if length2 < 1e-9:
            return None
        u = ((p.x - ax) * dx + (p.y - ay) * dy) / length2
        distance = abs((p.x - ax) * dy - (p.y - ay) * dx) / math.sqrt(length2)
        return u if distance < 1e-4 and -1e-6 <= u <= 1 + 1e-6 else None

    def bump(point, normal, weight):
        offset = noise.noise(point * 0.06) * AMPLITUDE * weight
        return point + normal * max(-AMPLITUDE, min(AMPLITUDE, offset))

    block = bmesh.new()
    exterior = displaced = 0
    for corners, bottom, edges in columns:
        top = [block.verts.new(p) for p in corners]
        base = [block.verts.new((p.x, p.y, bottom)) for p in corners]
        block.faces.new(top)
        block.faces.new(list(reversed(base)))
        centre = sum(corners, Vector()) / len(corners)
        for i in range(len(corners)):
            j = (i + 1) % len(corners)
            a, b = corners[i], corners[j]
            shared = None
            for edge in edges:
                ua, ub = on_edge(a, edge), on_edge(b, edge)
                if ua is not None and ub is not None:
                    shared = (edge, ua, ub)
                    break
            if shared is None or edge_use[outline_key(*shared[0])] > 1 or (b - a).length < 0.5:
                block.faces.new((top[j], top[i], base[i], base[j]))
                continue
            (ex, ey), (fx, fy) = shared[0]
            outward = Vector((fy - ey, -(fx - ex), 0)).normalized()
            if outward.dot(Vector((a.x - centre.x, a.y - centre.y, 0))) < 0:
                outward = -outward
            exterior += 1
            height = max(a.z, b.z) - bottom
            nv = max(1, round(height / CELL))
            left, right = [top[i]], [top[j]]
            for iv in range(1, nv):
                v = iv / nv
                for point, u, column in ((a, shared[1], left), (b, shared[2], right)):
                    p = Vector((point.x, point.y, point.z + (bottom - point.z) * v))
                    # Zero at the ends of each outline edge, so corners and wall bases stay fixed.
                    column.append(block.verts.new(bump(p, outward, math.sin(math.pi * min(1, max(0, u))) * math.sin(math.pi * v))))
                    displaced += 1
            left.append(base[i]); right.append(base[j])
            for iv in range(nv):
                block.faces.new((right[iv], left[iv], left[iv + 1], right[iv + 1]))
    bmesh.ops.recalc_face_normals(block, faces=list(block.faces))
    block.transform(target.matrix_world.inverted())
    faces_before = len(target.data.polygons)
    merged = bmesh.new()
    merged.from_mesh(target.data)
    lookup = {}
    for vert in block.verts:
        lookup[vert] = merged.verts.new(vert.co)
    for face in block.faces:
        merged.faces.new([lookup[v] for v in face.verts]).material_index = 0
    block.free()
    merged.to_mesh(target.data)
    merged.free()
    target.data.update()
    co = [target.matrix_world @ v.co for v in target.data.vertices]
    report = {'columns': len(columns), 'exterior_sides': exterior, 'displaced_vertices': displaced,
              'faces_before': faces_before, 'faces_after': len(target.data.polygons),
              'bounds_min': [round(min(p[i] for p in co), 2) for i in range(3)],
              'bounds_max': [round(max(p[i] for p in co), 2) for i in range(3)],
              'castle_assets': CASTLE, 'region': REGION, 'min_gap': MIN_GAP, 'cell': CELL,
              'amplitude': AMPLITUDE, 'overhangs': probes}
    target['round8_rock_columns'] = json.dumps({k: report[k] for k in ('columns', 'exterior_sides', 'displaced_vertices')})
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
    (workspace / 'inspection').mkdir(exist_ok=True)
    (workspace / 'inspection' / 'round8-fill.json').write_text(json.dumps(report, indent=2) + '\n')
    print('ROUND8 ROCK', json.dumps({k: report[k] for k in ('columns', 'exterior_sides', 'displaced_vertices',
                                                           'faces_before', 'faces_after')}), flush=True)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1])
