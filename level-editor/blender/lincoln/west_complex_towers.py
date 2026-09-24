"""Western round tower, tower hall and slate cone tower (lane west_complex).

All three assets share one hall roof system (hall facets 392-395/407 in the
hall asset, south slope 391 in the slate-tower asset) and one set of measured
towers, so their geometry is defined together here. Each asset build returns
only its catalog-owned nodes.

Artwork measurements (covered.png; native point projects to pixel (x, y - z)):

Round tower (387, 398-403), centre (463, 1533):
- Shaft left edge is vertical at pixel x 365-367 from y 1100 to 1320: world
  radius 96. The shaft stands on the bastion roof / west plateau at z 220.
- Upper window band 398 (light masonry with square openings) has its left edge
  at pixel x ~354-355: radius 106, front face visible from pixel y ~1110 to
  ~1152, so z 440-482 at the front (y 1594).
- Red scale roof: silhouette x 347.5-579 (radius 116, centre x 463). Its top
  outline follows the back half of the widest ring (x 370 -> y 1007.5,
  x 397.5 -> 995, x 447.5 -> 987.5), and its lowest front eave is pixel y
  ~1115; the back rim/top outline is at pixel y ~986: cy - z_rim = 1050.7,
  so the widest ring is z 480-482.5 at radius 116 (first pass at z 487 overshot
  the painted back outline by ~5 px in the coverage audit). Crown z 539 with a
  low convex profile whose slope stays below the camera slope, so the back rim
  is the top silhouette as in the artwork. Metal cap to pixel
  y ~984 and finial pole tip ~pixel y 920 (z ~613).
- Chimney 403 on the hall's north roof slope: top pixel y ~1105 (z 535),
  meets the roof at pixel y ~1140 (z ~503); open flue drawn at the top.

Slate cone tower (377, 380, 381, 396, 397, 404, ...), centre (722, 1742):
- Shaft: mask 291 edges at pixel rows 1350-1425 are x 616-822 (radius 104,
  centre x 719); rows 1300-1325 widen to x ~830-834 under the eave (radius
  111 from z ~415). Wall 9 units (inner radius 95).
- Cone eave tips at pixel x 592 / 847 (radius 127.5), side pixel y ~1245 and
  front eave pixel y ~1313: eave z 500 at radius 127. Cone apex (cap base)
  pixel (718, 1078): z 664; cap to z ~675; pole tip pixel y ~982 (z ~760).
- Stone chimney on the cone front: x 687-722, front face from pixel y ~1190
  (top edge) to ~1257 where it meets the cone: front face y 1797.5, z 540-607,
  top face 14 px deep (y 1783.5-1797.5).
- The shaft foot meets the plateau at z 220 (front foot pixel ~1585).

Hall (386, 388, 389, 392-395, 405, 407, 408): walls stand on the plateau
(z 220). The hip roof keeps the native traced facet vertices (apex A at
(557, 1684, 524), ridge to R (769, 1607, 523)); their pixels match the painted
eave corners (W1 pixel (455, 1222), S1 (524, 1278)) and apex (557, 1160).
Roof facets are closed 5-unit slabs; every wall under the roof rises to meet
the slab underside so the attic is closed. 388/389 (native invisible sight
blockers reaching z 510-550, not drawn in the artwork) are rebuilt as the
hall's north wall and east wall under the eaves; 407 owns the east hip facet.
"""
import math

from west_complex_geom import (PLATEAU_Z, SINE, Shape, lathe, native_obstacles, points, prism,
                               signed_area)

ROUND_C = (463.0, 1533.0)
CONE_C = (719.0, 1742.0)
ROOF_SLAB = 5.0


def _poly(obstacles, node):
    return [(x, y) for x, y, _, _ in points(obstacles, node)]


def _pip(pt, poly):
    x, y = pt
    inside = False
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i], poly[i - 1]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            inside = not inside
    return inside


def _plane(pts):
    """Least-squares plane z = a x + b y + c through native (x, y, z) points."""
    n = len(pts)
    sx = sum(p[0] for p in pts); sy = sum(p[1] for p in pts); sz = sum(p[2] for p in pts)
    sxx = sum(p[0] ** 2 for p in pts); syy = sum(p[1] ** 2 for p in pts); sxy = sum(p[0] * p[1] for p in pts)
    sxz = sum(p[0] * p[2] for p in pts); syz = sum(p[1] * p[2] for p in pts)
    m = [[sxx, sxy, sx, sxz], [sxy, syy, sy, syz], [sx, sy, n, sz]]
    for col in range(3):
        piv = max(range(col, 3), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        for r in range(3):
            if r != col:
                f = m[r][col] / m[col][col]
                m[r] = [a - f * b for a, b in zip(m[r], m[col])]
    a, b, c = (m[i][3] / m[i][i] for i in range(3))
    return lambda x, y: a * x + b * y + c


# ---------------------------------------------------------------- round tower

def _dome_profile():
    radius, lip, crown = 116.0, 482.5, 539.0
    prof = [(0.0, 478.0), (106.0, 478.0), (116.0, 480.0), (116.0, lip)]
    for r in (104.0, 90.0, 75.0, 60.0, 45.0, 30.0, 15.0):
        prof.append((r, lip + (crown - lip) * (1 - (r / radius) ** 1.1)))
    prof.append((0.0, crown))
    return prof


def round_tower(obstacles):
    shapes = {387: lathe(ROUND_C, [(0, PLATEAU_Z), (96.0, PLATEAU_Z), (96.0, 440.0), (0, 440.0)], 40),
              398: lathe(ROUND_C, [(0, 440.0), (106.0, 440.0), (106.0, 478.0), (0, 478.0)], 40)}
    dome = _dome_profile()
    # Native roof sectors: 399 front-west, 400 front-east, 401 back-east, 402 back-west
    # (native y grows toward the viewer; lathe angle 90 deg points south/front).
    sectors = {400: (0.0, math.pi / 2), 399: (math.pi / 2, math.pi),
               402: (math.pi, 1.5 * math.pi), 401: (1.5 * math.pi, 2 * math.pi)}
    for node, (a, b) in sectors.items():
        shapes[node] = lathe(ROUND_C, dome, 10, a, b)
    finial = lathe(ROUND_C, [(0, 533.0), (15.0, 533.0), (4.0, 549.0), (1.3, 549.0), (1.3, 611.0), (0, 614.0)], 8)
    shapes[399].add(finial)
    # Chimney 403 on the hall's north slope: open flue (2.5-unit rim, floor z 528).
    quad = _poly(obstacles, 403)
    cx = sum(p[0] for p in quad) / 4
    cy = sum(p[1] for p in quad) / 4
    inner = []
    for x, y in quad:
        dx, dyw = x - cx, (y - cy) / SINE
        k = (math.hypot(dx, dyw) - 3.5) / math.hypot(dx, dyw)
        inner.append((cx + dx * k, cy + (y - cy) * k))
    n = 4
    verts = ([(x, y, 488.0) for x, y in quad] + [(x, y, 535.0) for x, y in quad]
             + [(x, y, 535.0) for x, y in inner] + [(x, y, 528.0) for x, y in inner])
    faces = [list(reversed(range(n)))]
    faces += [[i, (i + 1) % n, (i + 1) % n + n, i + n] for i in range(n)]
    faces += [[n + i, n + (i + 1) % n, 2 * n + (i + 1) % n, 2 * n + i] for i in range(n)]
    faces += [[2 * n + i, 2 * n + (i + 1) % n, 3 * n + (i + 1) % n, 3 * n + i] for i in range(n)]
    faces += [list(range(3 * n, 4 * n))]
    shapes[403] = Shape.of(verts, faces)
    return shapes


# ---------------------------------------------------------------- hall roof

# Level south/west eave (z 436) re-seated on the wall line with the painted
# eave pixels preserved: the native south eave vertex (620, 1743, 465) is the
# same pixel as (628, 1723, ~445) but lies 25 units in front of the facade,
# whose foot the artwork draws at pixel y ~1496 (wall y ~1716).
APEX = (557.0, 1684.5, 524.0)
EAVE_Z = 436.0
W0 = (467.0, 1602.0, EAVE_Z)   # west eave at the round tower
W1 = (455.0, 1659.0, EAVE_Z)   # south-west hip corner, pixel (455, 1223) (painted 1222)
S1 = (520.0, 1714.0, EAVE_Z)   # south hip corner, pixel (520, 1278) (painted 1278)
S2 = (628.0, 1723.0, EAVE_Z)   # south eave at the cone tower, pixel 1287 (painted ~1290)
# North eave on the outer face of north wall 388 (+2 overhang), north-east
# corner where it meets east wall 389: the painted plank slope reaches pixel
# y ~1102 at x 600, which the native eave line (452,1587)-(681,1505) misses
# (the first combined audit showed 388's top exposed there).
ROOF_OUTLINE = [(460, 1569), (686, 1489), (846, 1676), (842, 1681), (789, 1693), (774, 1689), (736, 1684),
                (689, 1688), (659, 1700), (637, 1717), S2[:2], S1[:2], W1[:2], W0[:2]]
# Hall south/west wall ring (outer face then inner face), 7 units thick, set
# 4 units inside the eave; its west face reaches x ~461-472 where mask 291
# (hall) meets the round tower (combined coverage audit: x 463 on the facade
# rows), and its east end enters the cone-tower shaft.
HALL_WALL_TOP = [(472.5, 1588.0), (461.0, 1655.0), (519.0, 1710.0), (628.0, 1719.0),
                 (630.0, 1712.0), (522.0, 1703.5), (468.0, 1653.0), (479.5, 1587.0)]
# The west face is battered: mask 291's left edge runs from x 461 under the
# eave (pixel row 1240) to x 474 at the foot (row 1440), so the foot keeps the
# native x ~472-480 while the top follows the eave.
HALL_WALL_FOOT = [(479.0, 1588.0), (472.0, 1656.0), (519.0, 1710.0), (628.0, 1719.0),
                  (630.0, 1712.0), (522.0, 1703.5), (479.0, 1654.0), (486.0, 1587.0)]


def _facet_planes(obstacles):
    """Native traced facet planes (apex A (557,1684) z 524, ridge to R (769,1607))."""
    planes = {}
    for node in (391, 392):
        planes[node] = _plane([(x, y, zt) for x, y, _, zt in points(obstacles, node)])
    # Hip facets through the native apex and the level, wall-seated eave corners.
    planes[393] = _plane([APEX, S1, S2])
    planes[394] = _plane([APEX, W1, S1])
    planes[395] = _plane([APEX, W0, W1])
    # No east hip: the native ridge end R (769, 1607) lies only ~9 units inside
    # the east eave line, so a hip there would be near-vertical. The roof ends
    # in a gable over east wall 389; 407 is the raked verge strip on that edge.
    return planes


def _clip(poly, a, b, c):
    """Sutherland-Hodgman clip of a polygon to the half-plane a x + b y + c <= 0."""
    out = []
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        fp, fq = a * p[0] + b * p[1] + c, a * q[0] + b * q[1] + c
        if fp <= 0:
            out.append(p)
        if (fp < 0 < fq) or (fq < 0 < fp):
            t = fp / (fp - fq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    clean = []
    for p in out:
        if not clean or math.dist(clean[-1], p) > 1e-6:
            clean.append(p)
    if len(clean) > 1 and math.dist(clean[0], clean[-1]) < 1e-6:
        clean.pop()
    return clean


def hall_facets(obstacles):
    """Hip roof as the lower envelope of the native facet planes over the eave outline.

    The native facet polygons leave slivers and overlaps (e.g. the region
    between the apex and the round tower, where the artwork shows the roof
    rising to the window band). Taking min() of the traced planes over the
    eave outline yields a watertight hip roof; each owner keeps the region
    where its plane is lowest.
    """
    planes = _facet_planes(obstacles)
    coef = {n: (pl(1, 0) - pl(0, 0), pl(0, 1) - pl(0, 0), pl(0, 0)) for n, pl in planes.items()}
    facets = {}
    for node, (a, b, c) in coef.items():
        region = [tuple(map(float, p)) for p in ROOF_OUTLINE]
        for other, (a2, b2, c2) in coef.items():
            if other != node and len(region) >= 3:
                region = _clip(region, a - a2, b - b2, c - c2)
        if len(region) < 3 or abs(signed_area(region)) < 1.0:
            raise ValueError(f'Roof facet {node} vanished from the plane envelope')
        facets[node] = (region, planes[node])
    return facets


def draped_strip(edge_a, edge_b, samples, bottom, top):
    """Closed strip over a quad whose bottom/top heights follow functions of (x, y).

    edge_a/edge_b are ((x0, y0), (x1, y1)) long edges; ``samples`` are the
    parameters (0..1) of the cross sections, so a height peak between the
    corners (e.g. a ridge crossing a gable) is represented.
    """
    lerp = lambda e, t: (e[0][0] + (e[1][0] - e[0][0]) * t, e[0][1] + (e[1][1] - e[0][1]) * t)
    ts = sorted(set([0.0, 1.0] + [t for t in samples if 0 < t < 1]))
    verts, faces = [], []
    for t in ts:
        a, b = lerp(edge_a, t), lerp(edge_b, t)
        verts += [(*a, bottom(*a)), (*b, bottom(*b)), (*b, top(*b)), (*a, top(*a))]
    for i in range(len(ts) - 1):
        o, q = 4 * i, 4 * (i + 1)
        faces += [[o + k, q + k, q + (k + 1) % 4, o + (k + 1) % 4] for k in range(4)]
    last = 4 * (len(ts) - 1)
    faces += [[0, 1, 2, 3], [last + 3, last + 2, last + 1, last]]
    return Shape.of(verts, faces)


def _ridge_samples(env, edge, count=24):
    ts = [i / count for i in range(count + 1)]
    lerp = lambda t: (edge[0][0] + (edge[1][0] - edge[0][0]) * t, edge[0][1] + (edge[1][1] - edge[0][1]) * t)
    best = max(ts, key=lambda t: env(*lerp(t)))
    lo, hi = max(0.0, best - 1 / count), min(1.0, best + 1 / count)
    for _ in range(40):  # golden-section refinement of the ridge crossing
        m1, m2 = lo + (hi - lo) * 0.382, lo + (hi - lo) * 0.618
        if env(*lerp(m1)) < env(*lerp(m2)):
            lo = m1
        else:
            hi = m2
    return sorted(set(ts + [(lo + hi) / 2]))


def roof_envelope(obstacles):
    planes = _facet_planes(obstacles)
    return lambda x, y: min(pl(x, y) for pl in planes.values())


def _slab(poly, plane):
    top = [plane(x, y) for x, y in poly]
    return prism(poly, [t - ROOF_SLAB for t in top], top)


def roof_underside(facets, x, y, fallback=423.0):
    if not _pip((x, y), ROOF_OUTLINE):
        return fallback
    return min(plane(x, y) for poly, plane in facets.values()) - ROOF_SLAB


def hall(obstacles):
    facets = hall_facets(obstacles)
    shapes = {node: _slab(*facets[node]) for node in (392, 393, 394, 395)}
    env = roof_envelope(obstacles)
    # 407: raked verge strip on the east gable edge (native footprint), lying on
    # the roof from 2 below to 2 above the envelope, following the ridge peak.
    v = _poly(obstacles, 407)  # (840,1676) (828,1679) (680,1506) (692,1503)
    ea, eb = (v[0], v[3]), (v[1], v[2])
    shapes[407] = draped_strip(ea, eb, _ridge_samples(env, ea), lambda x, y: env(x, y) - ROOF_SLAB,
                               lambda x, y: env(x, y) + 2.0)

    def under_roof_prism(node, minimum=None, maximum=None):
        poly = _poly(obstacles, node)
        tops = []
        for x, y in poly:
            z = roof_underside(facets, x, y, fallback=423.0)
            if minimum is not None:
                z = max(z, minimum)
            if maximum is not None:
                z = min(z, maximum)
            tops.append(z)
        return prism(poly, PLATEAU_Z, tops)
    # South and west walls rise to the hip-roof underside (native top 423).
    # The west face is moved 8 units west: mask 291 (hall) reaches x 463 on
    # the rows of the facade (combined coverage audit showed the round-tower
    # shaft first-hit on x 463-471 where the artwork draws the hall facade).
    n = len(HALL_WALL_TOP)
    verts = ([(x, y, PLATEAU_Z) for x, y in HALL_WALL_FOOT]
             + [(x, y, roof_underside(facets, x, y)) for x, y in HALL_WALL_TOP])
    faces = [list(reversed(range(n))), list(range(n, 2 * n))]
    faces += [[i, (i + 1) % n, (i + 1) % n + n, i + n] for i in range(n)]
    shapes[386] = Shape.of(verts, faces)
    # North wall along the north eave; east wall under the east hip eave.
    shapes[388] = under_roof_prism(388)
    # East gable wall 389 rises to the roof underside, peaking under the ridge.
    w = _poly(obstacles, 389)  # (840,1676) (828,1679) (680,1506) (692,1503)
    wa, wb = (w[0], w[3]), (w[1], w[2])
    shapes[389] = draped_strip(wa, wb, _ridge_samples(env, wa), lambda x, y: PLATEAU_Z,
                               lambda x, y: env(x, y) - ROOF_SLAB)
    # Attic floor rings (reject-all interior) and wall plate 408 as closed slabs.
    for node in (390, 405):
        pts = points(obstacles, node)
        shapes[node] = prism([(x, y) for x, y, _, _ in pts], pts[0][2], pts[0][3])
    shapes[408] = prism(_poly(obstacles, 408), 411.0, 414.0)
    # Ground-floor furniture (Patch02 interior, reject-all): stand on the floor.
    for node in range(334, 345):
        pts = points(obstacles, node)
        bottom = PLATEAU_Z  # tables and benches are closed blocks on the floor
        shapes[node] = prism([(x, y) for x, y, _, _ in pts], bottom, max(p[3] for p in pts))
    return shapes


# ---------------------------------------------------------------- slate tower

SHAFT_IN, SHAFT_TOP = 95.0, 505.0
# Outer wall: radius 104 (mask 291 edges x 616-822 at pixel rows 1350-1425),
# widening to 111 under the eave (mask edge x 830-834 at rows 1300-1325).
SHAFT_OUTER = [(220.0, 104.0), (405.0, 104.0), (415.0, 111.0), (SHAFT_TOP, 111.0)]


def _angle(x, y, centre=CONE_C):
    return math.atan2((y - centre[1]) / SINE, x - centre[0]) % math.tau


def _outer_radius(z):
    for (za, ra), (zb, rb) in zip(SHAFT_OUTER, SHAFT_OUTER[1:]):
        if za <= z <= zb:
            return ra + (rb - ra) * (z - za) / (zb - za)
    raise ValueError(z)


def _ring(a, b, z0, z1, segments):
    outer = [(_outer_radius(z0), z0)] + [(r, z) for z, r in SHAFT_OUTER if z0 < z < z1] + [(_outer_radius(z1), z1)]
    return lathe(CONE_C, [(SHAFT_IN, z0)] + outer + [(SHAFT_IN, z1)], segments, a, b)


def slate_tower(obstacles):
    shapes = {}
    # Shaft ownership follows the native arcs: 377 the front half, 381 the
    # back-east arc (full height), 380 the back-west arc above the hall
    # ground-floor opening (native bottom z 317).
    west = _angle(615.0, 1717.0)   # ~ 194 deg (west point of the front arc)
    east = _angle(834.0, 1720.0)   # ~ 349 deg... front arc runs east -> south -> west
    split = _angle(688.0, 1688.0)  # back arc division between 380 and 381
    shapes[377] = _ring(east - math.tau, west, PLATEAU_Z, SHAFT_TOP, 28)
    shapes[380] = _ring(west, split, 317.0, SHAFT_TOP, 8)
    shapes[381] = _ring(split, east, PLATEAU_Z, SHAFT_TOP, 14)
    cone = [(0, 503.0), (106.0, 503.0), (127.0, 498.0), (127.0, 500.5), (0, 664.0)]
    shapes[396] = lathe(CONE_C, cone, 24, math.pi / 2, 1.5 * math.pi)
    shapes[397] = lathe(CONE_C, cone, 24, -math.pi / 2, math.pi / 2)
    shapes[396].add(lathe(CONE_C, [(0, 660.0), (13.0, 660.0), (3.0, 675.0), (1.3, 675.0),
                                   (1.3, 757.0), (0, 760.0)], 8))
    shapes[396].add(prism([(688.0, 1783.5), (721.0, 1783.5), (721.0, 1797.5), (688.0, 1797.5)], 530.0, 607.0))
    # Hall south slope (catalog-owned here): native traced facet as a slab.
    facets = hall_facets(obstacles)
    shapes[391] = _slab(*facets[391])
    # Junction stub between shaft and hall east wall.
    shapes[404] = prism(_poly(obstacles, 404), PLATEAU_Z, 425.0)
    # Tower ground floor (native 0-220 terrain chunk inside the shaft).
    shapes[73] = prism(_poly(obstacles, 73), 212.0, PLATEAU_Z)
    # Patch03 interior (reject-all): floors, stairs and landing as closed slabs.
    for node in (378, 379, 382, 384, 406):
        pts = points(obstacles, node)
        shapes[node] = prism([(x, y) for x, y, _, _ in pts], pts[0][2], pts[0][3])
    for node in (383, 385):
        pts = points(obstacles, node)
        tops = [max(zt, PLATEAU_Z + 3.0) for *_, zt in pts]
        shapes[node] = prism([(x, y) for x, y, _, _ in pts], [t - 4.0 for t in tops], tops)
    return shapes


GROUND = {'lincoln-west-round-tower': {'387': PLATEAU_Z, 'roof/band': 'on shaft'},
          'lincoln-west-tower-hall': {'walls 386/388/389': PLATEAU_Z, 'furniture 334-344': PLATEAU_Z},
          'lincoln-west-slate-tower': {'377/381': PLATEAU_Z, '380': 317.0, '73 (ground floor)': PLATEAU_Z}}


def build(asset):
    obstacles = native_obstacles()
    if asset == 'lincoln-west-round-tower':
        shapes = round_tower(obstacles)
        changes = [
            'Shaft 387 rebuilt as a closed 40-sided drum, radius 96 (artwork left edge x 365-367), from the plateau/bastion roof (z 220) to z 440 instead of the z 0 datum.',
            'Window band 398 rebuilt as a closed drum, radius 106 (artwork edge x ~354), z 440-478.',
            'Roof sectors 399-402 rebuilt as four closed quarter sectors of one low convex scale dome: widest ring radius 116 at z 480-482.5 (artwork x 347.5-579, front eave pixel y ~1115, back outline ~986), crown z 539; replaces the flat-faced wedges.',
            'Added the metal cap and finial pole (to z 614) on sector 399; chimney 403 rebuilt as an open-flue stack standing in the hall roof (z 488-535).']
        limitations = [
            'Window openings in the band and the scale-roof relief are texture on smooth surfaces.',
            'The finial is attached to sector 399 (all round-tower nodes share masks 249/250).',
            'The chimney bottom (z 488) is buried in the hall roof slab and is inferred.']
    elif asset == 'lincoln-west-tower-hall':
        shapes = hall(obstacles)
        changes = [
            'Walls 386 (south/west), 388 (north) and 389 (east) now stand on the plateau (z 220) and rise to the hip-roof underside instead of z 0-423/510/550 pillars.',
            'Hip roof facets 392 (north slope), 393/394/395 (south/south-west/west hips) and 407 (east hip) rebuilt as closed 5-unit slabs on the native traced facet planes (apex (557,1684) z 524, ridge to (769,1607) z 523).',
            '388/389 (tall invisible native sight blockers not drawn in the artwork) trimmed to plausible north/east walls under the eaves.',
            'Attic rings 390/405, wall plate 408 and ground-floor furniture 334-344 rebuilt as closed slabs/prisms standing on their floors (furniture from z 220).']
        limitations = [
            'The native roof facets overhang the wall line irregularly (up to 17 units at the south-west hip); kept because their pixels match the painted eaves.',
            'The hall north-west roof corner dies into the round tower; its hidden sliver is not modelled.',
            'Ground-floor furniture and attic floors are reject-all interior (Patch02/Patch03) and stay neutral; the revealed state is not reviewed.',
            'Roof-base rings 390/405 and cone-ring 391 span several objects; they are kept as single catalog-owned meshes (no component split).']
    elif asset == 'lincoln-west-slate-tower':
        shapes = slate_tower(obstacles)
        changes = [
            'Shaft rebuilt as a hollow round tower (outer radius 104 widening to 111 under the eave from z 415, 9-unit wall, centre (719,1742) from mask 291 edges) split by native arcs: 377 front half and 381 back-east arc from the plateau (z 220), 380 back-west arc from z 317 (hall ground-floor opening), all to z 505.',
            'Cone 396/397 rebuilt as closed west/east halves of a true cone: eave radius 127 at z 500 (artwork eave tips x 592/847, front pixel y ~1313), apex z 664, replacing the native tent-shaped halves with a ridge line.',
            'Added the cap and finial pole (to z 760) and the stone chimney on the cone front (x 688-721, z 530-607) on 396.',
            'Hall south slope 391 rebuilt as a closed slab on its native plane; stub 404 and ground-floor slab 73 trimmed to the plateau.',
            'Patch03 interior floors/stairs (378, 379, 382-385, 406) rebuilt as closed slabs at their native heights.']
        limitations = [
            'Interior floors, stairs and ground-floor slab 73 are reject-all (hidden in the covered state) and stay neutral; the Patch03 revealed state is not reviewed.',
            'Cone ring 391 spans the hall roof and cone base and is kept as one mesh; a component split may be needed for the revealed state.',
            'Chimney flues and slate relief are texture.']
    else:
        raise KeyError(asset)
    return shapes, {'ground_native_z': GROUND[asset], 'changes': changes, 'limitations': limitations}
