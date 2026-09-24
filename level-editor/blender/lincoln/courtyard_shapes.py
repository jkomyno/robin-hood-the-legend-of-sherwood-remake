"""Measured courtyard-lane shapes for Lincoln, independent of Blender.

Coordinates are authored in native map units (x, y, z) and converted to Blender
world space: X = x, Y = -y / sin35, Z = z / cos35. A native point projects to
source pixel (x, y - z). Every building and prop in this lane stands on the
castle plateau whose top is native z = 220; the native obstacles are extruded
from z = 0, so every shell here is rebuilt from the plateau surface upward.

`build(asset_id)` returns {source_node: [shell, ...]} where a shell is
(vertices_world, faces). Shells are closed; Blender recomputes outward normals.
"""
import math

import numpy as np

S = math.sin(math.radians(35))
C = math.cos(math.radians(35))
GROUND = 220.0  # native plateau height shared by every asset in this lane


def W(x, y, z):
    """Native point to Blender world."""
    return np.array([x, -y / S, z / C], dtype=float)


def nat(p):
    """Blender world point to native (x, y, z)."""
    return np.array([p[0], -p[1] * S, p[2] * C])


def pixel(p):
    n = nat(p)
    return n[0], n[1] - n[2]


class Plane:
    """Z = a*X + b*Y + c in world space, through three world points."""

    def __init__(self, p0, p1, p2):
        m = np.array([[p0[0], p0[1], 1], [p1[0], p1[1], 1], [p2[0], p2[1], 1]], float)
        self.a, self.b, self.c = np.linalg.solve(m, [p0[2], p1[2], p2[2]])

    def __call__(self, X, Y):
        return self.a * X + self.b * Y + self.c

    def shifted(self, dz):
        q = Plane.__new__(Plane)
        q.a, q.b, q.c = self.a, self.b, self.c + dz
        return q


def const(z_native):
    zw = z_native / C
    return lambda X, Y: zw


def prism(poly_xy, bottom, top):
    """Closed prism over a plan polygon (world XY) between two height functions."""
    n = len(poly_xy)
    verts = [np.array([x, y, bottom(x, y)]) for x, y in poly_xy]
    verts += [np.array([x, y, top(x, y)]) for x, y in poly_xy]
    for x, y in poly_xy:
        if top(x, y) - bottom(x, y) < 1e-3:
            raise ValueError('Degenerate prism: top is not above bottom')
    faces = [list(reversed(range(n))), list(range(n, 2 * n))]
    faces += [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
    return verts, faces


def slab(top_quad, thickness_native):
    """Planar roof slab: a top quad (world) and its copy lowered vertically."""
    dz = thickness_native / C
    verts = [np.array(p, float) for p in top_quad] + [np.array(p, float) - [0, 0, dz] for p in top_quad]
    faces = [[0, 1, 2, 3], [7, 6, 5, 4], [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]]
    return verts, faces


def box_between(p0, p1, width, depth):
    """Square-section beam from world p0 to p1 (posts, rails)."""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    axis = p1 - p0
    axis /= np.linalg.norm(axis)
    helper = np.array([0, 0, 1.0]) if abs(axis[2]) < 0.9 else np.array([1.0, 0, 0])
    u = np.cross(axis, helper)
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    verts = [p0 + u * a * width / 2 + v * b * depth / 2 for a, b in corners]
    verts += [p1 + u * a * width / 2 + v * b * depth / 2 for a, b in corners]
    faces = [[3, 2, 1, 0], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    return verts, faces


def cylinder(p0, p1, radius, segments=16, radius1=None):
    """Closed cylinder (or frustum) around the world axis p0->p1."""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    axis = p1 - p0
    axis /= np.linalg.norm(axis)
    helper = np.array([0, 0, 1.0]) if abs(axis[2]) < 0.9 else np.array([1.0, 0, 0])
    u = np.cross(axis, helper)
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    r1 = radius if radius1 is None else radius1
    verts = []
    for centre, r in ((p0, radius), (p1, r1)):
        for k in range(segments):
            t = 2 * math.pi * k / segments
            verts.append(centre + (u * math.cos(t) + v * math.sin(t)) * r)
    n = segments
    faces = [list(reversed(range(n))), list(range(n, 2 * n))]
    faces += [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
    return verts, faces


def dome_part(centre, rx, ry, height, theta0, theta1, rings=5, segments=8, flat_top=0.0):
    """Closed ellipsoidal mound sector between angles theta0..theta1 (radians).

    The sector's two bounding angles must lie on one straight line through the
    centre so the cut face is planar. `centre` is the world ground point.
    """
    cx, cy, cz = centre
    arc = [theta0 + (theta1 - theta0) * j / segments for j in range(segments + 1)]
    verts, rows = [], []
    for k in range(rings):
        f = k / rings
        z = cz + height * f
        s = math.sqrt(max(0.0, 1 - f * f)) if flat_top == 0 else math.sqrt(max(0.0, 1 - (f * (1 - flat_top)) ** 2))
        row = []
        for t in arc:
            row.append(len(verts))
            verts.append(np.array([cx + rx * s * math.cos(t), cy + ry * s * math.sin(t), z]))
        rows.append(row)
    apex = len(verts)
    verts.append(np.array([cx, cy, cz + height]))
    faces = [list(reversed(rows[0]))]
    for k in range(rings - 1):
        for j in range(segments):
            faces.append([rows[k][j], rows[k][j + 1], rows[k + 1][j + 1], rows[k + 1][j]])
    for j in range(segments):
        faces.append([rows[-1][j], rows[-1][j + 1], apex])
    cut = [rows[k][0] for k in range(rings)] + [apex] + [rows[k][-1] for k in reversed(range(rings))]
    faces.append(list(reversed(cut)))
    return verts, faces


def lerp(a, b, t):
    return np.array(a, float) + (np.array(b, float) - np.array(a, float)) * t


def extend(p, q, distance):
    """Point beyond p on the line q->p by a world distance."""
    d = np.array(p, float) - np.array(q, float)
    return np.array(p, float) + d / np.linalg.norm(d) * distance


def roof_quad(ridge0, ridge1, eave0, eave1, eave_out, gable_out):
    """Extend a planar roof quad (world) past its eaves and gables."""
    e0 = extend(eave0, ridge0, eave_out)
    e1 = extend(eave1, ridge1, eave_out)
    r0, r1 = np.array(ridge0, float), np.array(ridge1, float)
    along = (r1 - r0) / np.linalg.norm(r1 - r0)
    return [r0 - along * gable_out, r1 + along * gable_out, e1 + along * gable_out, e0 - along * gable_out]


def xy(*points):
    return [(p[0], p[1]) for p in points]


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

def _ground_body(plan, top):
    return prism(plan, const(GROUND), top)


def gable_house(ridge0, ridge1, back0, back1, front0, front1, *, eave_out, gable_out, thickness):
    """Two-slope house from native ridge/eave corners (world points).

    Walls stand on the eave footprint; roof slabs extend past walls. Returns
    (back_roof, back_body, front_roof, front_body) shells.
    """
    back_plane = Plane(ridge0, ridge1, back1)
    front_plane = Plane(ridge0, ridge1, front1)
    back_roof = slab(roof_quad(ridge0, ridge1, back0, back1, eave_out, gable_out), thickness)
    front_roof = slab(roof_quad(ridge0, ridge1, front0, front1, eave_out, gable_out), thickness)
    t = thickness / C
    back_body = _ground_body(xy(back0, back1, ridge1, ridge0), back_plane.shifted(-t))
    front_body = _ground_body(xy(ridge0, ridge1, front1, front0), front_plane.shifted(-t))
    return back_roof, back_body, front_roof, front_body


def at_x(p, q, x):
    """Point on the world line p->q with world X = x (native x is identical)."""
    return lerp(p, q, (x - p[0]) / (q[0] - p[0]))


def thatched_cottage():
    # Ridge at native z 335 (349: 333, 350: 336); eaves 304 back, 281 front.
    r0, r1 = W(1333, 1707.5, 335), W(1482, 1673.5, 335)
    b0, b1 = W(1316, 1685, 304), W(1463, 1651, 304)
    f0, f1 = W(1360, 1745, 281), W(1509, 1711, 281)
    # The drawn west gable wall and verge reach pixel x ~1300, about eight
    # world units west of the obstacle's gable; extend the west end.
    west = (r0 - r1) / np.linalg.norm(r0 - r1) * 8.0
    r0, b0, f0 = r0 + west, b0 + west, f0 + west
    # The drawn east verge runs from pixel (~1474, 1338) to (~1505, 1440),
    # about five units west of the obstacle's 349/351 gable and flush with the
    # gable wall (no east overhang; the shingle cottage's shaded west gable
    # and the stile are drawn immediately beyond it).
    r1, b1, f1 = at_x(r0, r1, 1477.0), at_x(b0, b1, 1458.0), at_x(f0, f1, 1504.0)
    split = 0.78  # 349/351 boundary, parallel to the gable
    th = 8.0 / C
    back_plane = Plane(r0, r1, b1)
    front_plane = Plane(r0, r1, f1)
    along = (r1 - r0) / np.linalg.norm(r1 - r0)
    gable_w = 5.0  # west verge overhang; the east verge is flush
    eave_out = 7.0

    def eave(p, ridge_point):
        return extend(p, ridge_point, eave_out)
    back_roof = slab([r0 - along * gable_w, r1, eave(b1, r1), eave(b0, r0) - along * gable_w], 8.0)
    # The drawn east gable wall stands ~21 px west of the verge (front wall
    # ends at pixel x ~1483): the thatch overhangs the east gable.
    wall_back = along * 22.7
    back_body = _ground_body(xy(b0, b1 - wall_back, r1 - wall_back, r0), back_plane.shifted(-th))
    rm, fm = lerp(r0, r1, split), lerp(f0, f1, split)
    front_west = slab([r0 - along * gable_w, rm, eave(fm, rm), eave(f0, r0) - along * gable_w], 8.0)
    front_east = slab([rm, r1, eave(f1, r1), eave(fm, rm)], 8.0)
    body_west = _ground_body(xy(r0, rm, fm, f0), front_plane.shifted(-th))
    body_east = _ground_body(xy(rm, r1 - wall_back, f1 - wall_back, fm), front_plane.shifted(-th))
    # Chimney 363 rises through the front slope; start it inside the roof.
    chimney = prism(xy(W(1362, 1710, 0), W(1378, 1706, 0), W(1383, 1713, 0), W(1368, 1717, 0)),
                    const(300), const(335))
    # Stile 355 between the cottages: low plank gate from the plateau.
    stile = prism(xy(W(1486, 1714, 0), W(1530, 1711, 0), W(1530, 1713, 0), W(1486, 1716, 0)),
                  const(GROUND), const(243))
    # Barrel 356 beside the west gable.
    c = W(1335.5, 1726, GROUND)
    barrel = cylinder(c, c + [0, 0, (245 - GROUND) / C], 7.5, 14, )
    # 364 was one collision volume spanning both cottages (reject-all). Keep
    # the node as a concealed core wholly inside this cottage's walls.
    core_plan = [lerp(lerp(b0, b1, .10), lerp(f0, f1, .10), .15), lerp(lerp(b0, b1, .78), lerp(f0, f1, .78), .15),
                 lerp(lerp(b0, b1, .78), lerp(f0, f1, .78), .85), lerp(lerp(b0, b1, .10), lerp(f0, f1, .10), .85)]
    core = prism(xy(*core_plan), const(GROUND + 2), const(270))
    return {
        'building-350': [back_roof, back_body],
        'building-349': [front_west, body_west],
        'building-351': [front_east, body_east],
        'building-363': [chimney],
        'building-355': [stile],
        'building-356': [barrel],
        'building-364': [core],
    }


def shingle_cottage():
    # Ridge 343 (353/352 tops), back eave 299, front eave 284; 354 is the
    # east verge overhang. Walls stand on the native eave footprint.
    r0, r1 = W(1488, 1676.5, 343), W(1635, 1626.5, 343)
    b0, b1 = W(1454, 1643, 299), W(1601, 1594, 299)
    f0, f1 = W(1529, 1715, 284), W(1675, 1666, 284)
    back_roof, back_body, front_roof, front_body = gable_house(
        r0, r1, b0, b1, f0, f1, eave_out=5.0, gable_out=4.0, thickness=4.0)
    # East verge 354 (x 1634..1687): a roof extension carried past the wall,
    # 272..343 in the obstacle; model as the continuation of the front slope.
    front_plane = Plane(r0, r1, f1)
    e_r0, e_r1 = r1, W(1647, 1622, 343)
    e_f0, e_f1 = f1, W(1687, 1661, 284)
    verge = slab([e_r0, extend(e_r1, e_r0, 3.0), extend(extend(e_f1, e_r1, 5.0), e_f0, 3.0), extend(e_f0, e_r0, 5.0)], 4.0)
    chimney = prism(xy(W(1623, 1646, 0), W(1638, 1640.5, 0), W(1644.5, 1647, 0), W(1629, 1652, 0)),
                    const(310), const(357))
    # Fence 357: the obstacle is only the picket gate at the house corner, but
    # its reviewed mask 120 draws the whole rail fence running east to pixel
    # x ~1840. Posts stand at drawn base pixels (1727,1458), (1785,1440) and
    # (1832,1405) on the plateau (native y = row + 220); rails are measured at
    # their drawn pixel rows.
    fence = [prism(xy(W(1672.5, 1666.5, 0), W(1727, 1677.5, 0), W(1727, 1679, 0), W(1672, 1668, 0)),
                   const(GROUND), const(251))]
    for x, y, top in ((1727, 1678, 290), (1785, 1660, 265), (1832, 1625, 255)):
        base = W(x, y, GROUND)
        fence.append(box_between(base, W(x, y, top), 3.0, 3.0))
    for (xa, ya, za), (xb, yb, zb) in (((1728, 1677.7, 263.5), (1785, 1660, 260)),
                                       ((1728, 1677.7, 241.5), (1785, 1660, 240)),
                                       ((1785, 1660, 261), (1832, 1625, 251.5)),
                                       ((1785, 1660, 241), (1832, 1625, 234.5))):
        fence.append(box_between(W(xa, ya, za), W(xb, yb, zb), 2.5, 2.5))
    return {
        'building-353': [back_roof, back_body],
        'building-352': [front_roof, front_body],
        'building-354': [verge],
        'building-362': [chimney],
        'building-357': fence,
    }


def trough():
    # Timber trough 358 standing on the plateau, 220..229.
    corners = [W(1793, 1664, 0), W(1841.5, 1637, 0), W(1856, 1646, 0), W(1808, 1672.5, 0)]
    plan = xy(*corners)
    return {'building-358': [prism(plan, const(GROUND), const(229))]}


def hay_cart():
    # Bed 359 and side rails 360/361 keep their authored tilt (the cart rests
    # tipped on its shafts); add the two wheels to the bed so it meets the
    # plateau. Wheel hubs sit under the rails near native x 1858 / 1890.
    bed_top = [W(1824.5, 1603, 234), W(1859, 1574, 229), W(1920, 1598, 245), W(1885.5, 1627, 250)]
    bed = slab(bed_top, 3.0)
    rail_back = slab([W(1859.5, 1575, 241), W(1862, 1573, 241), W(1918, 1595, 257), W(1916, 1597, 257)], 12.0)
    rail_front = slab([W(1828, 1606, 248), W(1830, 1605, 248), W(1886, 1627, 265), W(1884, 1629, 265)], 12.0)
    # Hay-rack spindles, measured from the tops of mask 111/112 columns:
    # (tip pixel x, tip pixel row, base pixel x on the rail). Spindles lean
    # west toward their tips; each stands in its rail's vertical plane.
    def spindles(rail0, rail1, tips):
        shells = []
        for tip_x, tip_row, base_x in tips:
            t = (base_x - rail0[0]) / (rail1[0] - rail0[0])
            y = rail0[1] + (rail1[1] - rail0[1]) * t
            z = rail0[2] + (rail1[2] - rail0[2]) * t
            shells.append(box_between(W(base_x, y, z - 2), W(tip_x, y, y - tip_row), 2.0, 2.0))
        return shells
    back_spindles = spindles((1861, 1574, 241), (1917, 1596, 257),
                             [(1861, 1308, 1865), (1872, 1310, 1876), (1882, 1309, 1886),
                              (1897, 1314, 1900), (1909.5, 1316, 1913)])
    front_spindles = spindles((1829, 1605.5, 248), (1885, 1628, 265),
                              [(1820, 1336, 1830), (1831, 1339, 1840), (1841, 1338, 1851),
                               (1855.5, 1341, 1864), (1864, 1339, 1875)])
    radius = 17.0 / C  # native wheel height ~34 px in the artwork
    wheel_front = W(1858, 1618, GROUND) + [0, 0, radius]
    along = W(1886, 1627, 0) - W(1828, 1606, 0)
    along /= np.linalg.norm(along)
    axle = np.array([-along[1], along[0], 0.0])  # horizontal, toward the north rail
    if axle[1] < 0:
        axle = -axle
    # The drawn rear wheel shows under the bed's east corner, ~10 units east of
    # a square axle; offset it along the cart axis.
    wheel_back = wheel_front + axle * 62.0 + along * 10.0  # world gap between the two rails
    wheels = [cylinder(w - axle * 1.5, w + axle * 1.5, radius, 16) for w in (wheel_front, wheel_back)]
    # Shaft drawn from the bed's west corner down to the plateau (pixel row
    # ~1361 at x 1806): a resting two-wheeled cart.
    shaft = box_between(W(1830, 1604, 236), W(1806, 1583, GROUND + 1.5), 2.5, 2.5)
    return {'building-359': [bed, shaft] + wheels, 'building-360': [rail_back] + back_spindles,
            'building-361': [rail_front] + front_spindles}


def well():
    # Native diamond 46 x 27 native units is a 46-unit circle in world space;
    # the drawn rim (pixel rows 1574..1614) fits a 44-unit shaft set 5 back.
    centre = W(1743, 1822, GROUND)
    shaft = cylinder(centre, centre + [0, 0, (236 - GROUND) / C], 22.0, 20)
    roof = slab([W(1720.5, 1812, 269), W(1765, 1827, 269), W(1760, 1832, 259), W(1715, 1817, 259)], 3.0)
    # Posts from the shaft rim to the roof, visible at pixels x 1724 and 1760.
    posts = []
    for x, y in ((1724, 1822), (1761, 1832)):
        base = W(x, y, 236)
        roof_z = Plane(W(1720.5, 1812, 269), W(1765, 1827, 269), W(1760, 1832, 259))(base[0], base[1])
        posts.append(box_between(base - [0, 0, 1.0], [base[0], base[1], roof_z - 3.0 / C + 0.5], 3.0, 3.0))
    return {'building-373': [shaft], 'building-374': [roof] + posts}


def mono_shed(back0, back1, front0, front1, *, eave_out, gable_out, thickness, back_out=0.0):
    """Mono-pitch shed: body under a planar roof on the native footprint."""
    plane = Plane(back0, back1, front1)
    quad = [extend(back0, front0, back_out), extend(back1, front1, back_out),
            extend(front1, back1, eave_out), extend(front0, back0, eave_out)]
    along = (np.array(back1) - np.array(back0))
    along /= np.linalg.norm(along)
    quad = [quad[0] - along * gable_out, quad[1] + along * gable_out,
            quad[2] + along * gable_out, quad[3] - along * gable_out]
    roof = slab(quad, thickness)
    body = _ground_body(xy(back0, back1, front1, front0), plane.shifted(-thickness / C))
    return roof, body


def south_wall_cottage():
    # N-S ridge at 338; west eave 272, east eave 266. The south gable runs into
    # the curtain wall; the curtain face occludes all walls in the artwork.
    r0, r1 = W(1590, 1925, 338), W(1613, 1995, 338)
    w0, w1 = W(1507, 1935, 272), W(1530, 2004, 272)
    e0, e1 = W(1668, 1916, 266), W(1692, 1986, 266)
    west_roof, west_body, east_roof, east_body = gable_house(
        r0, r1, w0, w1, e0, e1, eave_out=5.0, gable_out=4.0, thickness=4.0)
    chimney = prism(xy(W(1602, 1935, 0), W(1618, 1933, 0), W(1619, 1939, 0), W(1604, 1941, 0)),
                    const(320), const(344))
    return {'building-365': [west_roof, west_body], 'building-366': [east_roof, east_body],
            'building-367': [chimney]}


def south_wall_lean_to():
    # Mono-pitch rising south to the curtain wall (307 north eave, 339 south).
    roof, body = mono_shed(W(2170, 1832, 339), W(2050, 1847, 339), W(2146, 1767, 307), W(2026, 1782, 307),
                           eave_out=5.0, gable_out=3.0, thickness=4.0)
    return {'building-368': [roof, body]}


def south_wall_thatched_store():
    r0, r1 = W(2209.5, 1730.5, 325), W(2260, 1821.5, 325)
    w0, w1 = W(2156.5, 1740, 300), W(2207, 1830.5, 300)
    e0, e1 = W(2264.5, 1721, 287), W(2315, 1812, 287)
    west_roof, west_body, east_roof, east_body = gable_house(
        r0, r1, w0, w1, e0, e1, eave_out=6.0, gable_out=4.0, thickness=7.0)
    chimney = prism(xy(W(2222, 1731, 0), W(2235, 1729, 0), W(2239.5, 1736, 0), W(2227, 1739, 0)),
                    const(305), const(323))
    return {'building-369': [west_roof, west_body], 'building-370': [east_roof, east_body],
            'building-371': [chimney]}


def southeast_lean_to():
    # Mono-pitch against the east curtain: 308 at the wall, 282 at the west eave.
    roof, body = mono_shed(W(2429, 1683, 308), W(2397, 1725, 308), W(2359, 1666, 282), W(2326, 1707, 282),
                           eave_out=5.0, gable_out=3.0, thickness=4.0)
    return {'building-372': [roof, body]}


def target(west_node, east_node, x_west, x_split, x_east, y_back, y_front, top, front_extra=0.0):
    """Straw archery butt: an ellipsoidal bale split at the native ridge."""
    # For the two eastern butts the drawn bale base (straw spill) sits ~4 px
    # below the obstacle's front edge; extend their plan depth south.
    y_front += front_extra
    yc = (y_back + y_front) / 2
    centre = W(x_split, yc, GROUND)
    ry = (y_front - y_back) / 2 / S
    h = (top - GROUND) / C
    # The drawn bale is ~5 units taller than the obstacle ridge, and
    # its target disc reaches ~4 px west of the obstacle footprint.
    h += 5.0 / C
    west = dome_part(centre, x_split - x_west + 3, ry, h, math.pi / 2, 3 * math.pi / 2, rings=6, segments=8)
    east = dome_part(centre, x_east - x_split - 2, ry, h, -math.pi / 2, math.pi / 2, rings=6, segments=8)
    return {west_node: [west], east_node: [east]}


def gabled_box(pts, z_body, z_ridge):
    """Box on the plateau with a gabled lid whose ridge joins plan corners 0 and 2."""
    c = [W(x, y, 0) for x, y in pts]
    body = prism(xy(*c), const(GROUND), const(z_body))
    lo = [np.array([p[0], p[1], z_body / C]) for p in c]
    hi0 = np.array([c[0][0], c[0][1], z_ridge / C])
    hi2 = np.array([c[2][0], c[2][1], z_ridge / C])
    verts = lo + [hi0, hi2]  # 0..3 eaves, 4 = ridge over corner 0, 5 = over corner 2
    faces = [[3, 2, 1, 0], [4, 1, 5], [4, 5, 3], [0, 1, 4], [1, 2, 5], [2, 3, 5], [3, 0, 4]]
    return body, (verts, faces)


def hutches():
    out = {}
    # Plan diamonds are inflated: the drawn hutch feet sit ~15 px above the
    # obstacle's front corner. Keep the back corner and shorten the depth.
    for node, pts in (('building-168', [(2586, 931), (2600, 918), (2628, 927), (2614, 941)]),
                      ('building-169', [(2537, 921), (2549, 908), (2577, 917), (2565, 930)])):
        back_y = min(p[1] for p in pts)
        pts = [(x, back_y + (y - back_y) * 0.45) for x, y in pts]
        body, lid = gabled_box(pts, 253, 264)
        out[node] = [body, lid]
    return out


def northeast_props():
    # 178: barrel lying on its side, axis along the native footprint's long edge.
    a, b = W(2752, 1031.5, GROUND), W(2780, 1036.5, GROUND)
    r = 9.5
    barrel = cylinder(a + [0, 0, r], b + [0, 0, r], r, 16)
    # 179: reject-all block (no unambiguous source mask); kept as a small
    # plateau-standing block at its authored plan and height.
    block = prism(xy(W(2711, 988, 0), W(2730, 987, 0), W(2731, 993, 0), W(2711, 993, 0)), const(GROUND), const(233))
    return {'building-178': [barrel], 'building-179': [block]}


def courtyard_shed():
    # Mono-pitch shingle roof 188: back edge 358 against the castle rock, front
    # eave 303. The slab keeps the native top surface with 5 units thickness.
    back0, back1 = W(1723, 1519, 358), W(1944, 1472, 358)
    front0, front1 = W(1746, 1555, 303), W(1967, 1508, 303)
    roof_plane = Plane(back0, back1, front1)
    t = 5.0 / C
    under = roof_plane.shifted(-t)
    along = (back1 - back0) / np.linalg.norm(back1 - back0)
    roof = slab([back0 - along * 1.0, back1 + along * 1.0, front1 + along * 1.0, front0 - along * 1.0], 5.0)
    # Back wall 195 (4 native deep) from the plateau to the roof underside.
    back_wall = _ground_body(xy(W(1723, 1515, 0), W(1942, 1469, 0), W(1944, 1473, 0), W(1725, 1519, 0)), under)
    # End walls 194 (west) and 193 (east) under the roof slope.
    west_wall = _ground_body(xy(W(1722, 1516, 0), W(1725, 1515, 0), W(1750, 1555.5, 0), W(1747, 1556, 0)), under)
    # 193 is a 6-unit strip under the roof's east edge whose top follows the
    # roof slope (358 -> 302): the east verge (barge) board, not a wall. The
    # privy 196 closes the back of the east end; a corner post carries the eave.
    verge_top = roof_plane.shifted(0.5 / C)
    east_verge = prism(xy(W(1936, 1471, 0), W(1942, 1469, 0), W(1968, 1510.5, 0), W(1962, 1512, 0)),
                       verge_top.shifted(-12.0 / C), verge_top)
    # Knee walls 191/192 at the open front (native top 276).
    knee_east = prism(xy(W(1820, 1538, 0), W(1855, 1531, 0), W(1857, 1534, 0), W(1822, 1541, 0)),
                      const(GROUND), const(276))
    knee_west = prism(xy(W(1745, 1554, 0), W(1768, 1549, 0), W(1770, 1552, 0), W(1747, 1556, 0)),
                      const(GROUND), const(276))
    # Front eave posts carrying the open front (visible at pixel x ~1897 and
    # at the ladder bay ~1812); added to the roof node as separate shells.
    # The timber header with small white windows hangs below the eave along
    # the open front down to the lintel (pixel row ~1262 at x 1850, native z
    # ~271-276); the knee walls reach the same lintel height.
    header = _ground_body(xy(W(1747, 1553.5, 0), W(1962, 1507.5, 0), W(1962, 1510.5, 0), W(1747, 1556.5, 0)), under)
    hv, hf = header
    lintel = 276.0 / C
    hv = [np.array([p[0], p[1], lintel]) if k < len(hv) // 2 else p for k, p in enumerate(hv)]
    header = (hv, hf)
    posts = []
    for x in (1812.0, 1897.0, 1962.0):
        f = (x - 1746) / (1967 - 1746)
        base = lerp(W(1746, 1553, GROUND), W(1967, 1506, GROUND), f)
        posts.append(box_between(base, [base[0], base[1], lintel], 4.0, 4.0))
    # Ladder 224 leaning from the plateau to the eave (native 302 at the back).
    ladder_top = [W(1833, 1536, 302), W(1845, 1533, 302), W(1856, 1547, GROUND + 1), W(1843, 1550, GROUND + 1)]
    ladder = slab(ladder_top, 4.0)
    # Clip the ladder slab bottom to the plateau.
    lv, lf = ladder
    lv = [np.array([p[0], p[1], max(p[2], GROUND / C)]) for p in lv]
    ladder = (lv, lf)
    # East privy/lean-to 196: mono-pitch 287 -> 268 over its native footprint.
    pr, pb = mono_shed(W(1943, 1468, 287), W(1987, 1460, 287), W(1957, 1493, 268), W(2001, 1485, 268),
                       eave_out=0.0, gable_out=0.0, thickness=4.0)
    # Barrel 220.
    c = W(1967.5, 1495.5, GROUND)
    barrel = cylinder(c, c + [0, 0, (243 - GROUND) / C], 8.5, 14)
    # 072: reject-all strip with top exactly at the plateau (0..220). It is
    # datum/collision geometry with no source-visible surface; keep it as a
    # thin concealed slab just below the plateau top.
    strip = prism(xy(W(1754, 1430, 0), W(1768, 1426, 0), W(1848, 1536, 0), W(1834, 1539, 0)),
                  const(GROUND - 2.5), const(GROUND - 0.5))
    return {
        'building-188': [roof, header] + posts,
        'building-195': [back_wall],
        'building-194': [west_wall],
        'building-193': [east_verge],
        'building-191': [knee_east],
        'building-192': [knee_west],
        'building-224': [ladder],
        'building-196': [pr, pb],
        'building-220': [barrel],
        'building-072': [strip],
    }


BUILDERS = {
    'lincoln-courtyard-shed': courtyard_shed,
    'lincoln-bailey-thatched-cottage': thatched_cottage,
    'lincoln-bailey-shingle-cottage': shingle_cottage,
    'lincoln-bailey-trough': trough,
    'lincoln-bailey-hay-cart': hay_cart,
    'lincoln-bailey-well': well,
    'lincoln-south-wall-cottage': south_wall_cottage,
    'lincoln-south-wall-lean-to': south_wall_lean_to,
    'lincoln-south-wall-thatched-store': south_wall_thatched_store,
    'lincoln-southeast-lean-to': southeast_lean_to,
    'lincoln-archery-target-west': lambda: target('building-177', 'building-176', 2100, 2115, 2137, 1147.5, 1160.5, 247),
    'lincoln-archery-target-west-middle': lambda: target('building-175', 'building-174', 2192, 2212, 2233, 1145, 1161.5, 243),
    'lincoln-archery-target-east-middle': lambda: target('building-173', 'building-172', 2290, 2309.5, 2328, 1152.5, 1168.5, 243, 4.0),
    'lincoln-archery-target-east': lambda: target('building-171', 'building-170', 2365, 2382.5, 2402, 1172.5, 1184.5, 247, 4.0),
    'lincoln-northeast-yard-hutches': hutches,
    'lincoln-northeast-yard-props': northeast_props,
}


def build(asset_id):
    return BUILDERS[asset_id]()
