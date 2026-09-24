"""Inner western gatehouse with stair turret (lincoln-inner-west-gate, nodes 289-305).

All heights are native z; a native point (x, y, z) projects to source pixel
(x, y - z). Measurements come from covered.png and the reviewed native gate
silhouette (mask 273) / ramp-wall silhouette (mask 279); the numbered corner
evidence is in the workspace ``inspection/corner-trace.json``.

Structure (covered state; no patch touches the gate):
- Ground: inner-bailey plateau, native z 220. Mask-273 foot line: west block
  front 1462-1471 px (z 217-219), east block front 1497-1512 px (z 217-219),
  east face 1512 -> 1465 px (z 217-220), passage jambs 1484-1499 px (z 220).
- West block 294 and east block 289 rise from z 220 to roof z 322; passage walls
  297/296 to the vault (z 310); side walls 295/293 keep their native sloped tops.
- Passage roof / walkway 291: slab z 309-333 over the passage, plus the front
  arch wall (jambs + spandrel) on the gate front plane with the arch opening
  measured from the mask-273 lower boundary (x 1034-1066 px, crown z ~282).
- Corbelled parapets overhang the blocks (native parapet rings are wider than
  the block footprints; mask foot of the west overhang ~z 320) and start at
  z 318; bay parapet 298 starts at its corbel, z 309; the back parapet 292
  over the rear passage exit starts at its native z 269.
- Crenellation (numbered corners): passage-level runs (bay 298, back 292) cap
  z 360 / notch floor z 351; east block runs (290) cap 349 / floor 339; west
  block runs (299) cap 353 / floor 344. Notches are narrow (~5 px) except on
  the round bay (~12 px). Notch shoulders are pixel x positions (= native x).
- Ramp retaining wall 300 (mask 279): from the plateau (mask foot 1455-1460 px,
  z ~225) to stepped merlons rising with the ramp (caps z 312 -> 347).
- Ramp surface 301: native sloped top, closed just below the plateau.
- Stair turret: shaft 302 r 30 (world) centred (1058, 1635), buried base z 300
  under the walkway/rock, eave disk 305 r 34 z 370-376, slate cone split into
  east (303) / west (304) halves from z 375.5 to apex z 426 (mask flank apex
  ~1209 px), plus the finial pole to z 463 (mask 1171 px) in 303.
"""
import math

from west_complex_geom import (PLATEAU_Z, Shape, extrude_profile, lathe, native_obstacles,
                               points, prism)

GROUND = PLATEAU_Z
ROOF = 322.0
WALK = 333.0
VAULT = 309.0
PARAPET_BASE = 318.0

# Crenel runs: outer/inner polylines (native x, y); per segment: notch intervals in pixel x,
# cap and floor heights (scalars or callables of pixel x).
EAST_CAP, EAST_FLOOR = 349.0, 339.0
WEST_CAP, WEST_FLOOR = 353.0, 344.0
PASSAGE_CAP, PASSAGE_FLOOR = 360.0, 351.0
PILLAR_CAP = 366.0

RUNS = {
    290: dict(  # east block U parapet: front (R4), east face (R3), back (R2)
        outer=[(1082, 1715), (1139, 1735), (1193, 1684), (1141, 1665)],
        inner=[(1085, 1710), (1134, 1727), (1181, 1685), (1139, 1670)],
        base=PARAPET_BASE, cap=EAST_CAP, floor=EAST_FLOOR,
        notches=[[(1101, 1106), (1120, 1125)],
                 [(1149, 1153), (1163, 1168), (1177, 1182)],
                 [(1151, 1156), (1172, 1177)]]),
    299: dict(  # west block U parapet: front (R6), north-west (R7), back (R8, inside turret)
        outer=[(1029, 1698), (978, 1680), (1035, 1627), (1086, 1646)],
        inner=[(1030, 1693), (986, 1678), (1037, 1632), (1082, 1649)],
        base=PARAPET_BASE, cap=WEST_CAP, floor=WEST_FLOOR,
        notches=[[(991, 996), (1011, 1016)],
                 [(988, 994), (1001, 1007), (1014, 1020)],
                 []]),
    292: dict(  # back parapet over the rear passage exit (R1)
        outer=[(1086, 1647), (1141, 1665)],
        inner=[(1083, 1651), (1138, 1669)],
        base=269.0, cap=PASSAGE_CAP, floor=PASSAGE_FLOOR,
        notches=[[(1098, 1103), (1119, 1124)]]),
}

BAY_OUTER = [(1016, 1700), (1019, 1712), (1026, 1721), (1036, 1726), (1048, 1728),
             (1062, 1728), (1075, 1726), (1084, 1721), (1092, 1718), (1101, 1718)]
BAY_INNER = [(1022, 1700), (1024, 1710), (1030, 1716), (1039, 1720), (1049, 1722),
             (1062, 1722), (1074, 1720), (1082, 1715), (1090, 1713), (1101, 1713)]
BAY_NOTCHES = [(1017, 1030), (1042, 1055), (1068, 1079)]

# Ramp wall 300: stepped merlon caps from the mask-279 top silhouette (inner edge).
# Merlons [1178,1188] z312, [1191,1202] z322, [1205,1216] z335, [1219,1221+] z347; notches 3 px.

TURRET_CENTER = (1058.0, 1635.0)
ARCH = dict(front=((1021, 1704), (1076, 1722)), back=((1024, 1700), (1079, 1718)),
            left=1034.0, right=1066.0, spring=262.0, crown=282.0)


def _poly(obstacles, node):
    return [(x, y) for x, y, _, _ in points(obstacles, node)]


def _value(v, x):
    return v(x) if callable(v) else v


def ribbon(outer, inner, base, cap, floor, notches):
    """One closed crenellated wall along a polyline.

    Cells between consecutive cut stations are hexahedra; faces shared by
    neighbouring cells cancel, so the result is a single manifold shell with
    explicit vertical notch shoulders. ``notches`` is one list of pixel-x
    intervals per segment; ``base``/``cap``/``floor`` may be callables of x.
    """
    verts, index, faces = [], {}, []

    def vid(p):
        key = tuple(round(c, 5) for c in p)
        if key not in index:
            index[key] = len(verts)
            verts.append(key)
        return index[key]

    def lerp(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    def cell(o0, o1, i1, i0, z0a, z0b, z1a, z1b):
        # z0a/z1a at station 0, z0b/z1b at station 1 (bottom, top)
        b = [vid((*o0, z0a)), vid((*o1, z0b)), vid((*i1, z0b)), vid((*i0, z0a))]
        t = [vid((*o0, z1a)), vid((*o1, z1b)), vid((*i1, z1b)), vid((*i0, z1a))]
        faces.extend([[b[3], b[2], b[1], b[0]], [t[0], t[1], t[2], t[3]],
                      [b[0], b[1], t[1], t[0]], [b[1], b[2], t[2], t[1]],
                      [b[2], b[3], t[3], t[2]], [b[3], b[0], t[0], t[3]]])

    for k in range(len(outer) - 1):
        a, c = outer[k], outer[k + 1]
        ai, ci = inner[k], inner[k + 1]
        cuts = {0.0, 1.0}
        span = c[0] - a[0]
        for lo, hi in notches[k]:
            for x in (lo, hi):
                if abs(span) > 1e-9:
                    t = (x - a[0]) / span
                    if 1e-6 < t < 1 - 1e-6:
                        cuts.add(t)
        cuts = sorted(cuts)
        for t0, t1 in zip(cuts, cuts[1:]):
            o0, o1, i0, i1 = lerp(a, c, t0), lerp(a, c, t1), lerp(ai, ci, t0), lerp(ai, ci, t1)
            xm = (o0[0] + o1[0]) / 2
            f0, f1 = _value(floor, o0[0]), _value(floor, o1[0])
            z0, z1 = _value(base, o0[0]), _value(base, o1[0])
            cell(o0, o1, i1, i0, z0, z1, f0, f1)
            if not any(min(lo, hi) < xm < max(lo, hi) for lo, hi in notches[k]):
                cz = _value(cap, xm)
                cell(o0, o1, i1, i0, f0, f1, cz, cz)
    # Cancel faces shared by adjacent cells (same vertex set, opposite winding).
    unique = {}
    for f in faces:
        key = tuple(sorted(f))
        if key in unique:
            del unique[key]
        else:
            unique[key] = f
    return Shape.of(verts, list(unique.values()))


def arch_wall():
    """Front wall of the passage: two jambs and the spandrel with the measured arch."""
    (x0, y0), (x1, y1) = ARCH['front']
    tl = (ARCH['left'] - x0) / (x1 - x0)
    tr = (ARCH['right'] - x0) / (x1 - x0)
    arch = []
    for i in range(13):
        a = math.pi * i / 12
        t = (tl + tr) / 2 - (tr - tl) / 2 * math.cos(a)
        arch.append((t, ARCH['spring'] + (ARCH['crown'] - ARCH['spring']) * math.sin(a)))
    profile = ([(0.0, GROUND), (tl, GROUND), (tl, ARCH['spring'])] + arch[1:-1]
               + [(tr, ARCH['spring']), (tr, GROUND), (1.0, GROUND), (1.0, VAULT + 0.5), (0.0, VAULT + 0.5)])
    return extrude_profile(ARCH['front'], ARCH['back'], profile)


def ramp_wall(obstacles):
    """Straight ramp retaining wall: one closed elevation profile extruded through its thickness.

    Parameter t runs along the far (inner) edge, whose top is the mask-279
    silhouette: x = 1178 + 43 t. Merlon caps step up with the ramp; each notch
    floor sits ~5 below the merlon on its left (silhouette dips at 1189, 1203, 1217 px).
    """
    pts = _poly(obstacles, 300)  # (1221,1669) (1223,1672) (1181,1687) (1178,1684)
    inner = (pts[3], pts[0])
    outer = (pts[2], pts[1])
    x0, x1 = inner[0][0], inner[1][0]
    t = lambda x: (x - x0) / (x1 - x0)
    upper = [(1221, 347.0), (1219, 347.0), (1219, 330.0), (1216, 330.0), (1216, 335.0),
             (1205, 335.0), (1205, 317.0), (1202, 317.0), (1202, 322.0), (1191, 322.0),
             (1191, 307.0), (1188, 307.0), (1188, 312.0), (x0, 312.0)]
    profile = [(0.0, GROUND), (1.0, GROUND)] + [(t(x), z) for x, z in upper]
    return extrude_profile(inner, outer, profile)


def turret():
    cx, cy = TURRET_CENTER
    shaft = lathe((cx, cy), [(0, 300.0), (30.0, 300.0), (30.0, 371.0), (0, 371.0)], segments=32)
    eave = lathe((cx, cy), [(0, 370.0), (34.0, 370.0), (34.0, 376.0), (0, 376.0)], segments=32)
    cone = [(0, 375.5), (34.0, 375.5), (0, 426.0)]
    east = lathe((cx, cy), cone, segments=16, start=-math.pi / 2, end=math.pi / 2)
    west = lathe((cx, cy), cone, segments=16, start=math.pi / 2, end=3 * math.pi / 2)
    finial = lathe((cx, cy), [(0, 423.0), (1.3, 423.0), (1.3, 458.0), (2.2, 459.0), (2.2, 461.0), (0, 463.0)], segments=6)
    return {302: shaft, 305: eave, 303: Shape().add(east).add(finial), 304: west}


def build(asset):
    if asset != 'lincoln-inner-west-gate':
        raise KeyError(asset)
    ob = native_obstacles()
    shapes = {}
    # Mask 273 lower boundary puts the west block's front-left corner at x ~991
    # (x 988-990 only reach 1364-1393 px: the corbelled parapet overhang).
    west = [(991.0, 1680.0) if (x, y) == _poly(ob, 294)[3] else (x, y) for x, y in _poly(ob, 294)]
    shapes[294] = prism(west, GROUND, ROOF)
    shapes[289] = prism(_poly(ob, 289), GROUND, ROOF)
    for node in (293, 295):
        pts = points(ob, node)
        shapes[node] = prism([(x, y) for x, y, _, _ in pts], GROUND, [zt for *_, zt in pts])
    shapes[296] = prism(_poly(ob, 296), GROUND, 310.0)
    shapes[297] = prism(_poly(ob, 297), GROUND, 310.0)
    shapes[291] = Shape().add(prism(_poly(ob, 291), VAULT, WALK)).add(arch_wall())
    for node, run in RUNS.items():
        shapes[node] = ribbon(run['outer'], run['inner'], run['base'], run['cap'], run['floor'], run['notches'])
    bay_cap = lambda x: PILLAR_CAP if x > 1079 else PASSAGE_CAP
    shapes[298] = ribbon(BAY_OUTER, BAY_INNER, VAULT, bay_cap, PASSAGE_FLOOR, [BAY_NOTCHES] * (len(BAY_OUTER) - 1))
    shapes[300] = ramp_wall(ob)
    pts = points(ob, 301)
    shapes[301] = prism([(x, y) for x, y, _, _ in pts], GROUND - 6.0, [zt for *_, zt in pts])
    shapes.update(turret())
    info = {
        'ground_native_z': {'default': GROUND, 'turret_302_buried_base': 300.0, 'ramp_surface_301_closing_base': GROUND - 6.0,
                            'bay_298_corbel': VAULT, 'back_parapet_292': 269.0},
        'changes': [
            'Removed every z 0 datum pillar: the gatehouse now stands on the inner-bailey plateau (native z 220), confirmed by the mask-273 foot line along the west block, passage jambs, east block front and east face.',
            'Blocks 294/289 rebuilt as closed prisms z 220-322; passage walls 297/296 to the vault (z 310); side walls 293/295 keep native sloped tops.',
            'Passage roof 291 rebuilt as the walkway slab z 309-333 plus the front arch wall with the arch opening measured from the mask-273 lower boundary (x 1034-1066 px, springing z 262, crown z 282).',
            'Parapets 290 (east block U), 299 (west block U), 292 (rear passage parapet) and 298 (round bay) rebuilt as single closed crenellated walls with explicit notch shoulders from numbered source corners; corbelled overhangs follow the native parapet rings.',
            'Ramp retaining wall 300 rebuilt from the plateau to stepped merlons (caps z 312-347) traced from the mask-279 silhouette; ramp surface 301 closed below the plateau with its native sloped top.',
            'Stair turret: round shaft 302 (world r 30), eave disk 305 (r 34), true slate cone split between east (303) and west (304) owners, apex z 426, finial pole to z 463.'],
        'limitations': [
            'Merlon cap/floor heights are per-run constants fitted to 1-3 px manual picks; individual merlons can deviate by a few pixels in the artwork.',
            'Back runs of the west block (inside the turret) and hidden faces are inferred without notches.',
            'Turret shaft base (z 300) is buried under the walkway and the rock spur and is inferred.',
            'Passage interior walls and vault are simplified; the passage interior seen through the arch is outside mask 273 and stays neutral.',
            'Node 291 combines the walkway slab and the arch front wall as two closed shells that interpenetrate at the vault line; 303 combines the east cone half and the finial pole.'],
    }
    return shapes, info
