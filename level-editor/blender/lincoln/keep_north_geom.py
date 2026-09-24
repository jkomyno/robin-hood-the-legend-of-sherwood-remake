"""Closed-shell construction helpers for the Lincoln keep_north refinement lane.

All specifications use native map coordinates (x, y, z): the source camera
projects a native point to pixel (x, y - z).  Blender world coordinates are
X = x, Y = -y / sin(35 deg), Z = z / cos(35 deg).  A true horizontal circle of
world radius R therefore has a native footprint whose y semi-axis is R*sin(35).

Every primitive emits a closed shell.  Cells that share a boundary share exact
vertices; coincident internal faces are cancelled, so stacked or adjacent cells
built through one ``Shell`` merge into a single manifold volume.
"""
import math

SIN = math.sin(math.radians(35))
COS = math.cos(math.radians(35))
GROUND = 220.0  # native plateau top shared by the keep plateau and both baileys


def world(p):
    x, y, z = p
    return (x, -y / SIN, z / COS)


def circ(cx, cy, r, theta_deg, z):
    """Native point on a true (world) circle; theta 90 faces the camera (south)."""
    t = math.radians(theta_deg)
    return (cx + r * math.cos(t), cy + r * SIN * math.sin(t), z)


class Shell:
    """Accumulates faces of one closed volume, cancelling shared internal faces."""

    def __init__(self):
        self.faces = {}

    def face(self, points):
        pts = [tuple(round(float(c), 5) for c in p) for p in points]
        pts = [p for i, p in enumerate(pts) if p != pts[i - 1]]
        if len(set(pts)) < 3:
            return
        key = tuple(sorted(pts))
        if key in self.faces:
            del self.faces[key]
        else:
            self.faces[key] = pts

    def cell(self, bottom, top):
        """Prism between two rings with equal point counts (native coordinates)."""
        n = len(bottom)
        self.face(list(reversed(bottom)))
        self.face(list(top))
        for i in range(n):
            j = (i + 1) % n
            self.face([bottom[i], bottom[j], top[j], top[i]])


class Mesh:
    """Several closed shells destined for one Blender mesh (one source node)."""

    def __init__(self):
        self.shells = []

    def new(self):
        s = Shell()
        self.shells.append(s)
        return s

    def data(self):
        verts, index, faces = [], {}, []
        for shell in self.shells:
            for pts in shell.faces.values():
                ids = []
                for p in pts:
                    w = world(p)
                    k = (shell_id(shell, self), tuple(round(c, 5) for c in w))
                    if k not in index:
                        index[k] = len(verts)
                        verts.append(w)
                    ids.append(index[k])
                faces.append(ids)
        return verts, faces


def shell_id(shell, mesh):
    return mesh.shells.index(shell)


# ---------------------------------------------------------------- primitives

def prism(mesh, poly, z0, z1):
    """Vertical prism over a native polygon; z1 may be a per-vertex list."""
    s = mesh.new()
    tops = z1 if isinstance(z1, (list, tuple)) else [z1] * len(poly)
    bots = z0 if isinstance(z0, (list, tuple)) else [z0] * len(poly)
    s.cell([(x, y, b) for (x, y), b in zip(poly, bots)],
           [(x, y, t) for (x, y), t in zip(poly, tops)])
    return s


def cylinder(mesh, cx, cy, r, z0, z1, n=48, start=0.0, end=360.0):
    """Closed cylinder (or closed sector wedge when the span is below 360)."""
    s = mesh.new()
    full = abs(end - start) >= 360 - 1e-6
    count = n if full else max(2, int(round(n * abs(end - start) / 360)))
    angles = [start + (end - start) * i / count for i in range(count if full else count + 1)]
    ring = [circ(cx, cy, r, a, 0)[:2] for a in angles]
    if not full:
        ring = [(cx, cy)] + ring
    s.cell([(x, y, z0) for x, y in ring], [(x, y, z1) for x, y in ring])
    return s


def annular_cells(cx, cy, r_out, r_in, angles):
    """Quad footprints of an annulus between consecutive angles."""
    cells = []
    for a, b in zip(angles, angles[1:]):
        cells.append([circ(cx, cy, r_out, a, 0)[:2], circ(cx, cy, r_out, b, 0)[:2],
                      circ(cx, cy, r_in, b, 0)[:2], circ(cx, cy, r_in, a, 0)[:2]])
    return cells


def crenellated_ring(mesh, cx, cy, r_out, r_in, z0, z_notch, z_top, merlons,
                     phase_deg, merlon_deg, n_per=4):
    """One closed annular parapet with ``merlons`` evenly spaced raised blocks.

    ``phase_deg`` is the centre angle of one merlon; ``merlon_deg`` its span.
    """
    s = mesh.new()
    pitch = 360.0 / merlons
    angles, raised = [], []
    for k in range(merlons):
        a0 = phase_deg + k * pitch - merlon_deg / 2
        a1 = a0 + merlon_deg
        a2 = a0 + pitch
        for i in range(n_per):
            angles.append(a0 + (a1 - a0) * i / n_per)
            raised.append(True)
        for i in range(n_per):
            angles.append(a1 + (a2 - a1) * i / n_per)
            raised.append(False)
    angles.append(angles[0] + 360.0)
    cells = annular_cells(cx, cy, r_out, r_in, angles)
    for quad, up in zip(cells, raised):
        s.cell([(x, y, z0) for x, y in quad], [(x, y, z_notch) for x, y in quad])
        if up:
            s.cell([(x, y, z_notch) for x, y in quad], [(x, y, z_top) for x, y in quad])
    return s


def ring(mesh, cx, cy, r_out, r_in, z0, z1, n=64):
    s = mesh.new()
    angles = [360.0 * i / n for i in range(n + 1)]
    for quad in annular_cells(cx, cy, r_out, r_in, angles):
        s.cell([(x, y, z0) for x, y in quad], [(x, y, z1) for x, y in quad])
    return s


def cone(mesh, cx, cy, r, z0, z_apex, n=48, start=0.0, end=360.0):
    """Closed cone, or a closed half/sector cone with flat cut faces."""
    s = mesh.new()
    full = abs(end - start) >= 360 - 1e-6
    count = n if full else max(2, int(round(n * abs(end - start) / 360)))
    angles = [start + (end - start) * i / count for i in range(count if full else count + 1)]
    base = [circ(cx, cy, r, a, z0) for a in angles]
    apex = (cx, cy, z_apex)
    centre = (cx, cy, z0)
    if full:
        s.face(list(reversed(base)))
        for i in range(len(base)):
            s.face([base[i], base[(i + 1) % len(base)], apex])
    else:
        s.face(list(reversed([centre] + base)))
        for i in range(len(base) - 1):
            s.face([base[i], base[i + 1], apex])
        s.face([centre, base[0], apex])
        s.face([base[-1], centre, apex])
    return s


def frustum(mesh, cx, cy, r0, r1, z0, z1, n=48):
    s = mesh.new()
    angles = [360.0 * i / n for i in range(n)]
    s.cell([circ(cx, cy, r0, a, z0) for a in angles], [circ(cx, cy, r1, a, z1) for a in angles])
    return s


def _offset_polyline(path, d):
    """Offset a native polyline sideways by d world units (left of travel in world XY)."""
    wpts = [(x, -y / SIN) for x, y in path]
    out = []
    for i, (x, y) in enumerate(wpts):
        normals = []
        for a, b in ((wpts[i - 1], wpts[i]) if i > 0 else (None, None),
                     (wpts[i], wpts[i + 1]) if i + 1 < len(wpts) else (None, None)):
            if a is None:
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy)
            normals.append((-dy / L, dx / L))
        nx = sum(n[0] for n in normals)
        ny = sum(n[1] for n in normals)
        L = math.hypot(nx, ny)
        nx, ny = nx / L, ny / L
        if len(normals) == 2:
            cosh = normals[0][0] * nx + normals[0][1] * ny
            scale = 1.0 / max(cosh, 0.3)
        else:
            scale = 1.0
        out.append((x + nx * d * scale, -(y + ny * d * scale) * SIN))
    return out


def crenellated_wall(mesh, path, thickness, z0, z_notch, z_top, notches_px,
                     outer_side=1, z_top_path=None):
    """Closed wall along a native polyline with measured notches.

    ``notches_px`` lists (x_left, x_right) source-pixel column spans of the
    notches.  Cuts are placed where the wall centre-line crosses those columns.
    ``outer_side`` +1 keeps the path as one face and offsets the other face to
    the left (world); -1 offsets to the right.  z0/z_notch/z_top may be callables
    of the native x position for sloped runs.
    """
    other = _offset_polyline(path, thickness * outer_side)
    s = mesh.new()
    zf = lambda v, x: v(x) if callable(v) else v
    # parameter cuts along each segment
    for (a, b), (c, d) in zip(zip(path, path[1:]), zip(other, other[1:])):
        ts = {0.0, 1.0}
        for lo, hi in notches_px:
            for xv in (lo, hi):
                if abs(b[0] - a[0]) > 1e-6:
                    t = (xv - a[0]) / (b[0] - a[0])
                    if 1e-4 < t < 1 - 1e-4:
                        ts.add(t)
        ts = sorted(ts)
        lerp = lambda p, q, t: (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
        for t0, t1 in zip(ts, ts[1:]):
            p0, p1 = lerp(a, b, t0), lerp(a, b, t1)
            q0, q1 = lerp(c, d, t0), lerp(c, d, t1)
            quad = [p0, p1, q1, q0]
            xm = (p0[0] + p1[0]) / 2
            lo_z = [zf(z0, p[0]) for p in quad]
            mid = [zf(z_notch, p[0]) for p in quad]
            top = [zf(z_top, p[0]) for p in quad]
            s.cell([(p[0], p[1], z) for p, z in zip(quad, lo_z)],
                   [(p[0], p[1], z) for p, z in zip(quad, mid)])
            if not any(l < xm < r for l, r in notches_px):
                s.cell([(p[0], p[1], z) for p, z in zip(quad, mid)],
                       [(p[0], p[1], z) for p, z in zip(quad, top)])
    return s


def _pixel(path, zproj):
    return [(x, y - zproj) for x, y in path]


def _locate(pix, target):
    """Arc position (segment index, t) of the pixel-polyline point nearest target."""
    best = None
    for i, (a, b) in enumerate(zip(pix, pix[1:])):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy or 1e-9
        t = max(0.0, min(1.0, ((target[0] - a[0]) * dx + (target[1] - a[1]) * dy) / L2))
        px, py = a[0] + dx * t, a[1] + dy * t
        d = (px - target[0]) ** 2 + (py - target[1]) ** 2
        if best is None or d < best[0]:
            best = (d, i, t)
    return best[1] + best[2]


def _column(pix, x, near=None):
    """Arc positions where the pixel polyline crosses column x (nearest to ``near``)."""
    lo, hi = min(p[0] for p in pix), max(p[0] for p in pix)
    x = min(max(x, lo + 1e-6), hi - 1e-6)  # spans reaching past a run end stop at it
    hits = []
    for i, (a, b) in enumerate(zip(pix, pix[1:])):
        if (a[0] - x) * (b[0] - x) <= 0 and a[0] != b[0]:
            hits.append(i + (x - a[0]) / (b[0] - a[0]))
    if not hits:
        raise ValueError(f'column {x} misses the path')
    return min(hits, key=lambda h: abs(h - near)) if near is not None else hits[0]


def _sub(path, s0, s1):
    if s1 < s0:
        s0, s1 = s1, s0
    def at(s):
        i = min(int(s), len(path) - 2)
        t = s - i
        a, b = path[i], path[i + 1]
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    pts = [at(s0)] + [path[i] for i in range(int(s0) + 1, int(s1) + 1) if s0 < i < s1] + [at(s1)]
    return pts


def path_blocks(mesh, path, thickness, inside, spans, z0, z1, zproj):
    """Merlon blocks on a native polyline face from measured source corners.

    Each span is (x_left, x_right) source columns, (x_left, x_right, y) when a
    column crosses the path more than once, or (x1, y1, x2, y2) corner pixels.  Corners are located on the path
    projected at ``zproj``; blocks extend ``thickness`` world units toward the
    native point ``inside``.
    """
    pix = _pixel(path, zproj)
    placed = []
    for span in spans:
        if len(span) == 4:
            a = _locate(pix, (span[0], span[1]))
            b = _locate(pix, (span[2], span[3]))
        elif len(span) == 3:
            a = _locate(pix, (span[0], span[2]))
            b = _locate(pix, (span[1], span[2]))
        else:
            a = _column(pix, span[0])
            b = _column(pix, span[1], near=a)
        sub = _sub(path, a, b)
        cands = [_offset_polyline(sub, thickness), _offset_polyline(sub, -thickness)]
        mid = lambda pts: (sum(p[0] for p in pts) / len(pts), sum(p[1] / SIN for p in pts) / len(pts))
        ins = (inside[0], inside[1] / SIN)
        other = min(cands, key=lambda c: (mid(c)[0] - ins[0]) ** 2 + (mid(c)[1] - ins[1]) ** 2)
        poly = sub + list(reversed(other))
        prism(mesh, poly, z0, z1)
        placed.append({'span': list(span), 'arc': [round(a, 4), round(b, 4)],
                       'native_face': [[round(v, 2) for v in sub[0]], [round(v, 2) for v in sub[-1]]]})
    return placed


def stair(mesh, top_a, top_b, bot_a, bot_b, z_top, z_bottom, steps, ground):
    """Closed stepped solid descending from edge top_a-top_b to bot_a-bot_b."""
    s = mesh.new()
    rise = (z_top - z_bottom) / steps
    prof = [(0.0, ground), (0.0, z_top)]
    for k in range(steps):
        t = (k + 1) / steps
        prof.append((t, z_top - rise * k))
        prof.append((t, z_top - rise * (k + 1)) if k + 1 < steps else (t, z_bottom))
    prof.append((1.0, ground))
    # remove duplicate trailing point if z_bottom == ground
    clean = []
    for p in prof:
        if not clean or p != clean[-1]:
            clean.append(p)
    prof = clean
    side = []
    for a, b in ((top_a, bot_a), (top_b, bot_b)):
        side.append([(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, z) for t, z in prof])
    n = len(prof)
    s.face(list(reversed(side[0])))
    s.face(side[1])
    for i in range(n):
        j = (i + 1) % n
        s.face([side[0][i], side[0][j], side[1][j], side[1][i]])
    return s


# ------------------------------------------------------------ Blender binding

def replace_mesh(obj, mesh_spec, material=None):
    """Replace obj.data with the spec (world coordinates); keep transform/props."""
    import bpy
    import bmesh
    from mathutils import Vector
    verts, faces = mesh_spec.data()
    inverse = obj.matrix_world.inverted()
    before = [list(r) for r in obj.matrix_world]
    stale = bpy.data.meshes.get(obj.name + ' / refined')
    if stale is not None and stale is not obj.data and stale.users == 0:
        bpy.data.meshes.remove(stale)
    new = bpy.data.meshes.new(obj.name + ' / refined')
    new.from_pydata([inverse @ Vector(v) for v in verts], [], faces)
    new.validate()
    bm = bmesh.new()
    bm.from_mesh(new)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    open_edges = sum(1 for e in bm.edges if not e.is_manifold)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-6)
    bm.to_mesh(new)
    bm.free()
    old = obj.data
    mats = [m for m in old.materials if m is not None and 'projection' not in m.name
            and 'owned' not in m.name]
    if material is not None:
        mats = [material]
    for m in mats[:1]:
        new.materials.append(m)
    uv = new.uv_layers.new(name='UVMap')
    # Fallback atlas UVs use the same source-camera projection as the map atlas.
    for loop in new.loops:
        w = verts[loop.vertex_index]
        uv.data[loop.index].uv = (w[0] / 2944.0, 1.0 + (w[1] * SIN + w[2] * COS) / 2176.0)
    obj.data = new
    if old.users == 0:
        bpy.data.meshes.remove(old)
    for m in list(obj.modifiers):
        obj.modifiers.remove(m)
    if [list(r) for r in obj.matrix_world] != before:
        raise ValueError('World transform changed for ' + obj.name)
    obj['source_projection_current'] = False
    return {'object': obj.name, 'vertices': len(new.vertices), 'faces': len(new.polygons),
            'shells': len(mesh_spec.shells), 'nonmanifold_edges': open_edges,
            'degenerate_faces': degenerate}
