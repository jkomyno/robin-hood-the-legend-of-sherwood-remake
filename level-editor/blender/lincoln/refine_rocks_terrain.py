"""Lincoln rocks/terrain lane geometry recipe (idempotent, per workspace).

Run from the repository root, one asset per process:

    /usr/bin/blender --background --threads 2 --python-exit-code 1 \
        --python level-editor/blender/lincoln/refine_rocks_terrain.py -- \
        --asset <asset-id> [--packet] [--analyse]

The recipe acquires a Lincoln render slot, opens the asset workspace's
``model.blend`` and rebuilds only the owned meshes from the frozen native
geometry in ``inventory/inventory.json``; running it twice gives identical
meshes. ``--packet`` then regenerates ``modified/`` with the frozen tooling.
``--analyse`` writes the per-node support/carve report without saving.

Geometry rules (native units; pixel = (x, y - z)):

* Plateau and terrace volumes keep their native top heights and outlines.
  They are terrain shared with every other lane.
* A rock rebuild never exceeds the native obstacle prism. Its base replaces the
  native z = 0 datum by the reviewed terrain surface below it (``support``) or
  by a documented ground height measured from the native silhouette foot.
  Parts buried inside a supporting terrain volume are removed.
* ``carve`` lowers columns whose source pixel lies outside the node's reviewed
  native silhouette, unless that pixel is covered by a reviewed foreground
  exclusion mask (hidden, therefore unknown). The result is a closed
  heightfield solid with softened shoulders.

Terrain source-domain assignments (``MASKS``) are explicit reviewed receiver
changes to the asset's working ``source-masks.json``; they only use native
terrain silhouettes and are written idempotently.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from mathutils.geometry import tessellate_polygon

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rocks_terrain_volumes_core as core  # noqa: E402

REPO = HERE.parents[2]
ROOT = REPO / 'level-editor/work/lincoln-refinement'
ASSETS = ROOT / 'round-1/assets'
INVENTORY = ROOT / 'inventory/inventory.json'
TOOLING = ROOT / 'tooling/e6b57cb851c7142b'
TAG = 'lincoln_rocks_terrain_recipe'
VERSION = 'rocks-terrain-v1'

# Terrain volumes whose native tops are the reviewed ground for rocks. Tops are
# never changed by this lane, so other lanes may rely on the same surfaces.
SUPPORT_NODES = [52, 53, 54, 55, 56, 57, 61, 62, 63, 64, 65, 66, 67, 68, 70]


def _normalise(spec):
    if 'raise_' in spec:
        spec['raise'] = spec.pop('raise_')
    return spec


def rock(**kw):
    spec = {'mode': 'carve', 'cell': 2.0, 'support': True, 'floor': 0.0,
            'round': 10.0, 'edge': 0.3, 'occluders': [], 'smooth': 4,
            'min_component': 6, 'dome': False}
    spec.update(kw)
    return _normalise(spec)


def trim(**kw):
    spec = {'mode': 'trim', 'cell': 2.0, 'support': True, 'floor': 0.0,
            'round': 0.0, 'occluders': [], 'smooth': 0, 'min_component': 6}
    spec.update(kw)
    return _normalise(spec)


KEEP = {'mode': 'keep'}

# Per node rebuild specification. Measured ground heights come from the
# silhouette-foot analysis in inspection/ground-contact.json of each asset.
NODES = {
    # Ground-level boulders beside the stream and on the western map edge.
    436: rock(round=8.0),
    454: {'mode': 'stump'},
    438: rock(), 439: rock(), 440: rock(), 441: rock(), 442: rock(),
    # Hillside boulders below the great hall's north-west corner. Their painted
    # feet sit at native z 0..17 on the lower slope; the keep plateau outline
    # is not used as support here (see review).
    447: rock(cell=1.5, support=False), 448: rock(cell=1.5, support=False),
    449: rock(support=False, floor=15.0), 450: rock(support=False),
    451: rock(cell=1.5, support=False),
    # South-eastern bank rocks. The outcrop's painted foot descends to native
    # z ~150 east of the bank plateau outline; the small pair sits on it.
    443: rock(cell=3.0, floor=150.0, round=10.0),
    444: rock(cell=3.0, floor=150.0, round=10.0),
    445: rock(cell=1.5), 446: rock(cell=1.5),
    # West tower hillside: a rock on the lower northern slope behind the west
    # tower hall roof and a boulder on the western grass slope. The two
    # non-solid sight volumes 455/456 stand west of the plateau outline on the
    # native z = 0 hillside and are kept (see review).
    452: rock(support=False, occluders=[291, 297]),
    453: rock(),
    # 455/456 recede wherever they would hide the painted rocks 452/453.
    455: None, 456: None,
    # South-western castle cliff rock faces (shared moat-bank envelope 265).
    # They tile one continuous painted cliff, so the authored facets are kept
    # and only the parts buried in the cliff-road and plateau volumes removed.
    423: trim(), 424: trim(), 425: trim(), 426: trim(), 431: trim(),
    427: trim(), 428: trim(), 429: trim(), 430: trim(),
    # Inner rock spur and raised upper-ward ground. The spur envelopes are
    # largely hidden behind the inner west gate, so columns are not carved.
    # 432/433 carry the reviewed outcrop envelope 267 and are carved to it (the
    # great hall west wing masonry shows above them); 434 is raised to the
    # painted crest traced at the keep annex round turret; 435/465 keep their
    # native tops above the bailey plateau.
    432: rock(cell=2.0, round=6.0, floor=220.0), 433: rock(cell=2.0, round=6.0, floor=220.0),
    434: trim(raise_={'points': [[1655, 1117, 1498], [1670, 1120, 1512], [1693, 1147, 1521],
                                  [1717, 1177, 1521], [1733, 1207, 1518]],
                       'slope': 1.6, 'reach': 45}),
    435: trim(), 465: trim(),
}

# Terrain assets keep their native geometry.
for _n in (52, 53, 54, 55, 56, 57, 61, 62, 63, 64, 65, 66, 67, 68, 74, 75, 76):
    NODES[_n] = KEEP

from rocks_terrain_volumes_masks import (MASKS, FOLIAGE, WALLS, CLIFF_WALLS,  # noqa: E402
                                          CLIFF_FOLIAGE)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def node_name(n):
    return f'building-{n:03d}'


# --------------------------------------------------------------------------
# Native evidence
# --------------------------------------------------------------------------

_INVENTORY = None


def native_triangles(source_node):
    """Frozen native mesh of a node as native-coordinate triangles."""
    global _INVENTORY
    if _INVENTORY is None:
        _INVENTORY = {o['source_node']: o for o in json.loads(INVENTORY.read_text())['objects']}
    record = _INVENTORY[source_node]
    matrix = Matrix(record['matrix_world'])
    world = [matrix @ Vector(v) for v in record['geometry']['vertices']]
    tris = []
    for face in record['geometry']['faces']:
        pts = [world[i] for i in face]
        for a, b, c in tessellate_polygon([pts]):
            tris.append([pts[a], pts[b], pts[c]])
    tris = np.array([[list(p) for p in t] for t in tris], float)
    native = core.world_to_native(tris.reshape(-1, 3)).reshape(-1, 3, 3)
    return native, matrix


class MaskStore:
    """Native mask bitmaps (source-image sized booleans) from the working manifest."""

    def __init__(self, manifest_path):
        manifest = json.loads(Path(manifest_path).read_text())
        inventory_path = (Path(manifest_path).parent / manifest['mask_inventory']).resolve(strict=True)
        self.dir = inventory_path.parent
        inventory = json.loads(inventory_path.read_text())
        self.records = {r['index']: r for r in inventory['masks']}
        self.size = (2176, 2944)
        self.cache = {}

    def get(self, index):
        if index in self.cache:
            return self.cache[index]
        record = self.records[index]
        full = np.zeros(self.size, bool)
        if record.get('png') is None:
            raise ValueError(f'Degenerate mask {index}')
        image = bpy.data.images.load(str(self.dir / record['png']), check_existing=False)
        w, h = image.size
        px = np.empty(w * h * 4, np.float32)
        image.pixels.foreach_get(px)
        bpy.data.images.remove(image)
        # Blender stores rows bottom-up.
        a = px.reshape(h, w, 4)[::-1]
        on = (a[..., :3].max(-1) > 0.5) & (a[..., 3] > 0.5)
        x, y = record['box_top_left']
        y0, y1 = max(0, y), min(self.size[0], y + h)
        x0, x1 = max(0, x), min(self.size[1], x + w)
        full[y0:y1, x0:x1] = on[y0 - y:y1 - y, x0 - x:x1 - x]
        self.cache[index] = full
        return full

    def union(self, indices):
        out = np.zeros(self.size, bool)
        for i in indices:
            out |= self.get(i)
        return out


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------

def support_surface(grid, exclude):
    """Highest supporting terrain top per cell (0 = generic ground plane)."""
    out = np.zeros((grid.ny, grid.nx))
    for n in SUPPORT_NODES:
        if n in exclude:
            continue
        tris, _ = native_triangles(node_name(n))
        top = core.raster_surface(grid, tris, upward=True)
        out = np.where(~np.isnan(top) & (top > out), top, out)
    return out


def build_heightfield_mesh(grid, inside, top, base, edge=1.0, radius=0.0, neighbour=None, vsmooth=True):
    """Closed solid between ``base`` and ``top`` over the inside cells.

    Cells become lattice quads; the staircase outline is relaxed in 2D so
    rock outlines follow the carved footprint without pixel steps.
    """
    inside = core.remove_pinches(inside)
    ny, nx = inside.shape
    index = -np.ones((ny + 1, nx + 1), int)
    corners = []
    for j, i in zip(*np.nonzero(inside)):
        for cj, ci in ((j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i)):
            if index[cj, ci] < 0:
                index[cj, ci] = len(corners)
                corners.append((ci, cj))
    corners = np.array(corners)
    xy = np.stack([grid.x0 + corners[:, 0] * grid.cell, grid.y0 + corners[:, 1] * grid.cell], 1)
    # Corner heights: mean of the adjacent inside cells.
    zt = np.zeros(len(corners))
    zb = np.zeros(len(corners))
    cnt = np.zeros(len(corners))
    for j, i in zip(*np.nonzero(inside)):
        for cj, ci in ((j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i)):
            k = index[cj, ci]
            zt[k] += top[j, i]
            zb[k] += base[j, i]
            cnt[k] += 1
    zt /= cnt
    zb /= cnt
    quads = [(index[j, i], index[j, i + 1], index[j + 1, i + 1], index[j + 1, i])
             for j, i in zip(*np.nonzero(inside))]
    count = {}
    for q in quads:
        for e in ((q[0], q[1]), (q[1], q[2]), (q[2], q[3]), (q[3], q[0])):
            key = tuple(sorted(e))
            count[key] = count.get(key, 0) + 1
    boundary = {k for k, v in count.items() if v == 1}
    neighbours = {}
    for a, b in boundary:
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)
    ring = np.array(sorted(neighbours))
    if any(len(v) != 2 for v in neighbours.values()):
        raise ValueError('Outline is not a set of simple loops')
    # Relax the staircase: boundary corners move toward their loop neighbours.
    for _ in range(6):
        target = np.array([xy[neighbours[k]].mean(0) for k in ring])
        xy[ring] = 0.5 * xy[ring] + 0.5 * target
    # Relax interior corners toward their lattice neighbours so the first
    # interior ring follows the smoothed outline.
    adjacency = {}
    for q in quads:
        for u, v in ((q[0], q[1]), (q[1], q[2]), (q[2], q[3]), (q[3], q[0])):
            adjacency.setdefault(u, set()).add(v)
            adjacency.setdefault(v, set()).add(u)
    interior = np.array([k for k in range(len(xy)) if k not in neighbours])
    if len(interior):
        nbrs = [list(adjacency[k]) for k in interior]
        for _ in range(3):
            target = np.array([xy[nb].mean(0) for nb in nbrs])
            xy[interior] = 0.5 * xy[interior] + 0.5 * target
    # Rounded shoulders from the continuous distance to the relaxed outline:
    # the outline keeps ``edge`` of the local height (a short skirt) and the
    # full height is reached ``radius`` native units inside (sqrt profile).
    if radius > 0:
        # Only outline segments facing the source camera (south) or sideways
        # are rounded. North-facing (back) crests define the top of the painted
        # silhouette and keep their native height.
        edge_quad = {}
        for q in quads:
            for u, v in ((q[0], q[1]), (q[1], q[2]), (q[2], q[3]), (q[3], q[0])):
                key = tuple(sorted((u, v)))
                if key in boundary:
                    edge_quad[key] = q
        keep_segments = []
        for key in boundary:
            a, b = xy[key[0]], xy[key[1]]
            centre = xy[list(edge_quad[key])].mean(0)
            d = b - a
            normal = np.array([d[1], -d[0]])
            if np.dot(normal, (a + b) / 2 - centre) < 0:
                normal = -normal
            normal /= max(np.linalg.norm(normal), 1e-9)
            if neighbour is not None:
                probe = (a + b) / 2 + normal * grid.cell
                i = int((probe[0] - grid.x0) / grid.cell)
                j = int((probe[1] - grid.y0) / grid.cell)
                if 0 <= i < grid.nx and 0 <= j < grid.ny and neighbour[j, i]:
                    continue  # seam shared with an adjoining rock of this asset
            if normal[1] > -0.35:
                keep_segments.append(key)
        if not keep_segments:
            keep_segments = list(boundary)
        seg_a = xy[[a for a, b in keep_segments]]
        seg_b = xy[[b for a, b in keep_segments]]
        dist = np.full(len(xy), np.inf)
        for start in range(0, len(xy), 512):
            p = xy[start:start + 512, None, :]
            ab = seg_b - seg_a
            t = np.clip(((p - seg_a) * ab).sum(-1) / np.maximum((ab * ab).sum(-1), 1e-12), 0, 1)
            closest = seg_a + t[..., None] * ab
            dist[start:start + 512] = np.sqrt(((p - closest) ** 2).sum(-1)).min(1)
        profile = edge + (1 - edge) * np.sin(0.5 * np.pi * np.clip(dist / radius, 0, 1))
        zt = zb + (zt - zb) * profile
    # Vertex-level Laplacian smoothing of the cap (outline fixed) removes
    # lattice zigzag where the diagonal outline meets the grid.
    if len(interior) and vsmooth:
        for _ in range(4):
            target = np.array([zt[nb].mean() for nb in nbrs])
            zt[interior] = 0.5 * zt[interior] + 0.5 * target
    zt = np.maximum(zt, zb + 0.3)
    n = len(xy)
    native = np.vstack([np.column_stack([xy, zt]), np.column_stack([xy, zb])])
    polys = []
    for q in quads:
        polys.append(q)
        polys.append(tuple(v + n for v in reversed(q)))
        for u, v in ((q[0], q[1]), (q[1], q[2]), (q[2], q[3]), (q[3], q[0])):
            if tuple(sorted((u, v))) in boundary:
                polys.append((v, u, u + n, v + n))
    return native, polys


def restore_native(obj):
    """Make the mesh equal to the frozen native geometry; True if it changed."""
    record = _INVENTORY[obj['source_node']]['geometry']
    same = (len(record['vertices']) == len(obj.data.vertices)
            and all((Vector(a) - v.co).length < 1e-3 for a, v in zip(record['vertices'], obj.data.vertices))
            and [list(p.vertices) for p in obj.data.polygons] == record['faces'])
    if same:
        return False
    old = obj.data
    mesh = bpy.data.meshes.new(obj.name)
    mesh.from_pydata([tuple(v) for v in record['vertices']], [], [tuple(f) for f in record['faces']])
    mesh.update()
    mesh.materials.append(old.materials[0])
    uv = mesh.uv_layers.new(name='UVMap')
    for loop in mesh.loops:
        p = obj.matrix_world @ mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (p.x / 2944, 1 - (-p.y * core.SIN35 - p.z * core.COS35) / 2176)
    obj.data = mesh
    if old.users == 0:
        bpy.data.meshes.remove(old)
    mesh.name = obj.name
    return True


def neighbour_cells(grid, nodes):
    out = np.zeros((grid.ny, grid.nx), bool)
    for node in nodes:
        tris, _ = native_triangles(node)
        out |= ~np.isnan(core.raster_surface(grid, tris))
    return core.close_cells(out, 1) if out.any() else out


def stump_mesh(tris, spec):
    """Round tree stump: a flared frustum inscribed in the native footprint."""
    xy = tris.reshape(-1, 3)
    cx, cy = (xy[:, 0].min() + xy[:, 0].max()) / 2, (xy[:, 1].min() + xy[:, 1].max()) / 2
    # Round in metric world space: native y is foreshortened by sin 35.
    radius = min(xy[:, 0].max() - xy[:, 0].min(), (xy[:, 1].max() - xy[:, 1].min()) / core.SIN35) / 2
    top = float(xy[:, 2].max())
    rings = [(0.0, 1.0), (0.12 * top, 0.9), (0.85 * top, 0.8), (top, 0.74)]
    count = 16
    verts = []
    for z, f in rings:
        for k in range(count):
            a = 2 * math.pi * k / count
            verts.append((cx + radius * f * math.cos(a), cy + radius * f * core.SIN35 * math.sin(a), z))
    verts.append((cx, cy, top))
    verts.append((cx, cy, 0.0))
    world = core.native_to_world(np.array(verts))
    bm = bmesh.new()
    bv = [bm.verts.new(Vector(p)) for p in world]
    for r in range(len(rings) - 1):
        for k in range(count):
            a, b = r * count + k, r * count + (k + 1) % count
            bm.faces.new([bv[a], bv[b], bv[b + count], bv[a + count]])
    cap, bottom = bv[-2], bv[-1]
    last = (len(rings) - 1) * count
    for k in range(count):
        bm.faces.new([bv[last + k], bv[last + (k + 1) % count], cap])
        bm.faces.new([bv[(k + 1) % count], bv[k], bottom])
    return bm, {'centre': [round(cx, 2), round(cy, 2)], 'radius': round(radius, 2), 'top': round(top, 2),
                'rings_height_radiusfraction': rings}


def finalize(bm, label):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-5)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    defects = {'nonmanifold_edges': sum(not e.is_manifold for e in bm.edges),
               'boundary_edges': sum(e.is_boundary for e in bm.edges),
               'degenerate_faces': sum(f.calc_area() < 1e-6 for f in bm.faces)}
    return defects


WALL_LANES = ('south_gate_walls', 'east_gate_walls')
WEST_LANES = ('west_complex',)
BASTION_WALLS = [282, 283, 284]


# Terrain fronts. Plateau tops stay at z = 220 wherever the art allows. A
# column is lowered only while its top pixel lands on the reviewed silhouette
# of a neighbouring wall (south/east/west lanes): the artwork shows that
# masonry, so the terrain must recede below the wall foot there.
def terrain_front(lanes=None, **kw):
    spec = {'mode': 'front', 'cell': 4.0, 'support': False, 'floor': 0.0, 'round': 0.0,
            'edge': 1.0, 'smooth': 0, 'min_component': 6, 'fill': False, 'dissolve': True,
            'vsmooth': False, 'wall_lanes': lanes or WALL_LANES}
    spec.update(kw)
    return spec


NODES[455] = terrain_front(cell=2.0, foreign_masks=[138, 139])
NODES[456] = terrain_front(cell=2.0, foreign_masks=[138, 139])
NODES[62] = terrain_front()
NODES[63] = terrain_front()
NODES[64] = terrain_front()
NODES[70] = terrain_front(cell=2.0)
# West plateau: the bastion's lower rooms (terrace volumes 060/069, floor
# z = 147) are cut out of it, and its front below the western complex is
# carved to the moat-bank envelope with the bastion walls treated as foreign.
NODES[65] = terrain_front(WEST_LANES + WALL_LANES, cutout=[60, 69])
# South-western cliff rocks meet the bastion wall feet (traced z 95-150 by the
# western complex lane): carve their band in front of the bastion likewise.
for _n in (423, 424, 425, 426, 427, 428, 429, 430, 431):
    # Foliage exclusions hide rock (support it); bastion wall exclusions do
    # not, so the cliff recedes below the bastion's painted wall feet.
    NODES[_n] = rock(cell=2.0, support=True, round=0.0, edge=1.0, smooth=1, fill=True, dissolve=True,
                     vsmooth=True, occluders=CLIFF_FOLIAGE, occluders_only=True)


def wall_nodes(lanes):
    assignments = json.loads((ROOT / 'worker-assignments.json').read_text())['assignments']
    catalog = json.loads((ROOT / 'grouping/catalog.json').read_text())
    groups = {g['id']: g for g in catalog['groups']}
    return sorted({node_name(p['obstacle']) for lane in lanes for asset in assignments[lane]
                   for p in groups[asset]['parts']})


def front_band(grid, lanes, depth):
    """Cells south of the southernmost wall cell of each column (within depth)."""
    walls = np.zeros((grid.ny, grid.nx), bool)
    for node in wall_nodes(lanes):
        tris, _ = native_triangles(node)
        xy = tris.reshape(-1, 3)
        if xy[:, 0].max() < grid.x0 or xy[:, 0].min() > grid.x0 + grid.nx * grid.cell:
            continue
        walls |= ~np.isnan(core.raster_surface(grid, tris))
    band = np.zeros_like(walls)
    rows = np.arange(grid.ny)[:, None]
    has = walls.any(0)
    last = np.where(has, grid.ny - 1 - np.argmax(walls[::-1], 0), -1)
    band = (rows > last[None, :]) & has[None, :] & ((rows - last[None, :]) * grid.cell <= depth)
    return band


_WALL_CACHE = {}


def wall_silhouettes(masks, lanes):
    """Union of the frozen reviewed include masks of every wall-lane node."""
    key = tuple(lanes)
    if key not in _WALL_CACHE:
        nodes = set(wall_nodes(lanes))
        frozen = json.loads((ROOT / 'mask-review/source-masks-v1.json').read_text())
        indices = sorted({i for r in frozen['projections']['exterior']['assignments']
                          if r.get('source_node') in nodes for i in r['mask_indices'] if i != 428})
        _WALL_CACHE[key] = masks.union(indices)
    return _WALL_CACHE[key]


def raise_to_trace(grid, heights, inside, base, trace):
    """Raise a rock crest to a traced painted crest line.

    ``trace['points']`` are [pixel x, pixel y, native y of the contact]; the
    crest height at each point is contact_y - pixel_y (source camera). South
    of the contact line the surface falls off with ``slope`` (z per native y)
    for at most ``reach`` units and never drops below the existing height.
    """
    pts = np.array(trace['points'], float)
    X, Y = grid.centers()
    in_range = (X >= pts[:, 0].min()) & (X <= pts[:, 0].max())
    depth = np.interp(X, pts[:, 0], pts[:, 2])
    crest = np.interp(X, pts[:, 0], pts[:, 2] - pts[:, 1])
    target = crest - trace['slope'] * np.maximum(Y - depth, 0)
    zone = in_range & (Y >= depth) & (Y <= depth + trace['reach']) & (target > base + 0.5)
    new = np.where(zone, np.fmax(heights, target), heights)
    raised = int((zone & ~(inside & (np.nan_to_num(heights) >= target))).sum())
    return new, inside | zone, raised, np.where(zone, new, np.nan)


def rebuild(obj, spec, masks, working_assignment, dry=False, neighbours=()):
    n = int(obj['source_node'].split('-')[-1])
    tris, matrix = native_triangles(obj['source_node'])
    if max(abs(a - b) for ra, rb in zip(matrix, obj.matrix_world) for a, b in zip(ra, rb)) > 1e-4:
        raise ValueError(f'Native transform differs for {obj.name}')
    report = {'object': obj.name, 'source_node': obj['source_node'], 'mode': spec['mode']}
    ztop_native = float(tris[..., 2].max())
    report['native_top'] = round(ztop_native, 2)
    if spec['mode'] == 'keep':
        report['changed'] = restore_native(obj)
        return report, None
    if spec['mode'] == 'stump':
        if dry:
            return report, None
        bm, shape = stump_mesh(tris, spec)
        report['construction'] = 'round flared stump inscribed in the native footprint'
        report['stump'] = shape
        report['topology'] = finalize(bm, obj.name)
        inverse = obj.matrix_world.inverted()
        for v in bm.verts:
            v.co = inverse @ v.co
        return report, bm
    cell = spec['cell']
    xy = tris.reshape(-1, 3)
    grid = core.Grid(xy[:, 0].min(), xy[:, 1].min(), xy[:, 0].max(), xy[:, 1].max(), cell)
    top = core.raster_surface(grid, tris, upward=True)
    # Close one-cell seams between the native faces of multi-part prisms.
    native_inside = core.close_cells(~np.isnan(top), 2)
    top = core.extend(top, ~np.isnan(top), 2)
    if spec.get('cutout'):
        cut = np.zeros_like(native_inside)
        for m in spec['cutout']:
            cut |= ~np.isnan(core.raster_surface(grid, native_triangles(node_name(m))[0]))
        report['cutout_cells'] = int((native_inside & cut).sum())
        report['cutout_nodes'] = spec['cutout']
        native_inside &= ~cut
    top = np.where(native_inside, top, np.nan)
    support = support_surface(grid, exclude={n}) if spec['support'] else np.zeros_like(top)
    base = np.maximum(support, spec['floor'])
    buried = native_inside & (top <= base + 0.5)
    report['native_cells'] = int(native_inside.sum())
    report['buried_cells'] = int(buried.sum())
    report['support_used'] = spec['support']
    report['floor'] = spec['floor']
    report['base_range'] = [round(float(base[native_inside & ~buried].min()), 1),
                            round(float(base[native_inside & ~buried].max()), 1)] if (native_inside & ~buried).any() else None
    if spec['mode'] == 'front':
        if spec.get('foreign_masks'):
            foreign = masks.union(spec['foreign_masks'])
            eligible = native_inside
            report['foreign_masks'] = spec['foreign_masks']
        else:
            foreign = wall_silhouettes(masks, spec['wall_lanes'])
            eligible = native_inside & front_band(grid, spec['wall_lanes'], spec.get('band_depth', 120.0))
        report['band_cells'] = int(eligible.sum())
        carved, counts = core.carve_foreign(grid, np.where(eligible, top, np.nan), base, foreign)
        heights = np.where(eligible, carved, np.where(native_inside, top, np.nan))
        report['front_carve'] = counts
        report['wall_lanes'] = [] if spec.get('foreign_masks') else list(spec['wall_lanes'])
        inside = native_inside & ~np.isnan(heights) & (heights > base + 0.5)
    elif spec['mode'] == 'trim':
        values = sorted(set(np.round(base[native_inside & ~buried], 1).tolist()))
        report['trim_base_values'] = values[:8]
        heights = top
        inside = native_inside & ~buried
    else:
        own = masks.union([i for i in working_assignment['mask_indices'] if i != 428])
        reviewed_exclusions = working_assignment.get('exclude_mask_indices', [])
        if reviewed_exclusions:
            own &= ~masks.union(reviewed_exclusions)
        # Terrain fronts treat neighbouring walls as foreign (the wall masonry
        # must not be hidden behind terrain); rocks treat exclusions as hidden.
        excluded = list(spec['occluders']) if spec.get('occluders_only') else reviewed_exclusions + spec['occluders']
        occ = masks.union(excluded) if excluded else np.zeros_like(own)
        eligible = native_inside
        if spec.get('band'):
            eligible = native_inside & front_band(grid, spec['band'], spec.get('band_depth', 1e9))
            report['band_cells'] = int(eligible.sum())
        carved, counts = core.carve(grid, np.where(eligible, top, np.nan), base, own, occ)
        heights = np.where(eligible, carved, np.where(native_inside, top, np.nan))
        report['carve'] = counts
        report['own_masks'] = working_assignment['mask_indices']
        report['occluder_masks'] = excluded
        inside = ~np.isnan(heights) & (heights > base + 0.5)
    raise_cap = None
    if spec.get('raise'):
        heights, inside, raised, raise_cap = raise_to_trace(grid, heights, inside, base, spec['raise'])
        report['raised_cells'] = raised
        report['raise_trace'] = spec['raise']
    labels, sizes = core.components(inside)
    keep = np.zeros_like(inside)
    for label, size in enumerate(sizes):
        if label and size >= spec['min_component']:
            keep |= labels == label
    inside = core.remove_pinches(core.fill_holes(keep) if spec.get('fill', True) else keep)
    filled = inside & (np.isnan(heights) | (heights <= base + 0.5))
    heights = core.extend(np.where(inside & ~filled, heights, np.nan), inside & ~filled, 6)
    heights = np.where(inside, heights, np.nan)
    if np.isnan(heights[inside]).any():
        raise ValueError(f'{obj.name}: unresolved heights after hole fill')
    if spec.get('dome'):
        heights = np.where(inside, core.mirror_dome(np.nan_to_num(heights), inside), np.nan)
        heights = np.maximum(heights, base + 0.5)
    if spec['smooth']:
        heights = np.where(inside, core.smooth(np.nan_to_num(heights), inside, spec['smooth']), np.nan)
    if spec['mode'] not in ('trim', 'front'):
        cap = np.where(native_inside, top, heights)
        if raise_cap is not None:
            cap = np.where(~np.isnan(raise_cap), np.fmax(cap, raise_cap), cap)
        heights = np.minimum(heights, cap)
    report['kept_cells'] = int(inside.sum())
    report['kept_height_range'] = [round(float(np.nanmin(heights)), 1), round(float(np.nanmax(heights)), 1)] if inside.any() else None
    if not inside.any():
        raise ValueError(f'{obj.name}: rebuild removed every column')
    if dry:
        return report, None
    raised = native_inside & (base > 0.5)
    if spec['mode'] == 'front' and report.get('front_carve', {}).get('lowered_columns', 1) == 0:
        report['construction'] = 'native volume kept: no column covers neighbouring wall masonry'
        report['changed'] = restore_native(obj)
        return report, None
    if spec['mode'] == 'trim' and raised.sum() <= 0.05 * native_inside.sum():
        report['raised_base_fraction'] = round(float(raised.sum() / native_inside.sum()), 4)
        report['construction'] = ('native volume kept: its footprint stands on the z = 0 ground '
                                  '(any overlap with supporting terrain is under 5 percent)')
        report['changed'] = restore_native(obj)
        return report, None
    native, polys = build_heightfield_mesh(grid, inside, heights, base, spec.get('edge', 1.0),
                                           spec['round'], neighbour_cells(grid, neighbours),
                                           spec.get('vsmooth', True))
    world = core.native_to_world(native)
    bm = bmesh.new()
    verts = [bm.verts.new(Vector(p)) for p in world]
    for p in polys:
        try:
            bm.faces.new([verts[i] for i in p])
        except ValueError:
            pass
    if spec.get('dissolve'):
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts, edges=bm.edges)
    report['construction'] = ('closed native-top solid over the unburied footprint, based on the supporting terrain'
                              if spec['mode'] == 'trim' else 'closed heightfield solid over carved native footprint')
    defects = finalize(bm, obj.name)
    report['topology'] = defects
    inverse = obj.matrix_world.inverted()
    for v in bm.verts:
        v.co = inverse @ v.co
    return report, bm


def apply_mesh(obj, bm):
    old = obj.data
    mesh = bpy.data.meshes.new(obj.name)
    bm.to_mesh(mesh)
    bm.free()
    # Keep the original fallback material only; the frozen projection helper
    # rebuilds its own projection materials and UV layers.
    mesh.materials.append(old.materials[0])
    uv = mesh.uv_layers.new(name='UVMap')
    for loop in mesh.loops:
        p = obj.matrix_world @ mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (p.x / 2944, 1 - (-p.y * core.SIN35 - p.z * core.COS35) / 2176)
    obj.data = mesh
    if old.users == 0:
        bpy.data.meshes.remove(old)
    mesh.name = obj.name


def pixel_triangles(world_tris):
    """Source-pixel triangles (x, y - z) from world-space triangles."""
    w = np.asarray(world_tris, float).reshape(-1, 3)
    px = np.stack([w[:, 0], -w[:, 1] * core.SIN35 - w[:, 2] * core.COS35, np.zeros(len(w))], 1)
    return px.reshape(-1, 3, 3)


def object_world_triangles(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    mw = obj.matrix_world
    co = [mw @ v.co for v in mesh.vertices]
    return [[list(co[i]) for i in t.vertices] for t in mesh.loop_triangles]


def silhouette_stats(owned, assignments, masks):
    """Asset silhouette (native vs rebuilt) against its reviewed native masks."""
    native_tris, new_tris, own = [], [], None
    for obj in owned:
        tris, _ = native_triangles(obj['source_node'])
        native_tris.extend(core.native_to_world(tris.reshape(-1, 3)).reshape(-1, 3, 3).tolist())
        new_tris.extend(object_world_triangles(obj))
        row = assignments[obj['source_node']]
        idx = [i for i in row['mask_indices'] if i != 428]
        if not idx:
            continue
        m = masks.union(idx)
        if row.get('exclude_mask_indices'):
            m &= ~masks.union(row['exclude_mask_indices'])
        own = m if own is None else own | m
    if own is None:
        return {'status': 'no reviewed native mask; silhouette comparison not applicable'}
    a = pixel_triangles(native_tris)
    b = pixel_triangles(new_tris)
    both = np.vstack([a.reshape(-1, 3), b.reshape(-1, 3)])
    grid = core.Grid(both[:, 0].min(), both[:, 1].min(), both[:, 0].max(), both[:, 1].max(), 1.0)
    X, Y = grid.centers()
    cols = np.clip(np.floor(X).astype(int), 0, 2943)
    rows = np.clip(np.floor(Y).astype(int), 0, 2175)
    valid = (X >= 0) & (X < 2944) & (Y >= 0) & (Y < 2176)
    m = own[rows, cols] & valid
    result = {'mask_pixels_in_frame': int(m.sum())}
    for label, tris in (('native', a), ('rebuilt', b)):
        sil = ~np.isnan(core.raster_surface(grid, tris)) & valid
        inter = int((sil & m).sum())
        union = int((sil | m).sum())
        result[label] = {'silhouette_pixels': int(sil.sum()), 'iou': round(inter / max(union, 1), 4),
                         'mask_covered': round(inter / max(int(m.sum()), 1), 4),
                         'outside_mask_pixels': int((sil & ~m).sum())}
    return result


def geometry_hash(obj):
    payload = [[list(v.co) for v in obj.data.vertices], [list(p.vertices) for p in obj.data.polygons],
               [list(r) for r in obj.matrix_world]]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def apply_masks(workspace, config, part_ids, write=True):
    """Idempotently write the reviewed MASKS rows for owned nodes."""
    path = Path(config['source_mask_manifest'])
    frozen = json.loads((Path(config['mask_reference']) / 'assignments.json').read_text())
    working = json.loads(path.read_text())
    frozen_rows = {r['source_node']: r for r in frozen['projections']['exterior']['assignments']
                   if 'source_node' in r}
    changes = []
    rows = working['projections']['exterior']['assignments']
    for i, row in enumerate(rows):
        node = row.get('source_node')
        if node not in part_ids:
            continue
        n = int(node.split('-')[-1])
        new = dict(frozen_rows[node])
        if n in MASKS:
            spec = MASKS[n]
            evidence = str(workspace / 'inspection' / f'mask-review-{node}.png')
            if spec.get('include') is not None:
                new = {'reviewed': True, 'source_node': node, 'mask_indices': list(spec['include']),
                       'constraint_kind': 'reviewed-native-silhouette',
                       'native_ownership_reviewed': True,
                       'review_group': 'rocks-terrain-' + node,
                       'review_evidence': evidence,
                       'review_note': spec['note'],
                       'requires_first_hit_gating': True,
                       'composite_envelope': 'native terrain/occluder silhouette shared with neighbours; '
                                             'receiver gating partitions it',
                       'frozen_assignment': {k: frozen_rows[node][k] for k in
                                             ('constraint_kind', 'mask_indices', 'review_group')}}
            exclude = sorted(set(new.get('exclude_mask_indices', [])) | set(spec.get('exclude', [])))
            if exclude:
                new['exclude_mask_indices'] = exclude
                new['exclusions_reviewed'] = True
                new['exclusion_reason'] = spec['reason']
                new['exclusion_evidence'] = evidence
        if row != new:
            rows[i] = new
            changes.append(node)
    if changes and write:
        path.write_text(json.dumps(working, indent=2, sort_keys=True) + '\n')
    return changes, working


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset', required=True)
    parser.add_argument('--packet', action='store_true')
    parser.add_argument('--analyse', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    workspace = (ASSETS / args.asset).resolve(strict=True)
    config = json.loads((workspace / 'workspace.json').read_text())
    if config['asset_id'] != args.asset:
        raise ValueError('Workspace asset mismatch')
    from render_slots import acquire
    acquire()
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'))
    scene = bpy.data.scenes[config['scene_name']]
    bpy.context.window.scene = scene
    collection = bpy.data.collections[config['collection_name']]
    owned = [o for o in collection.all_objects if o.type == 'MESH' and o.get('asset_group') == args.asset]
    part_ids = sorted({o['source_node'] for o in owned})
    if part_ids != config['part_ids'] or len(owned) != len(part_ids):
        raise ValueError(f'Unexpected owned meshes {part_ids}')
    outside = {o.name: geometry_hash(o) for o in scene.objects if o.type == 'MESH' and o not in owned}
    mask_changes, working = apply_masks(workspace, config, part_ids, write=not args.analyse)
    assignments = {r['source_node']: r for r in working['projections']['exterior']['assignments'] if 'source_node' in r}
    masks = MaskStore(config['source_mask_manifest'])
    reports = []
    for obj in sorted(owned, key=lambda o: o['source_node']):
        n = int(obj['source_node'].split('-')[-1])
        spec = NODES[n]
        before = geometry_hash(obj)
        neighbours = [o['source_node'] for o in owned if o is not obj
                      and NODES[int(o['source_node'].split('-')[-1])]['mode'] in ('carve', 'trim', 'keep')]
        report, bm = rebuild(obj, spec, masks, assignments[obj['source_node']], dry=args.analyse,
                             neighbours=neighbours)
        if bm is not None:
            apply_mesh(obj, bm)
            report['changed'] = True
        report.setdefault('changed', False)
        report['before_geometry_sha256'] = before
        report['geometry_sha256'] = geometry_hash(obj)
        report['vertices'] = len(obj.data.vertices)
        report['faces'] = len(obj.data.polygons)
        obj[TAG] = VERSION
        reports.append(report)
    silhouette = silhouette_stats(owned, assignments, masks)
    after = {o.name: geometry_hash(o) for o in scene.objects if o.type == 'MESH' and o not in owned}
    if after != outside:
        raise ValueError('Recipe changed an outside object')
    result = {'version': 1, 'asset_id': args.asset, 'recipe': str(Path(__file__).resolve()),
              'recipe_version': VERSION, 'recipe_sha256': sha(__file__),
              'core_sha256': sha(HERE / 'rocks_terrain_volumes_core.py'),
              'mask_changes': mask_changes, 'silhouette': silhouette, 'nodes': reports,
              'outside_objects_unchanged': len(outside)}
    inspection = workspace / 'inspection'
    inspection.mkdir(exist_ok=True)
    name = 'recipe-analysis.json' if args.analyse else 'geometry-recipe.json'
    (inspection / name).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'nodes'}))
    for r in reports:
        print(json.dumps(r))
    if args.analyse:
        return
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(workspace / 'model.blend'))
    if args.packet:
        sys.path.insert(0, str(TOOLING))
        import refinement_workspace
        packet = refinement_workspace.modified(str(workspace))
        print(json.dumps({'packet': packet.get('status'), 'modified': packet.get('modified')}))


if __name__ == '__main__':
    main()
