"""Pure-Python closed-shell builders for the Lincoln village lane.

Every builder returns ``(vertices, faces)`` in Blender world coordinates
(X = native x, Y = -native y / sin 35, Z = native z / cos 35).  No bpy import:
the same definitions feed the Blender recipe and offline source overlays.
"""
import math

SIN = math.sin(math.radians(35))
COS = math.cos(math.radians(35))


def pixel(p):
    """Source-artwork pixel of a world point (oblique orthographic 35 degree camera)."""
    return (p[0], -p[1] * SIN - p[2] * COS)


def world_from_pixel(px, py, y=None, z=None):
    """Solve the world point on a known Y (depth) or Z (height) that projects to a pixel."""
    if y is not None:
        return (px, y, (-py - y * SIN) / COS)
    if z is not None:
        return (px, (-py - z * COS) / SIN, z)
    raise ValueError('Give a depth (y) or a height (z)')


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def mul(a, s):
    return tuple(x * s for x in a)


def lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def length(a):
    return math.sqrt(sum(x * x for x in a))


def unit(a):
    n = length(a)
    return tuple(x / n for x in a)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


class Frame:
    """Building frame: origin, long axis ``ex``, horizontal depth axis ``ey``, up ``ez``."""

    def __init__(self, origin, along):
        self.o = tuple(origin)
        ax = unit((along[0], along[1], 0.0))
        self.ex = ax
        self.ey = (-ax[1], ax[0], 0.0)
        self.ez = (0.0, 0.0, 1.0)

    def at(self, x, y, z):
        return tuple(self.o[i] + self.ex[i] * x + self.ey[i] * y + self.ez[i] * z for i in range(3))


def extrude(frame, profile, x0, x1):
    """Closed prism: a planar (y, z) profile (counter-clockwise seen from +x) swept along x."""
    n = len(profile)
    area = sum(profile[i][0] * profile[(i + 1) % n][1] - profile[(i + 1) % n][0] * profile[i][1] for i in range(n))
    if (area < 0) != (x1 < x0):
        profile = list(reversed(profile))
    verts = [frame.at(x0, y, z) for y, z in profile] + [frame.at(x1, y, z) for y, z in profile]
    faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return verts, faces


def extrude_between(profile_a, profile_b):
    """Closed shell between two corresponding world-space loops (same vertex count)."""
    n = len(profile_a)
    verts = list(profile_a) + list(profile_b)
    faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return verts, faces


def box(corner, a, b, c):
    """Parallelepiped from a corner and three edge vectors."""
    p = [corner, add(corner, a), add(add(corner, a), b), add(corner, b)]
    q = [add(v, c) for v in p]
    verts = p + q
    faces = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return verts, faces


def frame_box(frame, x0, x1, y0, y1, z0, z1):
    return extrude(frame, [(y0, z0), (y1, z0), (y1, z1), (y0, z1)], x0, x1)


def lathe(base, axis, ref, rings, segments=12):
    """Closed solid of revolution; ``rings`` = [(t, radius)] along the axis, radius > 0."""
    axis = unit(axis)
    u = unit(cross(axis, ref))
    v = cross(axis, u)
    verts = []
    for t, r in rings:
        c = add(base, mul(axis, t))
        for k in range(segments):
            a = 2 * math.pi * k / segments
            verts.append(add(c, add(mul(u, r * math.cos(a)), mul(v, r * math.sin(a)))))
    faces = []
    m = len(rings)
    for i in range(m - 1):
        for k in range(segments):
            a = i * segments + k
            b = i * segments + (k + 1) % segments
            faces.append((a, b, b + segments, a + segments))
    faces.append(tuple(reversed(range(segments))))
    faces.append(tuple(range((m - 1) * segments, m * segments)))
    return verts, faces


def post(bottom, top, radius, segments=6):
    return lathe(bottom, sub(top, bottom), (1.0, 0.3, 0.0), [(0, radius), (length(sub(top, bottom)), radius)],
                 segments)


def merge(*shells):
    verts, faces = [], []
    for sv, sf in shells:
        off = len(verts)
        verts.extend(sv)
        faces.extend(tuple(off + i for i in f) for f in sf)
    return verts, faces


def gable_walls(frame, x0, x1, depth, front_eave, back_eave, ridge_y, ridge_z, z0=0.0):
    """Pentagonal gable body; the ridge peak meets the roof underside."""
    profile = [(0.0, z0), (depth, z0), (depth, back_eave), (ridge_y, ridge_z), (0.0, front_eave)]
    return extrude(frame, profile, x0, x1)


def thatch_roof(frame, x0, x1, ridge_y, ridge_z, front, back, thickness, bulge=0.0, steps=1):
    """Closed thick gable thatch: ``front``/``back`` = (y, z) of the lower outer eave points.

    The outer surface optionally bulges (convex thatch shoulders) between eave and ridge.
    """
    outer = []
    fy, fz = front
    by, bz = back

    def slope(p, q, k):
        pts = []
        for i in range(k + 1):
            t = i / k
            y = p[0] + (q[0] - p[0]) * t
            z = p[1] + (q[1] - p[1]) * t + bulge * 4 * t * (1 - t)
            pts.append((y, z))
        return pts

    outer = slope((fy, fz), (ridge_y, ridge_z), steps) + slope((ridge_y, ridge_z), (by, bz), steps)[1:]
    # Inner (underside) points: offset straight down by the thickness, eaves keep a vertical lip.
    inner = [(y, z - thickness) for y, z in reversed(outer)]
    profile = outer + inner
    return extrude(frame, profile, x0, x1)


def weld(verts, faces, digits=4):
    compact, lookup, remap = [], {}, {}
    for i, p in enumerate(verts):
        key = tuple(round(c, digits) for c in p)
        if key not in lookup:
            lookup[key] = len(compact)
            compact.append(p)
        remap[i] = lookup[key]
    out = []
    for f in faces:
        ids = list(dict.fromkeys(remap[i] for i in f))
        if len(ids) >= 3:
            out.append(tuple(ids))
    return compact, out


def roof_halves(frame, x0, x1, ridge_y, ridge_z, front, back, thickness, bulge=0.0, steps=1):
    """Front and back thatch slopes as two closed slabs meeting at the ridge plane.

    ``front``/``back`` are the outer (upper) eave points (y, z); the slab is ``thickness``
    thick measured vertically.  Returns (front_shell, back_shell, underside(y)).
    """
    def slope(p, q):
        pts = []
        for i in range(steps + 1):
            t = i / steps
            pts.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t + bulge * 4 * t * (1 - t)))
        return pts

    f_outer = slope(front, (ridge_y, ridge_z))
    b_outer = slope((ridge_y, ridge_z), back)
    f_profile = f_outer + [(y, z - thickness) for y, z in reversed(f_outer)]
    b_profile = b_outer + [(y, z - thickness) for y, z in reversed(b_outer)]

    def underside(y):
        pts = f_outer + b_outer[1:]
        for (ya, za), (yb, zb) in zip(pts, pts[1:]):
            if min(ya, yb) - 1e-6 <= y <= max(ya, yb) + 1e-6:
                t = 0 if yb == ya else (y - ya) / (yb - ya)
                return za + (zb - za) * t - thickness
        raise ValueError(f'y={y} outside the roof')

    return extrude(frame, f_profile, x0, x1), extrude(frame, b_profile, x0, x1), underside


def mound(center, along, rx, ry, height, rings=5, segments=14, top=0.35):
    """Closed rounded heap (half-ellipsoid) with elliptical footprint rx x ry."""
    ax = unit((along[0], along[1], 0.0))
    ay = (-ax[1], ax[0], 0.0)
    verts = []
    levels = []
    for i in range(rings):
        t = i / (rings - 1)
        ang = t * (math.pi / 2) * (1 - 0.02)
        s = max(math.cos(ang), top * 0.2) if i < rings - 1 else top * 0.25
        z = height * math.sin(ang) if i < rings - 1 else height
        levels.append((s, z))
    for s, z in levels:
        for k in range(segments):
            a = 2 * math.pi * k / segments
            x = rx * s * math.cos(a)
            y = ry * s * math.sin(a)
            verts.append((center[0] + ax[0] * x + ay[0] * y, center[1] + ax[1] * x + ay[1] * y, center[2] + z))
    faces = []
    for i in range(rings - 1):
        for k in range(segments):
            a = i * segments + k
            b = i * segments + (k + 1) % segments
            faces.append((a, b, b + segments, a + segments))
    faces.append(tuple(reversed(range(segments))))
    faces.append(tuple(range((rings - 1) * segments, rings * segments)))
    return verts, faces


def hip_roof(frame, x0, x1, y_front, y_back, z_front, z_back, ridge_y, ridge_z, hip0, hip1, thickness):
    """Closed thick hipped/half-hipped roof in a building frame.

    Eave rectangle spans x0..x1 and y_front..y_back at heights z_front / z_back (outer
    surface).  The ridge runs at (ridge_y, ridge_z) from x0 + hip0 to x1 - hip1; hip 0
    gives a gable end.  The underside is the outer surface lowered by ``thickness``.
    """
    top = [frame.at(x0, y_front, z_front), frame.at(x1, y_front, z_front),
           frame.at(x1, y_back, z_back), frame.at(x0, y_back, z_back),
           frame.at(x0 + hip0, ridge_y, ridge_z), frame.at(x1 - hip1, ridge_y, ridge_z)]
    bottom = [(p[0], p[1], p[2] - thickness) for p in top]
    verts = top + bottom
    faces = [(0, 1, 5, 4), (2, 3, 4, 5), (1, 2, 5), (3, 0, 4)]
    under = [tuple(6 + i for i in reversed(f)) for f in faces]
    rim = [(b, a, a + 6, b + 6) for a, b in ((0, 1), (1, 2), (2, 3), (3, 0))]
    return verts, faces + under + rim


def ring(center, axis, ref, r_in, r_out, width, segments=18):
    """Closed annulus (wheel rim) of ``width`` along ``axis`` centred on ``center``."""
    axis = unit(axis)
    u = unit(cross(axis, ref))
    v = cross(axis, u)
    verts = []
    for side in (-0.5, 0.5):
        c = add(center, mul(axis, side * width))
        for r in (r_out, r_in):
            for k in range(segments):
                a = 2 * math.pi * k / segments
                verts.append(add(c, add(mul(u, r * math.cos(a)), mul(v, r * math.sin(a)))))
    n = segments
    # index blocks: 0 outer@-, n inner@-, 2n outer@+, 3n inner@+
    faces = []
    for k in range(n):
        a, b = k, (k + 1) % n
        faces.append((a, b, 2 * n + b, 2 * n + a))            # outer tyre
        faces.append((n + b, n + a, 3 * n + a, 3 * n + b))    # inner bore
        faces.append((b, a, n + a, n + b))                    # side -
        faces.append((2 * n + a, 2 * n + b, 3 * n + b, 3 * n + a))  # side +
    return verts, faces


def bowl(loops):
    """Closed hollow hull from four equal-length loops: outer bottom, outer rim, inner rim, inner floor."""
    n = len(loops[0])
    verts = [p for loop in loops for p in loop]
    faces = [tuple(reversed(range(n)))]                          # keel / bottom
    for s in range(3):                                           # outer side, rim top, inner side
        a, b = s * n, (s + 1) * n
        faces += [(a + k, a + (k + 1) % n, b + (k + 1) % n, b + k) for k in range(n)]
    faces.append(tuple(3 * n + k for k in range(n)))             # inner floor (faces up)
    return verts, faces


def loft(rings):
    """Closed shell through equal-length horizontal-ish loops (bottom first)."""
    n = len(rings[0])
    verts = [p for r in rings for p in r]
    faces = [tuple(reversed(range(n)))]
    for i in range(len(rings) - 1):
        a, b = i * n, (i + 1) * n
        faces += [(a + k, a + (k + 1) % n, b + (k + 1) % n, b + k) for k in range(n)]
    faces.append(tuple((len(rings) - 1) * n + k for k in range(n)))
    return verts, faces
