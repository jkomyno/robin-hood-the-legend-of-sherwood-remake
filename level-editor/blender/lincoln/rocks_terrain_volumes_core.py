"""Numpy geometry helpers for the Lincoln rocks/terrain lane (no Blender imports).

Coordinates are native Lincoln units: x right, y down the map, z up. The source
camera projects native (x, y, z) to source pixel (x, y - z). Blender world
coordinates are X = x, Y = -y / sin35, Z = z / cos35.

The rock rebuild works on a regular native (x, y) cell grid:

* ``top``/``bottom`` rasterize the native obstacle prism (its authored collision
  outline and sloped top), so a rebuilt rock never exceeds the native volume;
* ``support`` is the highest reviewed terrain surface below each cell (the real
  ground contact that replaces the native z = 0 datum);
* ``carve`` lowers each column to the highest point whose source pixel is
  still inside the node's reviewed native silhouette, or hidden behind a
  foreign native occluder mask (occlusion is not evidence of absence).
"""
import math

import numpy as np

SIN35 = math.sin(math.radians(35))
COS35 = math.cos(math.radians(35))


def world_to_native(points):
    p = np.asarray(points, float)
    return np.stack([p[:, 0], -p[:, 1] * SIN35, p[:, 2] * COS35], 1)


def native_to_world(points):
    p = np.asarray(points, float)
    return np.stack([p[:, 0], -p[:, 1] / SIN35, p[:, 2] / COS35], 1)


class Grid:
    """Cell-centred native grid covering a bounding box with a margin."""

    def __init__(self, xmin, ymin, xmax, ymax, cell, margin=2):
        self.cell = float(cell)
        self.x0 = math.floor(xmin / cell) * cell - margin * cell
        self.y0 = math.floor(ymin / cell) * cell - margin * cell
        self.nx = int(math.ceil((xmax - self.x0) / cell)) + margin + 1
        self.ny = int(math.ceil((ymax - self.y0) / cell)) + margin + 1
        self.xs = self.x0 + (np.arange(self.nx) + 0.5) * cell
        self.ys = self.y0 + (np.arange(self.ny) + 0.5) * cell

    def centers(self):
        return np.meshgrid(self.xs, self.ys)  # arrays shaped (ny, nx)


def raster_surface(grid, triangles, upward=True):
    """Max (upward) or min (downward) z of covering triangles per cell centre.

    ``triangles`` is an (n, 3, 3) native array. Vertical faces are skipped. NaN
    marks cells outside the footprint.
    """
    out = np.full((grid.ny, grid.nx), np.nan)
    X, Y = grid.centers()
    for tri in triangles:
        a, b, c = tri
        # Facing is not trusted (native winding is inconsistent): the maximum
        # over every non-vertical covering triangle is the top of a closed
        # prism, the minimum its bottom.
        det = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
        if abs(det) < 1e-6:
            continue
        xmin, xmax = tri[:, 0].min(), tri[:, 0].max()
        ymin, ymax = tri[:, 1].min(), tri[:, 1].max()
        i0 = max(0, int((xmin - grid.x0) / grid.cell) - 1)
        i1 = min(grid.nx, int((xmax - grid.x0) / grid.cell) + 2)
        j0 = max(0, int((ymin - grid.y0) / grid.cell) - 1)
        j1 = min(grid.ny, int((ymax - grid.y0) / grid.cell) + 2)
        if i0 >= i1 or j0 >= j1:
            continue
        px = X[j0:j1, i0:i1]
        py = Y[j0:j1, i0:i1]
        l1 = ((px - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (py - a[1])) / det
        l2 = ((b[0] - a[0]) * (py - a[1]) - (px - a[0]) * (b[1] - a[1])) / det
        l0 = 1 - l1 - l2
        eps = -1e-7
        inside = (l0 >= eps) & (l1 >= eps) & (l2 >= eps)
        z = l0 * a[2] + l1 * b[2] + l2 * c[2]
        view = out[j0:j1, i0:i1]
        if upward:
            update = inside & (np.isnan(view) | (z > view))
        else:
            update = inside & (np.isnan(view) | (z < view))
        view[update] = z[update]
    return out


def carve(grid, top, base, own, occluders, step=1.0):
    """Highest z in [base, top] whose pixel is own-silhouette or occluded.

    Returns (height, evidence) where height is NaN for dropped columns and
    evidence counts columns that were own-supported, occlusion-supported or
    empty. ``own``/``occluders`` are boolean source-image arrays (rows, cols).
    """
    X, Y = grid.centers()
    height = np.full(top.shape, np.nan)
    source = np.zeros(top.shape, np.int8)  # 1 own pixel, 2 occluded pixel
    valid = ~np.isnan(top) & (top > base + 0.25)
    rows, cols = own.shape
    span = np.where(valid, top - base, 0)
    for dz in np.arange(0.0, float(span.max()) + step, step):
        z = base + dz
        live = valid & (z <= top + 1e-6)
        if not live.any():
            continue
        px = np.clip(np.floor(X).astype(int), 0, cols - 1)
        py = np.floor(Y - z).astype(int)
        inside_image = (py >= 0) & (py < rows) & (X >= 0) & (X < cols)
        pyc = np.clip(py, 0, rows - 1)
        hit_own = live & inside_image & own[pyc, px]
        hit_occ = live & inside_image & ~hit_own & occluders[pyc, px]
        # Outside the source image nothing is observed: keep the native top.
        hit_out = live & ~inside_image
        hit = hit_own | hit_occ | hit_out
        height[hit] = z[hit]
        source[hit_own] = 1
        source[hit_occ | hit_out] = 2
    # The top itself may sit between two integer steps.
    counts = {'own_supported': int((source == 1).sum()),
              'occlusion_or_offimage_supported': int((source == 2).sum()),
              'empty_dropped': int((valid & np.isnan(height)).sum()),
              'native_columns': int(valid.sum())}
    return height, counts


def fill_holes(inside):
    """Fill enclosed holes of a boolean grid (4-connected flood from border)."""
    outside = np.zeros_like(inside)
    frontier = np.zeros_like(inside)
    frontier[0, :] = ~inside[0, :]
    frontier[-1, :] = ~inside[-1, :]
    frontier[:, 0] |= ~inside[:, 0]
    frontier[:, -1] |= ~inside[:, -1]
    while frontier.any():
        outside |= frontier
        grow = np.zeros_like(inside)
        grow[1:, :] |= frontier[:-1, :]
        grow[:-1, :] |= frontier[1:, :]
        grow[:, 1:] |= frontier[:, :-1]
        grow[:, :-1] |= frontier[:, 1:]
        frontier = grow & ~inside & ~outside
    return ~outside


def components(inside):
    """Label 4-connected components; returns (labels, sizes)."""
    labels = np.zeros(inside.shape, int)
    sizes = [0]
    current = 0
    for j, i in zip(*np.nonzero(inside)):
        if labels[j, i]:
            continue
        current += 1
        stack = [(j, i)]
        labels[j, i] = current
        size = 0
        while stack:
            y, x = stack.pop()
            size += 1
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < inside.shape[0] and 0 <= xx < inside.shape[1] \
                        and inside[yy, xx] and not labels[yy, xx]:
                    labels[yy, xx] = current
                    stack.append((yy, xx))
        sizes.append(size)
    return labels, sizes


def distance_to_outside(inside, max_steps):
    """Chessboard-ish distance (in cells) from each inside cell to the outside."""
    dist = np.where(inside, float(max_steps), 0.0)
    current = inside.copy()
    for step in range(1, max_steps + 1):
        eroded = current.copy()
        eroded[1:, :] &= current[:-1, :]
        eroded[:-1, :] &= current[1:, :]
        eroded[:, 1:] &= current[:, :-1]
        eroded[:, :-1] &= current[:, 1:]
        eroded[0, :] = eroded[-1, :] = False
        eroded[:, 0] = eroded[:, -1] = False
        dist[current & ~eroded] = step - 0.5
        current = eroded
        if not current.any():
            break
    return dist


def smooth(values, inside, passes=1):
    """Masked 3x3 mean filter over inside cells."""
    v = np.where(inside, values, 0.0)
    w = inside.astype(float)
    for _ in range(passes):
        acc = np.zeros_like(v)
        wt = np.zeros_like(w)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                acc += np.roll(np.roll(v * w, dy, 0), dx, 1)
                wt += np.roll(np.roll(w, dy, 0), dx, 1)
        v = np.where(inside, acc / np.maximum(wt, 1e-9), 0.0)
    return v


def extend(values, inside, passes):
    """Propagate inside values outward so boundary samples are defined."""
    v = np.where(inside, values, np.nan)
    for _ in range(passes):
        missing = np.isnan(v)
        if not missing.any():
            break
        acc = np.zeros_like(v)
        cnt = np.zeros_like(v)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            s = np.roll(np.roll(v, dy, 0), dx, 1)
            ok = ~np.isnan(s)
            acc[ok] += s[ok]
            cnt[ok] += 1
        fill = missing & (cnt > 0)
        v[fill] = acc[fill] / cnt[fill]
    return v


def bilinear(grid, values, x, y):
    """Sample a cell-centred grid at native points (clamped)."""
    fx = (np.asarray(x) - grid.x0) / grid.cell - 0.5
    fy = (np.asarray(y) - grid.y0) / grid.cell - 0.5
    i0 = np.clip(np.floor(fx).astype(int), 0, grid.nx - 2)
    j0 = np.clip(np.floor(fy).astype(int), 0, grid.ny - 2)
    tx = np.clip(fx - i0, 0, 1)
    ty = np.clip(fy - j0, 0, 1)
    v00 = values[j0, i0]
    v10 = values[j0, i0 + 1]
    v01 = values[j0 + 1, i0]
    v11 = values[j0 + 1, i0 + 1]
    return (v00 * (1 - tx) * (1 - ty) + v10 * tx * (1 - ty)
            + v01 * (1 - tx) * ty + v11 * tx * ty)


def marching_loops(inside, grid):
    """Closed outline loops (native xy) around inside cells, holes ignored.

    Edges run along cell borders; each loop is returned counter-clockwise in
    image orientation is not guaranteed, callers must not rely on winding.
    """
    ny, nx = inside.shape
    pad = np.zeros((ny + 2, nx + 2), bool)
    pad[1:-1, 1:-1] = inside
    # Directed boundary edges on the corner lattice, cell (j, i) of pad has
    # corners (i, j)..(i + 1, j + 1). Keep inside on the left of each edge.
    nxt = {}
    js, is_ = np.nonzero(pad)
    for j, i in zip(js, is_):
        if not pad[j - 1, i]:
            nxt.setdefault((i + 1, j), []).append((i, j))       # top edge, leftward
        if not pad[j + 1, i]:
            nxt.setdefault((i, j + 1), []).append((i + 1, j + 1))  # bottom, rightward
        if not pad[j, i - 1]:
            nxt.setdefault((i, j), []).append((i, j + 1))       # left, downward
        if not pad[j, i + 1]:
            nxt.setdefault((i + 1, j + 1), []).append((i + 1, j))  # right, upward
    loops = []
    while nxt:
        start = next(iter(nxt))
        loop = [start]
        cur = start
        while True:
            outs = nxt.get(cur)
            if not outs:
                break
            nb = outs.pop()
            if not outs:
                del nxt[cur]
            if nb == start:
                break
            loop.append(nb)
            cur = nb
        if len(loop) >= 4:
            pts = np.array(loop, float)
            xs = grid.x0 + (pts[:, 0] - 1) * grid.cell
            ys = grid.y0 + (pts[:, 1] - 1) * grid.cell
            loops.append(np.stack([xs, ys], 1))
    return loops


def signed_area(loop):
    x, y = loop[:, 0], loop[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def simplify(loop, tolerance):
    """Douglas-Peucker on a closed loop."""
    if len(loop) < 8:
        return loop
    # Split at the two mutually farthest points.
    d0 = np.linalg.norm(loop - loop[0], axis=1)
    k = int(np.argmax(d0))
    parts = [np.vstack([loop[:k + 1]]), np.vstack([loop[k:], loop[:1]])]

    def dp(pts):
        if len(pts) <= 2:
            return pts
        a, b = pts[0], pts[-1]
        ab = b - a
        n = np.linalg.norm(ab)
        if n < 1e-9:
            d = np.linalg.norm(pts - a, axis=1)
        else:
            d = np.abs(ab[0] * (pts[:, 1] - a[1]) - ab[1] * (pts[:, 0] - a[0])) / n
        i = int(np.argmax(d))
        if d[i] > tolerance:
            left = dp(pts[:i + 1])
            right = dp(pts[i:])
            return np.vstack([left[:-1], right])
        return np.vstack([a, b])

    first = dp(parts[0])
    second = dp(parts[1])
    return np.vstack([first[:-1], second[:-1]])


def smooth_loop(loop, passes=2, weight=0.5):
    """Laplacian smoothing of a closed outline (removes staircase corners)."""
    p = loop.copy()
    for _ in range(passes):
        p = (1 - weight) * p + weight * 0.5 * (np.roll(p, 1, 0) + np.roll(p, -1, 0))
    return p


def mirror_dome(heights, inside):
    """Symmetric ridge per north-south run: h(y) = min(h(y), h(y_front+y_back-y)).

    The source view constrains only the ridge (silhouette crest) and the
    visible front. A carved visual hull rises monotonically to the front; the
    mirrored minimum keeps every column's crest pixel on the silhouette while
    giving the unobserved back the same slope as the front.
    """
    out = heights.copy()
    ny, nx = inside.shape
    for i in range(nx):
        col = inside[:, i]
        j = 0
        while j < ny:
            if not col[j]:
                j += 1
                continue
            k = j
            while k + 1 < ny and col[k + 1]:
                k += 1
            seg = heights[j:k + 1, i]
            out[j:k + 1, i] = np.minimum(seg, seg[::-1])
            j = k + 1
    return out


def remove_pinches(inside):
    """Fill one cell of every diagonal-only contact so the outline is manifold."""
    out = inside.copy()
    changed = True
    while changed:
        changed = False
        a = out[:-1, :-1]
        b = out[:-1, 1:]
        c = out[1:, :-1]
        d = out[1:, 1:]
        p1 = a & d & ~b & ~c
        p2 = b & c & ~a & ~d
        if p1.any() or p2.any():
            changed = True
            js, is_ = np.nonzero(p1)
            out[js, is_ + 1] = True
            js, is_ = np.nonzero(p2)
            out[js, is_] = True
    return out


def close_cells(inside, steps=1):
    """Morphological closing (8-neighbour dilate then erode) of a boolean grid."""
    def dilate(a):
        out = a.copy()
        out[1:, :] |= a[:-1, :]
        out[:-1, :] |= a[1:, :]
        out[:, 1:] |= a[:, :-1]
        out[:, :-1] |= a[:, 1:]
        out[1:, 1:] |= a[:-1, :-1]
        out[:-1, :-1] |= a[1:, 1:]
        out[1:, :-1] |= a[:-1, 1:]
        out[:-1, 1:] |= a[1:, :-1]
        return out
    grown = inside
    for _ in range(steps):
        grown = dilate(grown)
    shrunk = ~grown
    for _ in range(steps):
        shrunk = dilate(shrunk)
    return inside | ~shrunk


def carve_foreign(grid, top, base, foreign, step=1.0):
    """Lower each column only while its top pixel lands on a foreign structure.

    A terrain surface cannot stand in front of masonry that the artwork draws
    as visible, so the column is lowered to the first height (going down)
    whose pixel is clear of ``foreign``. Columns that never clear drop to base.
    Returns (height, counts).
    """
    X, Y = grid.centers()
    rows, cols = foreign.shape
    valid = ~np.isnan(top)
    height = np.where(valid, np.nan, np.nan)
    done = ~valid
    lowered = np.zeros(top.shape, bool)
    span = np.where(valid, top - base, 0)
    px = np.clip(np.floor(X).astype(int), 0, cols - 1)
    for dz in np.arange(0.0, float(span.max()) + step, step):
        z = np.maximum(top - dz, base)
        live = ~done
        if not live.any():
            break
        py = np.floor(Y - z).astype(int)
        inside_image = (py >= 0) & (py < rows) & (X >= 0) & (X < cols)
        hit = inside_image & foreign[np.clip(py, 0, rows - 1), px]
        clear = live & ~hit
        height[clear] = z[clear]
        lowered |= clear & (dz > 0)
        done |= clear
        at_base = live & ~clear & (z <= base + 1e-6)
        height[at_base] = base[at_base]
        done |= at_base
    height[~valid] = np.nan
    counts = {'native_columns': int(valid.sum()), 'lowered_columns': int(lowered.sum()),
              'dropped_to_base': int((valid & (height <= base + 1e-6)).sum())}
    return height, counts


def nearness(y_native, z_native):
    """Distance toward the source camera (larger is nearer) of a native point."""
    return y_native / math.tan(math.radians(35)) + z_native * math.tan(math.radians(35))


def zbuffer(depth, owner, tris_world, label, x0, y0):
    """Rasterise world triangles into a source-pixel z-buffer (nearest wins)."""
    h, w = depth.shape
    px = tris_world[..., 0] - x0
    py = -tris_world[..., 1] * SIN35 - tris_world[..., 2] * COS35 - y0
    near = -tris_world[..., 1] * COS35 + tris_world[..., 2] * SIN35
    for k in range(len(tris_world)):
        xs, ys, zs = px[k], py[k], near[k]
        i0, i1 = max(0, int(math.floor(xs.min()))), min(w, int(math.ceil(xs.max())) + 1)
        j0, j1 = max(0, int(math.floor(ys.min()))), min(h, int(math.ceil(ys.max())) + 1)
        if i0 >= i1 or j0 >= j1:
            continue
        det = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
        if abs(det) < 1e-9:
            continue
        gx, gy = np.meshgrid(np.arange(i0, i1) + 0.5, np.arange(j0, j1) + 0.5)
        l1 = ((gx - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (gy - ys[0])) / det
        l2 = ((xs[1] - xs[0]) * (gy - ys[0]) - (gx - xs[0]) * (ys[1] - ys[0])) / det
        l0 = 1 - l1 - l2
        inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
        z = l0 * zs[0] + l1 * zs[1] + l2 * zs[2]
        vd = depth[j0:j1, i0:i1]
        vo = owner[j0:j1, i0:i1]
        upd = inside & (z > vd)
        vd[upd] = z[upd]
        vo[upd] = label


def unhide(grid, heights, inside, base, receiver, depth, x0, y0, step=1.0):
    """Lower columns whose top or front face would stand in front of a neighbour's receiver.

    ``receiver`` marks source pixels (crop origin x0, y0) where the front-most
    neighbour mesh owns the reviewed mask; ``depth`` is that mesh's nearness.
    Every point (x, y, zz) of a column between its base and its top projects
    to pixel (x, y - zz). The column is cut just below the lowest such point
    that is nearer than the neighbour on a receiver pixel, so no part of it
    hides a neighbour's painted receiver. Returns (heights, lowered_columns).
    """
    X, Y = grid.centers()
    h, w = receiver.shape
    valid = inside & ~np.isnan(heights)
    px = np.floor(X - x0).astype(int)
    pxc = np.clip(px, 0, w - 1)
    first_bad = np.full(heights.shape, np.inf)
    top = np.where(valid, heights, -np.inf)
    span = float(np.nanmax(np.where(valid, heights - base, 0))) if valid.any() else 0.0
    for dz in np.arange(0.0, span + step, step):
        zz = base + dz
        live = valid & (zz <= top) & np.isinf(first_bad)
        if not live.any():
            continue
        py = np.floor(Y - zz - y0).astype(int)
        ok = live & (px >= 0) & (px < w) & (py >= 0) & (py < h)
        pyc = np.clip(py, 0, h - 1)
        bad = ok & receiver[pyc, pxc] & (nearness(Y, zz) > depth[pyc, pxc] + 0.5)
        first_bad[bad] = zz[bad] if np.ndim(zz) else zz
    lowered = valid & np.isfinite(first_bad)
    out = np.where(lowered, np.maximum(first_bad - step, base), heights)
    return out, int(lowered.sum())


def break_pinches(inside):
    """Remove one cell of every diagonal-only contact (keeps the outline manifold)."""
    out = inside.copy()
    while True:
        a = out[:-1, :-1]
        b = out[:-1, 1:]
        c = out[1:, :-1]
        d = out[1:, 1:]
        p1 = a & d & ~b & ~c
        p2 = b & c & ~a & ~d
        if not (p1.any() or p2.any()):
            return out
        js, is_ = np.nonzero(p1)
        out[js + 1, is_ + 1] = False
        js, is_ = np.nonzero(p2)
        out[js + 1, is_] = False
