"""Native-coordinate geometry builders for the Lincoln south gate and wall lane.

Pure Python (no bpy), so the same code runs in Blender recipes and in offline
trace/report tools. Native coordinates are the map's sight-obstacle frame:
(x, y) is the ground footprint and z the height; covered.png pixel = (x, y - z).
Blender world coordinates are X = x, Y = -y / sin35, Z = z / cos35.
"""
import math

SIN = math.sin(math.radians(35))
COS = math.cos(math.radians(35))


def to_world(p):
    x, y, z = p
    return (x, -y / SIN, z / COS)


def to_native(p):
    X, Y, Z = p
    return (X, -Y * SIN, Z * COS)


def pixel(p):
    return (p[0], p[1] - p[2])


class Mesh:
    """Vertex-deduplicated face soup in native coordinates."""

    def __init__(self):
        self.verts, self.faces, self.index = [], [], {}

    def v(self, p):
        key = tuple(round(float(c), 4) for c in p)
        if key not in self.index:
            self.index[key] = len(self.verts)
            self.verts.append(key)
        return self.index[key]

    def face(self, pts):
        ids = [self.v(p) for p in pts]
        ids = [i for k, i in enumerate(ids) if i != ids[k - 1]]
        if len(set(ids)) >= 3:
            self.faces.append(ids)

    def extend(self, other):
        for f in other.faces:
            self.face([other.verts[i] for i in f])

    def add_shell(self, other):
        """Append another closed shell without merging coincident vertices."""
        base = len(self.verts)
        self.verts.extend(other.verts)
        self.faces.extend([[i + base for i in f] for f in other.faces])
        # Keep the dedup index pointing at this shell's own vertices only.

    def cancel_duplicates(self):
        """Remove coincident opposite faces (internal walls between cells)."""
        seen = {}
        for f in self.faces:
            key = tuple(sorted(f))
            if key in seen:
                del seen[key]
            else:
                seen[key] = f
        self.faces = list(seen.values())


def lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(len(a)))


def polyline_length(poly):
    return sum(math.dist(a, b) for a, b in zip(poly, poly[1:]))


def point_at(poly, s):
    """Point at arc length s along a polyline (clamped)."""
    if s <= 0:
        return tuple(poly[0])
    acc = 0.0
    for a, b in zip(poly, poly[1:]):
        L = math.dist(a, b)
        if acc + L >= s and L > 0:
            return lerp(a, b, (s - acc) / L)
        acc += L
    return tuple(poly[-1])


def arc_param_at_x(poly, x):
    """Arc length along poly where the polyline first reaches image column x."""
    acc = 0.0
    for a, b in zip(poly, poly[1:]):
        L = math.dist(a, b)
        lo, hi = sorted((a[0], b[0]))
        if lo - 1e-9 <= x <= hi + 1e-9 and abs(b[0] - a[0]) > 1e-9:
            return acc + L * (x - a[0]) / (b[0] - a[0])
        acc += L
    raise ValueError(f'column {x} is not on polyline {poly[0]}..{poly[-1]}')


def prism(poly, bottom, top, subdivide=None):
    """Closed vertical prism over a simple polygon.

    bottom/top: number or callable (x, y) -> z. With ``subdivide`` (max edge
    length) long edges receive extra vertices so a varying bottom can follow
    measured ground. Caps are n-gons; a varying bottom cap is non-planar but
    is always buried below ground.
    """
    pts = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        n = 1 if not subdivide else max(1, int(math.ceil(math.dist(a, b) / subdivide)))
        pts.extend(lerp(a, b, i / n) for i in range(n))
    zb = [bottom(*p) if callable(bottom) else bottom for p in pts]
    zt = [top(*p) if callable(top) else top for p in pts]
    m = Mesh()
    n = len(pts)
    m.face([(p[0], p[1], z) for p, z in zip(pts, zt)])
    m.face([(p[0], p[1], z) for p, z in reversed(list(zip(pts, zb)))])
    for i in range(n):
        j = (i + 1) % n
        m.face([(pts[i][0], pts[i][1], zb[i]), (pts[j][0], pts[j][1], zb[j]),
                (pts[j][0], pts[j][1], zt[j]), (pts[i][0], pts[i][1], zt[i])])
    return m


def ribbon(outer, inner, stations, bottom, cells, closed=False):
    """Closed strip solid between two polylines with stepped tops.

    ``stations`` are normalised parameters t in [0, 1]; station k lies at
    arc fraction t on both ``outer`` and ``inner`` (so cut faces run across the
    strip). ``bottom`` is a number or callable(t) -> z. ``cells[k]`` is the
    (z_at_start, z_at_end) top of the cell between stations k and k+1. For a
    closed loop the last cell wraps from the last station back to station 0.
    Steps between neighbouring cells become explicit vertical faces, and
    T-junctions are avoided by inserting every station level into both faces.
    """
    Lo, Li = polyline_length(outer), polyline_length(inner)
    O = [point_at(outer, t * Lo) for t in stations]
    I = [point_at(inner, t * Li) for t in stations]
    n = len(stations)
    ncell = n if closed else n - 1
    assert len(cells) == ncell, (len(cells), ncell)
    zb = [bottom(t) if callable(bottom) else bottom for t in stations]
    levels = [set([zb[k]]) for k in range(n)]
    for c in range(ncell):
        a, b = c, (c + 1) % n
        levels[a].add(cells[c][0])
        levels[b].add(cells[c][1])
    m = Mesh()
    P = lambda side, k, z: (side[k][0], side[k][1], z)

    def run(k, lo, hi):
        return sorted(z for z in levels[k] if lo < z < hi)

    for c in range(ncell):
        a, b = c, (c + 1) % n
        ta, tb = cells[c]
        for side, rev in ((O, False), (I, True)):
            poly = [P(side, a, zb[a]), P(side, b, zb[b])]
            poly += [P(side, b, z) for z in run(b, zb[b], tb)]
            poly += [P(side, b, tb), P(side, a, ta)]
            poly += [P(side, a, z) for z in reversed(run(a, zb[a], ta))]
            m.face(list(reversed(poly)) if rev else poly)
        m.face([P(O, a, ta), P(O, b, tb), P(I, b, tb), P(I, a, ta)])
        m.face([P(O, a, zb[a]), P(I, a, zb[a]), P(I, b, zb[b]), P(O, b, zb[b])])
    for k in range(n):
        left = cells[k - 1][1] if (closed or k > 0) else None
        right = cells[k][0] if (closed or k < n - 1) else None
        if left is not None and right is not None:
            lo, hi = sorted((left, right))
            if hi - lo > 1e-6:
                zs = [lo] + run(k, lo, hi) + [hi]
                m.face([P(O, k, z) for z in zs] + [P(I, k, z) for z in reversed(zs)])
        else:
            top = left if left is not None else right
            zs = [zb[k]] + run(k, zb[k], top) + [top]
            m.face([P(O, k, z) for z in zs] + [P(I, k, z) for z in reversed(zs)])
    return m


def crenel_cells(stations, notches, merlon_top, sill):
    """Cell tops for a parapet whose notches are station index pairs."""
    tops = []
    for c in range(len(stations) - 1):
        notch = any(a <= c < b for a, b in notches)
        z = sill if notch else merlon_top
        tops.append((z, z))
    return tops


def crenellated_strip(outer, inner, notch_params, bottom, merlon_top, sill,
                      extra_stations=(), closed=False):
    """Strip with notches given as normalised (t0, t1) intervals along it."""
    ts = {0.0, 1.0} | set(extra_stations)
    for a, b in notch_params:
        ts.update((a, b))
    stations = sorted(t for t in ts if 0.0 <= t <= 1.0)
    if closed:
        stations = [t for t in stations if t < 1.0]
    cells = []
    count = len(stations) if closed else len(stations) - 1
    for c in range(count):
        a = stations[c]
        b = stations[c + 1] if c + 1 < len(stations) else 1.0
        mid = (a + b) / 2
        notch = any(lo <= mid <= hi for lo, hi in notch_params)
        mt = merlon_top(mid) if callable(merlon_top) else merlon_top
        sl = sill(mid) if callable(sill) else sill
        z = sl if notch else mt
        cells.append((z, z))
    return ribbon(outer, inner, stations, bottom, cells, closed=closed)


def validate(mesh):
    """Return edge-use statistics; a closed 2-manifold has only 2-use edges."""
    from collections import Counter
    use = Counter()
    for f in mesh.faces:
        for i in range(len(f)):
            e = tuple(sorted((f[i], f[(i + 1) % len(f)])))
            use[e] += 1
    bad = {e: c for e, c in use.items() if c != 2}
    return {'vertices': len(mesh.verts), 'faces': len(mesh.faces),
            'edges': len(use), 'nonmanifold_edges': len(bad)}
