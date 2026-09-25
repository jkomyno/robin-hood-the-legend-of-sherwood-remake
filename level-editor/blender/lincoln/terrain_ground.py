"""Lincoln ground terrain geometry: the village stream channel (idempotent).

The native map ground is a flat z = 0 plane. The painted stream runs from the
north map edge (x 1050..1240) south, turns west past the village footbridge,
widens into the pond and leaves the map at the west edge (y 960..1080). This
recipe cuts that channel into the ground; everything else stays at z = 0.

Coordinates: native (x, y, z) projects to source pixel (x, y - z); Blender
world is X = x, Y = -y / sin35, Z = z / cos35. In native units the source
camera ray descends at exactly 45 degrees, so a 1:1 bank that faces away from
the camera is edge-on. The painted water is the flat channel bed (the water
surface) at native z = BED_Z, and its native footprint is therefore the painted
water region shifted up by the depth: the south edge of the painted water is
the (edge-on) top of the south bank, the north edge is the far waterline.

* ``WATER``: hand-traced painted water outline in covered.png pixels, both
  banks, including water glimpsed through the footbridge arches and the
  gravel bar of the northern bend. Tree canopies over the course are crossed
  along the continuation of the visible banks. Where the footbridge hides the
  water, the outline follows the bed corners under the bridge (painted pixel =
  native corner shifted down by the depth).
* Bed: world Z = -58 (native -47.51), 2 units above the approved footbridge
  pier/arch feet (world Z = -60) so the masonry is seated in the bed.
* Banks: 1:1 native slope from the bed footprint up to z = 0.
* Footbridge: between the approved abutments (bridge frame x 13..155, 1 unit
  inside the abutment masonry x 12..18 / 150..156) the bed spans the whole
  bridge width plus 6 units front and rear (frame y -7..87), with vertical
  channel walls at the abutments. The banks behind the abutments stay at z = 0
  against the abutment faces and under the deck ramps (frame x -35..13 /
  155..191, frame y -7..87), over any painted water there too, and fall off
  at ABUTMENT_BANK_SLOPE; the channel is open only between the abutments.
* Top map edge: the ground gains a tongue to native y = -60 over x 990..1300 so
  the channel is continuous in the top source rows; the channel section is
  open at that tongue edge and at the west map edge.
"""
import hashlib
import json
import math

import numpy as np

SIN = math.sin(math.radians(35))
COS = math.cos(math.radians(35))
WIDTH, HEIGHT = 2944.0, 2176.0
BED_WORLD_Z = -58.0
BED_Z = BED_WORLD_Z * COS  # native
BANK_SLOPE = 1.0  # native rise per native run
ABUTMENT_BANK_SLOPE = 4.0  # banks where the painted water meets the abutment ramps
GRID = 3.0  # native sample spacing inside the channel zone
TAG = 'lincoln_terrain_stream_channel_v1'

WATER = [
    (1050, 0), (1055, 50), (1100, 90), (1140, 130), (1170, 170), (1185, 225), (1190, 280), (1180, 350),
    (1160, 390), (1140, 410), (1100, 425), (1050, 432), (1000, 445), (975, 462), (950, 468), (900, 475),
    (850, 485), (800, 500), (775, 515), (765, 545), (750, 560), (720, 600), (686, 635), (635, 680),
    (600, 668), (560, 660), (480, 665), (440, 680), (400, 700), (375, 725), (355, 760), (325, 775), (285, 780),
    (275, 800), (250, 830), (200, 835), (150, 855), (100, 890), (60, 930), (0, 960),
    (0, 1080), (75, 1050), (140, 1010), (200, 965), (265, 945), (300, 925), (330, 895), (365, 870),
    (410, 855), (460, 830), (500, 800), (550, 785), (580, 760), (585, 700), (640, 700), (700, 712),
    (755, 724), (805, 679), (812, 630), (820, 585), (850, 570), (880, 560), (915, 550), (920, 500), (975, 497),
    (1010, 480), (1065, 475), (1140, 490), (1200, 475), (1260, 450), (1285, 400), (1300, 350),
    (1300, 300), (1320, 250), (1320, 200), (1310, 150), (1290, 100), (1260, 50), (1240, 0)]

# Village footbridge frame (village_assets.stone_footbridge): world origin and long axis.
BRIDGE_ORIGIN = (628.0, -1090.0)
BRIDGE_ALONG = (145.0, -93.0)
BRIDGE_BED_X = (13.0, 155.0)
BRIDGE_BAND_Y = (-7.0, 87.0)
DECK_X = (-35.0, 191.0)  # deck ramp ends at the bank datum (frame x -30.9 / 186.9)
WALL_GAP = 0.05  # half-width of the near-vertical abutment wall (frame x)
TONGUE = (990.0, 1300.0, -60.0)  # x0, x1, native y of the top-edge extension


def _unit(v):
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n)


def bridge_frame(native_xy):
    """Native (x, y) -> footbridge frame (fx along the bridge, fy towards the rear)."""
    p = np.asarray(native_xy, float)
    ex = _unit(BRIDGE_ALONG)
    ey = (-ex[1], ex[0])
    dx = p[..., 0] - BRIDGE_ORIGIN[0]
    dy = -p[..., 1] / SIN - BRIDGE_ORIGIN[1]
    return dx * ex[0] + dy * ex[1], dx * ey[0] + dy * ey[1]


def bridge_native(fx, fy):
    ex = _unit(BRIDGE_ALONG)
    ey = (-ex[1], ex[0])
    wx = BRIDGE_ORIGIN[0] + ex[0] * fx + ey[0] * fy
    wy = BRIDGE_ORIGIN[1] + ex[1] * fx + ey[1] * fy
    return wx, -wy * SIN


def water_footprint():
    """Native footprint of the flat bed: the painted water shifted by the bed depth."""
    return [(x, y + BED_Z) for x, y in WATER]


def _inside(points, polygon):
    x, y = points[:, 0], points[:, 1]
    result = np.zeros(len(points), bool)
    poly = np.asarray(polygon, float)
    for (ax, ay), (bx, by) in zip(poly, np.roll(poly, -1, 0)):
        crosses = (ay > y) != (by > y)
        with np.errstate(divide='ignore', invalid='ignore'):
            xi = (bx - ax) * (y - ay) / (by - ay) + ax
        result ^= crosses & (x < xi)
    return result


def _distance(points, polygon):
    best = np.full(len(points), np.inf)
    poly = np.asarray(polygon, float)
    for a, b in zip(poly, np.roll(poly, -1, 0)):
        d = b - a
        t = np.clip(((points - a) @ d) / max(d @ d, 1e-12), 0, 1)
        best = np.minimum(best, np.linalg.norm(points - (a + t[:, None] * d), axis=1))
    return np.where(_inside(points, polygon), 0.0, best)


def bed_regions():
    fx0, fx1 = BRIDGE_BED_X
    fy0, fy1 = BRIDGE_BAND_Y
    rect = [bridge_native(fx0, fy0), bridge_native(fx1, fy0), bridge_native(fx1, fy1), bridge_native(fx0, fy1)]
    return [water_footprint(), rect]


def height(points):
    """Native terrain height at native (x, y) points."""
    points = np.asarray(points, float)
    distance = np.min([_distance(points, region) for region in bed_regions()], axis=0)
    z = np.minimum(0.0, BED_Z + BANK_SLOPE * distance)
    # Solid banks behind the abutments (under the deck ramps) fall off at the bank slope.
    solid = np.min([_distance(points, block) for block in solid_blocks()], axis=0)
    # The banks against the abutment faces stay at z 0 (also over painted water that the
    # source ray sees past the abutments) and fall off at the steep ABUTMENT_BANK_SLOPE,
    # so the channel is open only between the abutments.
    z = np.maximum(z, -ABUTMENT_BANK_SLOPE * solid)
    fx, fy = bridge_frame(points)
    bed = ((fy >= BRIDGE_BAND_Y[0]) & (fy <= BRIDGE_BAND_Y[1]) &
           (fx >= BRIDGE_BED_X[0]) & (fx <= BRIDGE_BED_X[1]))
    return np.where(bed, BED_Z, z)


def solid_blocks():
    fy0, fy1 = BRIDGE_BAND_Y
    return [[bridge_native(a, fy0), bridge_native(b, fy0), bridge_native(b, fy1), bridge_native(a, fy1)]
            for a, b in ((DECK_X[0], BRIDGE_BED_X[0]), (BRIDGE_BED_X[1], DECK_X[1]))]


def sample_points():
    """Channel-zone grid plus the explicit abutment wall lines (native x, y, z) and wall edges."""
    reach = -BED_Z / BANK_SLOPE + 2 * GRID
    regions = bed_regions()
    allpts = np.concatenate([np.asarray(r, float) for r in regions])
    x0, y0 = allpts.min(0) - reach
    x1, y1 = allpts.max(0) + reach
    xs = np.arange(max(0.0, math.floor(x0 / GRID) * GRID), min(WIDTH, x1) + GRID, GRID)
    ys = np.arange(max(TONGUE[2], math.floor(y0 / GRID) * GRID), min(HEIGHT, y1) + GRID, GRID)
    gx, gy = np.meshgrid(xs, ys)
    grid = np.stack([gx.ravel(), gy.ravel()], 1)
    grid = grid[(grid[:, 0] > 0) & (grid[:, 0] < WIDTH) & (grid[:, 1] < HEIGHT)]
    in_tongue = (grid[:, 0] > TONGUE[0]) & (grid[:, 0] < TONGUE[1])
    grid = grid[(grid[:, 1] > 0) | (in_tongue & (grid[:, 1] > TONGUE[2]))]
    distance = np.min([_distance(grid, r) for r in regions], axis=0)
    grid = grid[distance < reach]
    fx, fy = bridge_frame(grid)
    near_wall = ((fy > BRIDGE_BAND_Y[0] - GRID) & (fy < BRIDGE_BAND_Y[1] + GRID) &
                 ((np.abs(fx - BRIDGE_BED_X[0]) < GRID) | (np.abs(fx - BRIDGE_BED_X[1]) < GRID)))
    grid = grid[~near_wall]
    points = [(float(x), float(y), float(z)) for (x, y), z in zip(grid, height(grid))]
    walls = []
    steps = int(round((BRIDGE_BAND_Y[1] - BRIDGE_BAND_Y[0]) / 2.0))
    for wall, outward in ((BRIDGE_BED_X[0], -1), (BRIDGE_BED_X[1], 1)):
        for side, z in ((outward, 0.0), (-outward, BED_Z)):
            line = []
            for i in range(steps + 1):
                fy = BRIDGE_BAND_Y[0] + (BRIDGE_BAND_Y[1] - BRIDGE_BAND_Y[0]) * i / steps
                nx, ny = bridge_native(wall + side * WALL_GAP, fy)
                line.append(len(points))
                points.append((nx, ny, z))
            walls.append(line)
    return points, walls


def boundary():
    x0, x1, y = TONGUE
    return [(0.0, 0.0), (x0, 0.0), (x0, y), (x1, y), (x1, 0.0), (WIDTH, 0.0), (WIDTH, HEIGHT), (0.0, HEIGHT)]


def world(p):
    return (p[0], -p[1] / SIN, p[2] / COS)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def definition():
    """Every constant that determines the geometry, for evidence records."""
    return {'water_trace_pixels': WATER, 'bed_world_z': BED_WORLD_Z, 'bed_native_z': BED_Z,
            'bank_slope_native': BANK_SLOPE, 'abutment_bank_slope_native': ABUTMENT_BANK_SLOPE, 'grid_native': GRID,
            'bridge': {'origin_world': BRIDGE_ORIGIN, 'along_world': BRIDGE_ALONG,
                       'bed_frame_x': BRIDGE_BED_X, 'band_frame_y': BRIDGE_BAND_Y, 'wall_gap': WALL_GAP,
                       'deck_ramp_frame_x': DECK_X},
            'tongue': TONGUE}


def build(ground):
    """Replace the flat ground mesh by the channel terrain (Blender only)."""
    import bpy
    import bmesh
    from mathutils import Vector
    from mathutils.geometry import delaunay_2d_cdt
    if ground.get(TAG):
        return json.loads(ground[TAG])
    world_before = [ground.matrix_world @ v.co for v in ground.data.vertices]
    if (len(ground.data.polygons) != 2 or len(world_before) != 4 or
            any(abs(p.z) > 1e-3 for p in world_before)):
        raise ValueError('Terrain recipe requires the frozen flat four-corner ground plane')
    corners = sorted((round(p.x, 3), round(-p.y * SIN, 3)) for p in world_before)
    if corners != sorted([(0.0, 0.0), (WIDTH, 0.0), (0.0, HEIGHT), (WIDTH, HEIGHT)]):
        raise ValueError(f'Unexpected ground extent: {corners}')
    before = {'vertices': [list(v.co) for v in ground.data.vertices],
              'faces': [list(p.vertices) for p in ground.data.polygons]}
    outline = boundary()
    points, walls = sample_points()
    base = len(outline)
    coords = [Vector((x, y)) for x, y in outline] + [Vector((p[0], p[1])) for p in points]
    heights = [0.0] * base + [p[2] for p in points]
    edges = []
    for line in walls:
        edges += [(base + a, base + b) for a, b in zip(line, line[1:])]
    # Output type 1 keeps only triangles inside the (non-convex) map outline face.
    out_coords, _, faces, original, _, _ = delaunay_2d_cdt(coords, edges, [list(range(base))], 1, 1e-4)
    outline_array = np.asarray(outline)
    centres = np.array([[sum(out_coords[i][k] for i in f) / len(f) for k in (0, 1)] for f in faces])
    if not _inside(centres, outline_array).all():
        raise ValueError('Triangulation produced faces outside the map outline')
    vertices = []
    for point, ids in zip(out_coords, original):
        if len(ids) != 1:
            raise ValueError(f'Triangulation introduced an unsupported point at {tuple(point)}')
        vertices.append(world((point.x, point.y, heights[ids[0]])))
    inverse = ground.matrix_world.inverted()
    mesh = bpy.data.meshes.new('Ground / village stream channel')
    # Native y points down the map, which mirrors world Y: reverse winding for upward normals.
    mesh.from_pydata([inverse @ Vector(v) for v in vertices], [], [tuple(reversed(f)) for f in faces])
    mesh.update()
    normals_down = sum((ground.matrix_world.to_3x3() @ p.normal).z < 0 for p in mesh.polygons)
    if normals_down:
        raise ValueError(f'{normals_down} terrain faces face downward')
    uv = mesh.uv_layers.new(name=ground.data.uv_layers.active.name)
    for loop in mesh.loops:
        x, y, z = vertices[loop.vertex_index]
        py = -y * SIN - z * COS
        uv.data[loop.index].uv = (x / WIDTH, 1 - py / HEIGHT)
    for material in ground.data.materials:
        mesh.materials.append(material)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    degenerate = sum(f.calc_area() < 1e-6 for f in bm.faces)
    nonmanifold = sum(not e.is_manifold and not e.is_boundary for e in bm.edges)
    bm.free()
    if degenerate or nonmanifold:
        raise ValueError(f'Invalid terrain surface: degenerate {degenerate}, nonmanifold {nonmanifold}')
    old = ground.data
    ground.data = mesh
    if old.users == 0:
        bpy.data.meshes.remove(old)
    zs = np.array([v[2] for v in vertices])
    report = {'status': 'candidate-stream-channel', 'source_node': 'ground', 'recipe_tag': TAG,
              'definition': definition(), 'definition_sha256': digest(definition()),
              'before_geometry_sha256': digest(before),
              'after_geometry_sha256': digest({'vertices': [list(v.co) for v in mesh.vertices],
                                               'faces': [list(p.vertices) for p in mesh.polygons]}),
              'vertices': len(mesh.vertices), 'faces': len(mesh.polygons),
              'lowered_vertices': int((zs < -1e-6).sum()), 'min_world_z': float(zs.min()),
              'degenerate_faces': degenerate, 'nonmanifold_edges': nonmanifold,
              'surface': 'open heightfield sheet (single-sided terrain surface, like the original plane)'}
    ground[TAG] = json.dumps(report, sort_keys=True)
    return json.loads(ground[TAG])


def footbridge_clearance(ground, bridge_objects, samples=10):
    """Arch/pier/abutment faces inside the channel must be above the bed, the pier foot seated in it."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    tree = BVHTree.FromPolygons([ground.matrix_world @ v.co for v in ground.data.vertices],
                                [tuple(p.vertices) for p in ground.data.polygons])
    buried, count, lowest_gap, seated = [], 0, math.inf, 0
    for obj in bridge_objects:
        mesh = obj.data
        mesh.calc_loop_triangles()
        for tri in mesh.loop_triangles:
            a, b, c = [obj.matrix_world @ mesh.vertices[i].co for i in tri.vertices]
            for i in range(samples + 1):
                for j in range(samples + 1 - i):
                    p = a + (b - a) * (i / samples) + (c - a) * (j / samples)
                    fx, fy = bridge_frame(np.array([[p.x, -p.y * SIN]]))
                    if not (BRIDGE_BED_X[0] + 0.5 < fx[0] < BRIDGE_BED_X[1] - 0.5 and -1.5 < fy[0] < 81.5):
                        continue
                    hit = tree.ray_cast(Vector((p.x, p.y, 1000)), Vector((0, 0, -1)), 5000)[0]
                    if hit is None:
                        raise ValueError('Ground missing under the footbridge')
                    count += 1
                    gap = p.z - hit.z
                    if p.z < BED_WORLD_Z - 1e-3:
                        seated += 1
                        continue
                    lowest_gap = min(lowest_gap, gap)
                    if gap < -1e-3:
                        buried.append([list(p), gap])
    if buried:
        raise ValueError(f'Footbridge masonry buried by the channel bed: {buried[:6]} ({len(buried)})')
    return {'status': 'PASS', 'samples_in_channel': count, 'seated_below_bed': seated,
            'lowest_clearance_above_bed': lowest_gap,
            'method': 'Barycentric samples on every 045/046 triangle between the abutment walls; '
                      'vertical ray to the saved ground. Only the pier/arch feet below the bed are seated.'}
