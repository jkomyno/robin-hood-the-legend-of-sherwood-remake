"""Geometry helpers for the Lincoln ``east_gate_walls`` refinement lane.

All construction happens in *native* map units: ground coordinates ``(x, y)``
and height ``z``, where the source camera maps a point to pixel ``(x, y - z)``.
Blender world coordinates are ``X = x, Y = -y / sin35, Z = z / cos35``, so a
circle in the world ground plane is an ellipse with semi-axes ``(r, r*sin35)``
in native ``(x, y)``.

The builders produce closed shells from explicit cells.  Coincident faces of
adjacent cells cancel, which keeps crenellated rings and walls as one
connected manifold body instead of detached merlon boxes.
"""
import math

S = math.sin(math.radians(35))
C = math.cos(math.radians(35))


def to_world(p):
    x, y, z = p
    return (x, -y / S, z / C)


def to_native(v):
    return (v[0], -v[1] * S, v[2] * C)


def pixel(p):
    """Source pixel of a native point."""
    return (p[0], p[1] - p[2])


def ellipse_point(cx, cy, r, phi):
    """Native ground point on a world circle of radius ``r``.

    ``phi`` is measured in the world ground plane; ``sin(phi) > 0`` is the
    near (viewer-facing, larger native y) side.
    """
    return (cx + r * math.cos(phi), cy + r * S * math.sin(phi))


def lerp2(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


class Shell:
    """Vertex-welded polygon soup; ``cancel`` removes coincident face pairs."""

    def __init__(self, digits=4, weld=0.0):
        self.verts = []
        self.index = {}
        self.faces = []
        self.digits = digits
        self.weld = weld

    def v(self, p):
        key = tuple(round(float(c), self.digits) for c in p)
        if key not in self.index:
            if self.weld:
                for i, q in enumerate(self.verts):
                    if max(abs(a - b) for a, b in zip(q, key)) <= self.weld:
                        self.index[key] = i
                        return i
            self.index[key] = len(self.verts)
            self.verts.append(key)
        return self.index[key]

    def face(self, pts):
        ids = [self.v(p) for p in pts]
        ids = [v for i, v in enumerate(ids) if v != ids[i - 1]]
        if len(set(ids)) >= 3:
            self.faces.append(ids)

    def hexa(self, a0, a1, b0, b1, z0, z1):
        """Cell spanning ground quad a0-a1 (station A) to b0-b1 (station B)."""
        if isinstance(z0, (int, float)):
            z0 = (z0, z0, z0, z0)
        if isinstance(z1, (int, float)):
            z1 = (z1, z1, z1, z1)
        q = [a0, a1, b1, b0]
        lo = [(p[0], p[1], z) for p, z in zip(q, z0)]
        hi = [(p[0], p[1], z) for p, z in zip(q, z1)]
        self.face(list(reversed(lo)))
        self.face(hi)
        for i in range(4):
            j = (i + 1) % 4
            self.face([lo[i], lo[j], hi[j], hi[i]])

    def prism(self, poly, z0, z1):
        """Closed vertical prism over a native ground polygon.

        ``z0``/``z1`` may be scalars or per-vertex sequences (sloped caps).
        """
        n = len(poly)
        z0 = [z0] * n if isinstance(z0, (int, float)) else list(z0)
        z1 = [z1] * n if isinstance(z1, (int, float)) else list(z1)
        lo = [(p[0], p[1], z) for p, z in zip(poly, z0)]
        hi = [(p[0], p[1], z) for p, z in zip(poly, z1)]
        self.face(list(reversed(lo)))
        self.face(hi)
        for i in range(n):
            j = (i + 1) % n
            self.face([lo[i], lo[j], hi[j], hi[i]])

    def cancel(self):
        unique = {}
        for f in self.faces:
            key = tuple(sorted(f))
            if key in unique:
                del unique[key]
            else:
                unique[key] = f
        self.faces = list(unique.values())
        return self

    def merge(self, other):
        for f in other.faces:
            self.face([other.verts[i] for i in f])
        return self


def crenel_strip(stations, spans, closed=False):
    """Crenellated strip built from ground stations.

    ``stations`` is a list of ``(outer, inner)`` native ground points.
    ``spans[i]`` lists the ``(z0, z1)`` intervals of the cell between station
    ``i`` and ``i + 1`` (closed strips wrap).  A notch cell has one interval up
    to the crenel floor, a merlon cell a second interval up to the cap.
    """
    shell = Shell()
    count = len(stations) if closed else len(stations) - 1
    if len(spans) != count:
        raise ValueError(f'Expected {count} span lists, got {len(spans)}')
    for i in range(count):
        (ao, ai), (bo, bi) = stations[i], stations[(i + 1) % len(stations)]
        for z0, z1 in spans[i]:
            shell.hexa(ao, ai, bo, bi, z0, z1)
    return shell.cancel()


def ring_cuts(merlons, extra=(), step_deg=6.0):
    """Sorted angle cuts (radians) for a ring: merlon edges plus a fine grid."""
    cuts = set()
    for a, b in merlons:
        cuts.add(round(a % (2 * math.pi), 9))
        cuts.add(round(b % (2 * math.pi), 9))
    for e in extra:
        cuts.add(round(e % (2 * math.pi), 9))
    step = math.radians(step_deg)
    ordered = sorted(cuts)
    result = []
    for k, a in enumerate(ordered):
        b = ordered[(k + 1) % len(ordered)] + (2 * math.pi if k + 1 == len(ordered) else 0)
        n = max(1, math.ceil((b - a) / step - 1e-9))
        result.extend(a + (b - a) * i / n for i in range(n))
    return result


def in_intervals(a, intervals):
    two = 2 * math.pi
    for lo, hi in intervals:
        lo %= two
        hi = lo + ((hi - lo) % two)
        x = a % two
        if lo <= x <= hi or lo <= x + two <= hi:
            return True
    return False


def crenellated_ring(cx, cy, r_out, r_in, z_base, z_floor, z_top, merlons, step_deg=6.0):
    """Closed round parapet; ``merlons`` are world-angle intervals (radians)."""
    cuts = ring_cuts(merlons, step_deg=step_deg)
    stations = [(ellipse_point(cx, cy, r_out, a), ellipse_point(cx, cy, r_in, a)) for a in cuts]
    spans = []
    for k, a in enumerate(cuts):
        b = cuts[(k + 1) % len(cuts)] + (2 * math.pi if k + 1 == len(cuts) else 0)
        mid = (a + b) / 2
        cell = [(z_base, z_floor)]
        if in_intervals(mid, merlons):
            cell.append((z_floor, z_top))
        spans.append(cell)
    return crenel_strip(stations, spans, closed=True)


def cylinder(shell, cx, cy, r, z0, z1, segments=48, phase=0.0):
    poly = [ellipse_point(cx, cy, r, phase + 2 * math.pi * i / segments) for i in range(segments)]
    shell.prism(poly, z0, z1)
    return shell


def stepped_cylinder(cx, cy, levels, segments=48):
    """Coaxial stack ``[(r, z0, z1), ...]`` fused into one closed shell."""
    shell = Shell()
    for r, z0, z1 in levels:
        cylinder(shell, cx, cy, r, z0, z1, segments)
    return shell.cancel()


def merlon_intervals(phase_deg, period_deg, width_deg, count):
    """World-angle merlon intervals centred at ``phase + k * period``."""
    out = []
    for k in range(count):
        c = math.radians(phase_deg + k * period_deg)
        h = math.radians(width_deg) / 2
        out.append((c - h, c + h))
    return out


def wall_run_param(a, b, px):
    """Parameter along native ground segment a->b whose x equals pixel x."""
    return (px - a[0]) / (b[0] - a[0])


def crenellated_wall(outer, inner, z_base, z_floor, z_top, notches, extra_cuts=()):
    """Straight crenellated parapet between ground lines.

    ``outer``/``inner`` are ``(start, end)`` native ground points.  ``notches``
    are parameter intervals ``(t0, t1)`` along the run; ``z_*`` may be scalars
    or ``(start, end)`` pairs interpolated along the run.
    """
    def zat(z, t):
        return z[0] + (z[1] - z[0]) * t if isinstance(z, tuple) else z
    cuts = {0.0, 1.0}
    for t0, t1 in notches:
        for t in (t0, t1):
            if 0 < t < 1:
                cuts.add(round(t, 9))
    cuts.update(t for t in extra_cuts if 0 < t < 1)
    cuts = sorted(cuts)
    shell = Shell()
    for t0, t1 in zip(cuts, cuts[1:]):
        mid = (t0 + t1) / 2
        a0, a1 = lerp2(outer[0], outer[1], t0), lerp2(inner[0], inner[1], t0)
        b0, b1 = lerp2(outer[0], outer[1], t1), lerp2(inner[0], inner[1], t1)
        base = (zat(z_base, t0), zat(z_base, t0), zat(z_base, t1), zat(z_base, t1))
        floor = (zat(z_floor, t0), zat(z_floor, t0), zat(z_floor, t1), zat(z_floor, t1))
        top = (zat(z_top, t0), zat(z_top, t0), zat(z_top, t1), zat(z_top, t1))
        shell.hexa(a0, a1, b0, b1, base, floor)
        if not any(lo < mid < hi for lo, hi in notches):
            shell.hexa(a0, a1, b0, b1, floor, top)
    return shell.cancel()


def extrude_profile(profile, origin, u, w, depth):
    """Extrude a closed (s, z) profile.

    Ground point = ``origin + s * u + d * w`` for ``d`` in ``depth`` (d0, d1).
    """
    shell = Shell()
    d0, d1 = depth
    def g(s, d):
        return (origin[0] + s * u[0] + d * w[0], origin[1] + s * u[1] + d * w[1])
    a = [(*g(s, d0), z) for s, z in profile]
    b = [(*g(s, d1), z) for s, z in profile]
    n = len(profile)
    shell.face(list(reversed(a)))
    shell.face(b)
    for i in range(n):
        j = (i + 1) % n
        shell.face([a[i], a[j], b[j], b[i]])
    return shell


def arch_profile(s0, s1, z_floor, z_spring, z_crown, segments=12):
    """Opening outline (floor-left, up, arch, down) for a round-headed arch.

    The arch is circular in the wall plane; ``z_crown - z_spring`` is its native
    rise.  Returns points from (s0, z_floor) counter-clockwise over the top.
    """
    pts = [(s0, z_floor), (s0, z_spring)]
    for i in range(1, segments):
        a = math.pi * (1 - i / segments)
        pts.append(((s0 + s1) / 2 + (s1 - s0) / 2 * math.cos(a),
                    z_spring + (z_crown - z_spring) * math.sin(a)))
    pts += [(s1, z_spring), (s1, z_floor)]
    return pts


# --- Blender side -----------------------------------------------------------

def load_baseline_native(baseline_path, matrices):
    """Native vertices/faces of named objects in an immutable baseline file.

    ``matrices`` maps object name -> world matrix of the (untransformed)
    working object; appended objects lose their parent, so their stored
    matrix cannot be trusted.
    """
    object_names = list(matrices)
    import bpy
    with bpy.data.libraries.load(str(baseline_path), link=False) as (src, dst):
        missing = [n for n in object_names if n not in src.objects]
        if missing:
            raise ValueError(f'Baseline lacks objects: {missing}')
        dst.objects = list(object_names)
    out = {}
    try:
        for name, obj in zip(object_names, dst.objects):
            m = matrices[name]
            verts = [to_native(tuple(m @ v.co)) for v in obj.data.vertices]
            out[name] = {'verts': verts, 'faces': [list(p.vertices) for p in obj.data.polygons],
                         'matrix_world': [list(r) for r in m]}
    finally:
        for obj in dst.objects:
            mesh = obj.data
            bpy.data.objects.remove(obj)
            if mesh and mesh.users == 0:
                bpy.data.meshes.remove(mesh)
    return out


def native_top_prism(data, ground, eps=1.0):
    """Rebuild a native z=0 pillar as a closed solid standing on ``ground``.

    Faces are welded, every vertex below ``ground(x, y)`` is lifted to it and
    the open datum boundary is capped.  Vertices above ``eps`` keep their
    authored height, so sloped or stepped caps are preserved.
    """
    shell = Shell(digits=3, weld=0.35)
    verts = []
    for x, y, z in data['verts']:
        g = ground(x, y) if callable(ground) else ground
        verts.append((x, y, g if z < eps else max(z, g)))
    for f in data['faces']:
        shell.face([verts[i] for i in f])
    shell.cancel()
    return shell


def replace_mesh(obj, shell, label):
    """Swap the object's mesh for ``shell`` (native coordinates), keeping transforms."""
    import bmesh
    import bpy
    from mathutils import Vector
    before = [list(r) for r in obj.matrix_world]
    inverse = obj.matrix_world.inverted()
    mesh = bpy.data.meshes.new(obj.name + ' ' + label)
    mesh.from_pydata([inverse @ Vector(to_world(p)) for p in shell.verts], [], shell.faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    boundary = [e for e in bm.edges if e.is_boundary]
    if boundary:
        bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    nonmanifold = sum(not e.is_manifold for e in bm.edges)
    degenerate = sum(f.calc_area() < 1e-6 for f in bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    for material in obj.data.materials:
        mesh.materials.append(material)
    mesh.uv_layers.new(name='UVMap')
    old = obj.data
    obj.data = mesh
    if old.users == 0:
        bpy.data.meshes.remove(old)
    if [list(r) for r in obj.matrix_world] != before:
        raise ValueError(f'{obj.name}: world transform drifted')
    obj['source_projection_current'] = False
    volume = mesh_volume(obj)
    return {'object': obj.name, 'source_node': obj.get('source_node'),
            'vertices': len(mesh.vertices), 'faces': len(mesh.polygons),
            'nonmanifold_edges': nonmanifold, 'degenerate_faces': degenerate,
            'world_volume': round(volume, 2)}


def mesh_volume(obj):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    volume = bm.calc_volume(signed=True)
    bm.free()
    return volume
