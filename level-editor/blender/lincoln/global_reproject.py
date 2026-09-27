"""Publication-level source reprojection: nothing source-visible stays neutral gray.

Run from the repository root (Blender, background; never promotes anything):

    # Audit any worker from the exact source camera (read-only):
    blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/global_reproject.py -- audit \
      --worker <worker.blend> --source <covered.png> --output <evidence directory>

    # Fill neutral texels of first-hit surfaces and stage a new worker:
    blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/global_reproject.py -- apply \
      --stage-in <publication-N/stage-vM> --source <covered.png> --output <publication-N/stage-vK>

Per-asset projections are baked inside each workspace against the neighbours of their time,
with strict native-mask ownership. After integration, some source-visible surfaces keep the
neutral "unknown" shading: a later neighbour/terrain change removed the occluder, a mask excluded
art the final geometry actually shows, or no mask covered the pixel. This pass works on the final
scene only:

1. Z-buffer every visible working triangle from the orthographic 35-degree source camera at
   2x2 subsamples per source pixel (depth = plane of the winning triangle, no culling).
2. Grazing reset: texels on triangles with |cos(normal, camera)| < 0.18 are reset to the
   bake's neutral shade even when the per-asset bake accepted them (its floor was 0.05; a mesh's
   reviewed `projection_min_cosine` raises the cutoff, `--grazing-cosine` sets the global one): one
   source pixel smears into long stretched streaks there. They stay unknown for generated fill.
3. Texel pass: every other ownership-atlas texel (island interior and its 2-texel gutter, with
   the bake's clamped positions) that still holds the bake's exact neutral shade and is first-hit
   visible receives the source RGB of its projected pixel, as the bake would have without masks.
4. Pixel pass: every subsample whose first hit is an ownership atlas assigns its pixel's source
   RGB to any still-neutral, non-grazing texel of its bilinear footprint, so the source view
   samples no neutral texel even on silhouettes. Only grazing faces may remain gray there.

Revealed-state copies and patch-only objects (see `covered_state_mesh`) are excluded as occluders and
receivers: they are render-visible in staged workers but absent from the covered artwork.

Masks are deliberately not applied: the requirement is that the source view shows no gray, and
the first-hit surface is what the viewer sees. Non-neutral texels on non-grazing faces (accepted
source, corrections) are byte-preserved; unseen texels stay neutral for synthesis. Geometry, UVs,
material graphs and slot assignments are unchanged; shared images are isolated before edit.
The terrain ground atlas is laid out one texel per source pixel with alpha 0 for unknown; its
unknown texels under first-hit terrain pixels receive exactly their own source pixel.
`apply` writes `<output>/worker.blend`, the stage-in catalog, an `integration.json` bound to the
new worker (with a `global_reprojection` record), `global-reprojection.json` (per-object texel
counts) and `global-reprojection/<object sha>.npz` fill masks (bottom-origin rows; 1 = texel
pass, 2 = pixel pass, 3 = grazing texel reset to neutral) for later generated-texture bakes.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

import numpy as np

ELEVATION = math.radians(35.0)
SIN, COS = math.sin(ELEVATION), math.cos(ELEVATION)
TOWARD = np.array([0.0, -COS, SIN])
LIGHT = np.array([-.35, -.45, .82]) / np.linalg.norm([-.35, -.45, .82])
SS = 2  # subsamples per source pixel along each axis
ASSET_SCOPE = None  # set of asset ids allowed to change (None = all)
MIN_COSINE_OVERRIDES = {}  # asset_id -> reviewed floor not yet carried by the staged meshes
DEPTH_TOLERANCE = 0.02  # world units (= map pixels)
GRAZING_COSINE = 0.18  # below this one source pixel smears over > 5.5 texels (Nottingham precedent)
COLLECTION = 'lincoln Working'
SCENE = 'lincoln Refinement'
OWNERSHIP_LABEL = 'exterior'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def screen(points):
    """World (Z-up) -> source x, top-origin source row coordinate, depth toward camera."""
    return points[..., 0], -(points[..., 1] * SIN + points[..., 2] * COS), points @ TOWARD


def load_source(path):
    from PIL import Image
    image = np.asarray(Image.open(path).convert('RGB'))
    return image  # top-origin rows


STATE_ONLY_KEYS = ('state_recipe', 'state_variant_of', 'reveal_show_when_applied')


def covered_state_mesh(properties):
    """True for geometry present in the covered (source) state.

    Revealed-state copies (`state_recipe`, `state_variant_of`) and objects shown only when a patch is
    applied (`reveal_show_when_applied`) stay render-visible in staged workers for the exporter, but
    are absent from the covered artwork: they must neither occlude nor receive in this pass.
    """
    return not any(properties.get(key) for key in STATE_ONLY_KEYS)


class Scene:
    """Covered-state working meshes as flat triangle arrays with per-slot material bindings."""

    def __init__(self):
        import bpy
        working = bpy.data.collections[COLLECTION]
        visible = [o for o in working.all_objects if o.type == 'MESH' and not o.hide_render]
        self.objects = sorted((o for o in visible if covered_state_mesh(o)), key=lambda o: o.name)
        self.state_only = sorted(o.name for o in visible if not covered_state_mesh(o))
        if any(m.show_render or m.show_viewport for o in self.objects for m in o.modifiers):
            raise ValueError('Apply modifiers before global reprojection')
        points, tri_obj, tri_local = [], [], []
        self.meshes = []
        for index, obj in enumerate(self.objects):
            mesh = obj.data
            mesh.calc_loop_triangles()
            count = len(mesh.vertices)
            co = np.empty(count * 3, dtype=np.float64)
            mesh.vertices.foreach_get('co', co)
            matrix = np.array(obj.matrix_world, dtype=np.float64)
            world = co.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
            triangles = len(mesh.loop_triangles)
            vertices = np.empty(triangles * 3, dtype=np.int32)
            loops = np.empty(triangles * 3, dtype=np.int32)
            polygons = np.empty(triangles, dtype=np.int32)
            slots = np.empty(triangles, dtype=np.int32)
            mesh.loop_triangles.foreach_get('vertices', vertices)
            mesh.loop_triangles.foreach_get('loops', loops)
            mesh.loop_triangles.foreach_get('polygon_index', polygons)
            mesh.loop_triangles.foreach_get('material_index', slots)
            corners = world[vertices.reshape(-1, 3)]
            normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
            length = np.linalg.norm(normals, axis=1)
            normals = normals / np.where(length > 0, length, 1)[:, None]
            face_normals = np.empty(len(mesh.polygons) * 3, dtype=np.float64)
            mesh.polygons.foreach_get('normal', face_normals)
            inverse = np.linalg.inv(matrix[:3, :3]).T
            face_normals = face_normals.reshape(-1, 3) @ inverse.T
            face_normals /= np.maximum(np.linalg.norm(face_normals, axis=1), 1e-12)[:, None]
            self.meshes.append({'object': obj, 'corners': corners, 'loops': loops.reshape(-1, 3),
                                'polygons': polygons, 'slots': slots, 'normals': normals,
                                'face_normals': face_normals})
            points.append(corners)
            tri_obj.append(np.full(triangles, index, dtype=np.int32))
            tri_local.append(np.arange(triangles, dtype=np.int32))
        offset = 0
        for record, local in zip(self.meshes, tri_local):
            record['first'] = offset
            offset += len(local)
        self.corners = np.concatenate(points)
        self.tri_obj = np.concatenate(tri_obj)
        self.tri_local = np.concatenate(tri_local)

    def slot_binding(self, obj, slot):
        """(kind, material, texture node, image, uv layer name) for one material slot."""
        mesh = obj.data
        material = mesh.materials[slot] if slot < len(mesh.materials) else None
        if material is None or material.node_tree is None:
            return None
        textures = [n for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
        if len(textures) != 1:
            return None
        texture = textures[0]
        links = texture.inputs['Vector'].links
        if links and links[0].from_node.type == 'UVMAP':
            uv = links[0].from_node.uv_map
        else:
            uv = next((layer.name for layer in mesh.uv_layers if layer.active_render), None)
        ownership = (material.get('source_ownership_bake') and
                     material.get('source_ownership_label') == OWNERSHIP_LABEL and
                     material.get('source_ownership_fill') == 'neutral')
        return {'kind': 'ownership' if ownership else 'other', 'material': material,
                'texture': texture, 'image': texture.image, 'uv': uv}


def rasterize(scene, width, height):
    """Max-depth triangle id per subsample, plus per-triangle screen depth planes."""
    x, v, d = screen(scene.corners)
    xs, vs = x * SS, v * SS
    area = (xs[:, 1] - xs[:, 0]) * (vs[:, 2] - vs[:, 0]) - (xs[:, 2] - xs[:, 0]) * (vs[:, 1] - vs[:, 0])
    # Depth plane d = a*x + b*v + c in source pixel units, for exact per-point depth tests.
    planes = np.full((len(x), 3), np.nan)
    good = np.abs(area) > 1e-9
    matrix = np.stack([x, v, np.ones_like(x)], axis=2)[good]
    planes[good] = np.linalg.solve(matrix, d[good][..., None])[..., 0]
    W, H = width * SS, height * SS
    depth = np.full((H, W), -np.inf, dtype=np.float64)
    ids = np.full((H, W), -1, dtype=np.int32)
    x0 = np.maximum(0, np.ceil(xs.min(axis=1) - .5)).astype(np.int64)
    x1 = np.minimum(W - 1, np.floor(xs.max(axis=1) - .5)).astype(np.int64)
    y0 = np.maximum(0, np.ceil(vs.min(axis=1) - .5)).astype(np.int64)
    y1 = np.minimum(H - 1, np.floor(vs.max(axis=1) - .5)).astype(np.int64)
    candidates = np.flatnonzero(good & (x1 >= x0) & (y1 >= y0))
    for t in candidates:
        gx = np.arange(x0[t], x1[t] + 1) + .5
        gy = (np.arange(y0[t], y1[t] + 1) + .5)[:, None]
        ax, bx, cx = xs[t]
        ay, by, cy = vs[t]
        inv = 1.0 / area[t]
        w0 = ((bx - gx) * (cy - gy) - (cx - gx) * (by - gy)) * inv
        w1 = ((cx - gx) * (ay - gy) - (ax - gx) * (cy - gy)) * inv
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
        if not inside.any():
            continue
        z = w0 * d[t, 0] + w1 * d[t, 1] + w2 * d[t, 2]
        window = depth[y0[t]:y1[t] + 1, x0[t]:x1[t] + 1]
        take = inside & (z > window)
        window[take] = z[take]
        ids[y0[t]:y1[t] + 1, x0[t]:x1[t] + 1][take] = t
    return ids, planes


def visible(points, ids, planes, width, height):
    """First-hit test of world points against the z-buffer (2x2 nearest subsamples)."""
    x, v, d = screen(points)
    result = np.zeros(len(points), dtype=bool)
    inside = (x >= 0) & (x < width) & (v >= 0) & (v < height)
    fx, fy = x * SS - .5, v * SS - .5
    for ox in (0, 1):
        for oy in (0, 1):
            cx = np.clip(np.floor(fx).astype(np.int64) + ox, 0, width * SS - 1)
            cy = np.clip(np.floor(fy).astype(np.int64) + oy, 0, height * SS - 1)
            t = ids[cy, cx]
            valid = inside & (t >= 0)
            plane = planes[np.maximum(t, 0)]
            front = plane[:, 0] * x + plane[:, 1] * v + plane[:, 2]
            result |= valid & (front <= d + DEPTH_TOLERANCE)
    return result


def neutral_value(normals):
    return .16 + .16 * np.maximum(0, normals @ LIGHT)


def read_image(image):
    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    return np.rint(pixels.reshape(height, width, 4) * 255).astype(np.uint8)


def write_image(image, rgba):
    image.pixels.foreach_set((rgba.astype(np.float32) / 255).ravel())
    image.update()
    image.pack()
    if not np.array_equal(read_image(image), rgba):
        raise RuntimeError('Packed atlas does not round-trip exactly: ' + image.name)


def islands(record, slot_uv, atlas_size, face_filter):
    """Yield (face, texel rows, texel cols, world positions, normals, interior) per atlas island."""
    width, height = atlas_size
    polygons, loops, corners = record['polygons'], record['loops'], record['corners']
    order = np.argsort(polygons, kind='stable')
    boundaries = np.flatnonzero(np.diff(polygons[order])) + 1
    for group in np.split(order, boundaries):
        face = int(polygons[group[0]])
        if not face_filter(group):
            continue
        uv = slot_uv[loops[group]] * [width, height]  # (k,3,2) texel coordinates
        left, right = int(round(uv[..., 0].min())), int(round(uv[..., 0].max()))
        bottom, top = int(round(uv[..., 1].min())), int(round(uv[..., 1].max()))
        cols = np.arange(max(0, left - 2), min(width, right + 2))
        rows = np.arange(max(0, bottom - 2), min(height, top + 2))
        if not len(cols) or not len(rows):
            continue
        gx, gy = np.meshgrid(cols + .5, rows + .5)
        qx, qy = gx.ravel(), gy.ravel()
        best = np.full(len(qx), -np.inf)
        positions = np.zeros((len(qx), 3))
        normals = np.zeros((len(qx), 3))
        for position, local in enumerate(group):
            (ax, ay), (bx, by), (cx, cy) = uv[position]
            det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(det) < 1e-12:
                continue
            wa = ((by - cy) * (qx - cx) + (cx - bx) * (qy - cy)) / det
            wb = ((cy - ay) * (qx - cx) + (ax - cx) * (qy - cy)) / det
            weights = np.stack((wa, wb, 1 - wa - wb), axis=1)
            margin = weights.min(axis=1)
            take = margin > best
            selected = weights[take]
            outside = margin[take] < 0
            selected[outside] = np.maximum(selected[outside], 0)
            selected[outside] /= selected[outside].sum(axis=1, keepdims=True)
            positions[take] = selected @ corners[local]
            normals[take] = record['normals'][local]
            best[take] = margin[take]
        keep = np.isfinite(best)
        yield (face, gy.ravel()[keep].astype(np.int64), gx.ravel()[keep].astype(np.int64),
               positions[keep], normals[keep], best[keep] >= 0)


def slot_uvs(obj, name):
    layer = obj.data.uv_layers[name]
    data = np.empty(len(obj.data.loops) * 2, dtype=np.float64)
    layer.data.foreach_get('uv', data)
    return data.reshape(-1, 2)


def neutral_mask(atlas, rows, cols, normals, face_normal):
    rgb = atlas[rows, cols, :3].astype(np.int16)
    equal = (rgb[:, 0] == rgb[:, 1]) & (rgb[:, 1] == rgb[:, 2]) & (atlas[rows, cols, 3] == 255)
    expected = np.stack([neutral_value(normals), np.full(len(rows), neutral_value(face_normal[None])[0])]) * 255
    return equal & (np.abs(rgb[:, 0] - expected).min(axis=0) <= 1.0)


def sample_subsamples(source_width, record, triangles, cells, binding_uv, atlas):
    """Bilinear texel footprint of subsample centres on the given triangles."""
    height, width = atlas.shape[:2]
    cy, cx = np.divmod(cells, source_width * SS)
    px, pv = (cx + .5) / SS, (cy + .5) / SS
    corners = record['corners'][triangles]
    x, v, _ = screen(corners)
    area = (x[:, 1] - x[:, 0]) * (v[:, 2] - v[:, 0]) - (x[:, 2] - x[:, 0]) * (v[:, 1] - v[:, 0])
    w0 = ((x[:, 1] - px) * (v[:, 2] - pv) - (x[:, 2] - px) * (v[:, 1] - pv)) / area
    w1 = ((x[:, 2] - px) * (v[:, 0] - pv) - (x[:, 0] - px) * (v[:, 2] - pv)) / area
    weights = np.stack([w0, w1, 1 - w0 - w1], axis=1)
    uv = np.einsum('nk,nkj->nj', weights, binding_uv[record['loops'][triangles]])
    fx, fy = uv[:, 0] * width - .5, uv[:, 1] * height - .5
    ix, iy = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    tx, ty = fx - ix, fy - iy
    footprint = []
    for ox, oy, weight in ((0, 0, (1 - tx) * (1 - ty)), (1, 0, tx * (1 - ty)),
                           (0, 1, (1 - tx) * ty), (1, 1, tx * ty)):
        footprint.append((np.clip(iy + oy, 0, height - 1), np.clip(ix + ox, 0, width - 1), weight))
    return footprint


class Pass:
    """One source-camera pass over the worker: audit rendering and (optionally) the fill."""

    def __init__(self, source):
        self.source = source
        self.height, self.width = source.shape[:2]
        self.scene = Scene()
        print(f'Global reprojection: {len(self.scene.objects)} meshes, {len(self.scene.tri_obj)} triangles',
              flush=True)
        self.ids, self.planes = rasterize(self.scene, self.width, self.height)
        print('Global reprojection: z-buffer done', flush=True)
        flat = self.ids.ravel()
        self.cells = np.flatnonzero(flat >= 0)
        self.cell_tri = flat[self.cells]
        self.cell_obj = self.scene.tri_obj[self.cell_tri]
        order = np.argsort(self.cell_obj, kind='stable')
        self.cells, self.cell_tri, self.cell_obj = self.cells[order], self.cell_tri[order], self.cell_obj[order]
        self.obj_ranges = np.searchsorted(self.cell_obj, np.arange(len(self.scene.objects) + 1))

    def source_rgb(self, cells):
        cy, cx = np.divmod(cells, self.width * SS)
        return self.source[cy // SS, cx // SS]

    def run(self, apply_fill, fill_directory=None):
        H, W = self.height * SS, self.width * SS
        render = {'before': np.zeros((H * W, 3), dtype=np.uint8), 'after': np.zeros((H * W, 3), dtype=np.uint8)}
        gray = {'before': np.zeros(H * W, dtype=bool), 'after': np.zeros(H * W, dtype=bool)}
        cosine = np.zeros(H * W, dtype=np.float16)
        kind = np.zeros(H * W, dtype=np.uint8)  # 0 background, 1 ownership atlas, 2 other material
        image_users = {}
        for record in self.scene.meshes:
            obj = record['object']
            for slot in np.unique(record['slots']):
                binding = self.scene.slot_binding(obj, int(slot))
                if binding and binding['kind'] == 'ownership':
                    image_users.setdefault(binding['image'].name, set()).add((obj.name, int(slot)))
        rows = []
        for index, record in enumerate(self.scene.meshes):
            obj = record['object']
            span = slice(self.obj_ranges[index], self.obj_ranges[index + 1])
            cells, tris = self.cells[span], self.cell_tri[span] - record['first']
            cosine[cells] = record['normals'][tris] @ TOWARD
            row = {'object': obj.name, 'source_node': obj.get('source_node'), 'asset_group': obj.get('asset_group'),
                   'projection_component': obj.get('projection_component'), 'slots': []}
            fill_record = {}
            # --assets limits every texel change to the named assets; the rest is audited only.
            apply_here = apply_fill and (ASSET_SCOPE is None or obj.get('asset_group') in ASSET_SCOPE)
            for slot in np.unique(record['slots']):
                slot = int(slot)
                binding = self.scene.slot_binding(obj, slot)
                on_slot = record['slots'][tris] == slot
                slot_cells, slot_tris = cells[on_slot], tris[on_slot]
                if binding is None:
                    kind[slot_cells] = 2
                    row['slots'].append({'slot': slot, 'kind': 'untextured', 'visible_subsamples': int(len(slot_cells))})
                    continue
                image = binding['image']
                atlas = read_image(image)
                uv = slot_uvs(obj, binding['uv'])
                footprint = sample_subsamples(self.width, record, slot_tris, slot_cells, uv, atlas)
                color = sum(atlas[r, c, :3].astype(np.float64) * w[:, None] for r, c, w in footprint)
                render['before'][slot_cells] = np.clip(np.rint(color), 0, 255)
                render['after'][slot_cells] = render['before'][slot_cells]
                if binding['kind'] != 'ownership':
                    kind[slot_cells] = 2
                    row['slots'].append({'slot': slot, 'kind': 'other', 'material': binding['material'].name,
                                         'visible_subsamples': int(len(slot_cells))})
                    continue
                kind[slot_cells] = 1
                neutral = np.zeros(atlas.shape[:2], dtype=bool)
                on_island = np.zeros(atlas.shape[:2], dtype=bool)
                interior = np.zeros(atlas.shape[:2], dtype=bool)
                fill = np.zeros(atlas.shape[:2], dtype=np.uint8)
                grazing_map = np.zeros(atlas.shape[:2], dtype=bool)
                new = atlas.copy()
                slot_faces = record['slots'] == slot
                texel_candidates = 0
                # A reviewed per-mesh cutoff (as honoured by the per-asset bake) can only raise the floor.
                floor = max(GRAZING_COSINE, float(obj.get('projection_min_cosine', 0.0)),
                            MIN_COSINE_OVERRIDES.get(obj.get('asset_group'), 0.0))
                # The terrain stores one texel per source pixel along the camera ray (UV = source
                # projection, rows bottom-origin) with alpha 0 marking unknown texels.
                projected = obj.get('source_node') == 'ground' and atlas.shape[:2] == (self.height, self.width)
                if projected:
                    neutral = atlas[:, :, 3] == 0
                    on_island[:] = interior[:] = True
                    if apply_here:
                        cy, cx = np.divmod(slot_cells, self.width * SS)
                        seen = np.zeros(atlas.shape[:2], dtype=bool)
                        seen[self.height - 1 - cy // SS, cx // SS] = True
                        for r, c, w in footprint:
                            seen[r[w > 1e-6], c[w > 1e-6]] = True
                        take = seen & neutral
                        texel_candidates = int(neutral.sum())
                        new[take, :3] = self.source[::-1][take]
                        new[take, 3] = 255
                        fill[take] = 1
                for face, ty, tx, positions, normals, inner in () if projected else islands(
                        record, uv, (atlas.shape[1], atlas.shape[0]), lambda group: slot_faces[group[0]]):
                    mask = neutral_mask(atlas, ty, tx, normals, record['face_normals'][face])
                    neutral[ty, tx] = mask
                    on_island[ty, tx] = True
                    interior[ty, tx] |= inner
                    if not apply_here:
                        continue
                    grazing = np.abs(normals @ TOWARD) < floor
                    grazing_map[ty, tx] = grazing
                    reset = grazing & ~mask
                    if reset.any():
                        new[ty[reset], tx[reset], :3] = np.rint(neutral_value(normals[reset]) * 255)[:, None]
                        new[ty[reset], tx[reset], 3] = 255
                        fill[ty[reset], tx[reset]] = 3
                    candidate = mask & ~grazing
                    texel_candidates += int(candidate.sum())
                    if not candidate.any():
                        continue
                    seen = visible(positions[candidate], self.ids, self.planes, self.width, self.height)
                    if not seen.any():
                        continue
                    x, v, _ = screen(positions[candidate][seen])
                    sx = np.clip(np.floor(x).astype(np.int64), 0, self.width - 1)
                    sv = np.clip(np.floor(v).astype(np.int64), 0, self.height - 1)
                    fy, fx = ty[candidate][seen], tx[candidate][seen]
                    new[fy, fx, :3] = self.source[sv, sx]
                    new[fy, fx, 3] = 255
                    fill[fy, fx] = 1
                gray_before = np.zeros(len(slot_cells), dtype=bool)
                for r, c, w in footprint:
                    gray_before |= neutral[r, c] & (w > 1e-6)
                gray['before'][slot_cells] = gray_before
                pixel_filled = 0
                if apply_here:
                    remaining = neutral & (fill == 0) & ~grazing_map
                    total = np.zeros(atlas.shape[:2] + (3,), dtype=np.float64)
                    count = np.zeros(atlas.shape[:2], dtype=np.int64)
                    rgb = self.source_rgb(slot_cells).astype(np.float64)
                    for r, c, w in footprint:
                        claim = remaining[r, c] & (w > 1e-6)
                        np.add.at(total, (r[claim], c[claim]), rgb[claim])
                        np.add.at(count, (r[claim], c[claim]), 1)
                    claimed = count > 0
                    new[claimed, :3] = np.rint(total[claimed] / count[claimed, None]).astype(np.uint8)
                    new[claimed, 3] = 255
                    fill[claimed] = 2
                    pixel_filled = int(claimed.sum())
                    changed = fill > 0
                    if not np.array_equal(new[~changed], atlas[~changed]) or np.any((fill == 1) & ~neutral) \
                            or np.any((fill == 2) & ~neutral) or np.any((fill == 3) & neutral):
                        raise RuntimeError('Fill touched a texel outside its class: ' + obj.name)
                    unknown_after = (neutral & (fill == 0)) | (fill == 3)
                    after_color = sum(new[r, c, :3].astype(np.float64) * w[:, None] for r, c, w in footprint)
                    render['after'][slot_cells] = np.clip(np.rint(after_color), 0, 255)
                    gray_after = np.zeros(len(slot_cells), dtype=bool)
                    for r, c, w in footprint:
                        gray_after |= unknown_after[r, c] & (w > 1e-6)
                    gray['after'][slot_cells] = gray_after
                    if changed.any():
                        material, texture = binding['material'], binding['texture']
                        if material.users > 1:
                            material = material.copy()
                            obj.data.materials[slot] = material
                            texture = next(n for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
                        if len(image_users[image.name]) > 1 or image.users > 1:
                            users = image_users.pop(image.name)
                            image = image.copy()
                            image.name = obj.name + ' / globally reprojected ' + OWNERSHIP_LABEL
                            texture.image = image
                            users.discard((obj.name, slot))
                            if users:
                                image_users[binding['image'].name] = users
                        write_image(image, new)
                        material['global_source_reprojection'] = json.dumps(
                            {'texel_pass': int((fill == 1).sum()), 'pixel_pass': pixel_filled,
                             'grazing_reset': int((fill == 3).sum()), 'grazing_cosine': GRAZING_COSINE,
                             'semantics': 'neutral texels of first-hit source-visible surfaces set to source RGB; '
                                          'grazing texels reset to neutral'},
                            sort_keys=True)
                        if fill_directory is not None:
                            path = Path(fill_directory) / (hashlib.sha256(
                                (obj.name + '\0' + str(slot)).encode()).hexdigest()[:20] + '.npz')
                            np.savez_compressed(path, fill=fill)
                            fill_record = {'path': str(path.resolve()), 'sha256': sha(path)}
                else:
                    gray['after'][slot_cells] = gray_before
                    unknown_after = neutral
                row['slots'].append({
                    'slot': slot, 'kind': 'ownership', 'layout': 'source-projected' if projected else 'face-islands', 'material': binding['material'].name,
                    'image': image.name, 'atlas_size': [atlas.shape[1], atlas.shape[0]],
                    'visible_subsamples': int(len(slot_cells)),
                    'gray_subsamples_before': int(gray_before.sum()),
                    'gray_subsamples_after': int(gray['after'][slot_cells].sum()),
                    'island_texels': int(on_island.sum()), 'interior_texels': int(interior.sum()),
                    'neutral_texels_before': int(neutral.sum()),
                    'neutral_interior_texels_before': int((neutral & interior).sum()),
                    'texel_pass_candidates': texel_candidates,
                    'texels_filled_texel_pass': int((fill == 1).sum()),
                    'texels_filled_pixel_pass': int((fill == 2).sum()),
                    'texels_reset_grazing': int((fill == 3).sum()),
                    'interior_texels_filled': int((((fill == 1) | (fill == 2)) & interior).sum()),
                    'interior_texels_reset_grazing': int(((fill == 3) & interior).sum()),
                    'neutral_texels_after': int(unknown_after.sum()),
                    'fill_mask': fill_record or None})
            rows.append(row)
            if index % 50 == 0:
                print(f'Global reprojection: object {index + 1}/{len(self.scene.meshes)}', flush=True)
        return rows, render, gray, cosine, kind


def save_evidence(directory, width, height, render, gray, cosine, kind, pass_):
    from PIL import Image
    directory.mkdir(parents=True, exist_ok=True)
    H, W = height * SS, width * SS
    for key in ('before', 'after'):
        image = render[key].reshape(H, W, 3).reshape(height, SS, width, SS, 3).mean(axis=(1, 3))
        Image.fromarray(np.rint(image).astype(np.uint8)).save(directory / f'render-{key}.png')
        mask = gray[key].reshape(height, SS, width, SS).any(axis=(1, 3))
        overlay = np.rint(image * .45).astype(np.uint8)
        overlay[mask] = (255, 0, 255)
        Image.fromarray(overlay).save(directory / f'gray-{key}.png')
    np.savez_compressed(directory / 'subsamples.npz', object=np.where(
        pass_.ids >= 0, pass_.scene.tri_obj[np.maximum(pass_.ids, 0)], -1).astype(np.int16),
        gray_before=gray['before'].reshape(H, W), gray_after=gray['after'].reshape(H, W),
        cosine=cosine.reshape(H, W), kind=kind.reshape(H, W))
    (directory / 'objects.json').write_text(json.dumps(
        [{'index': i, 'object': o.name, 'source_node': o.get('source_node'), 'asset_group': o.get('asset_group'),
          'projection_component': o.get('projection_component')} for i, o in enumerate(pass_.scene.objects)],
        indent=1) + '\n')


def pixel_counts(gray, kind, cosine, width, height):
    geometry = (kind.reshape(height, SS, width, SS) > 0).any(axis=(1, 3))
    grazing = np.abs(cosine.astype(np.float32)) < GRAZING_COSINE
    out = {}
    for key in ('before', 'after'):
        cells = gray[key].reshape(height, SS, width, SS)
        steep = (gray[key] & ~grazing).reshape(height, SS, width, SS)
        out[key] = {'gray_pixels_any_subsample': int(cells.any(axis=(1, 3)).sum()),
                    'gray_pixels_all_subsamples': int(cells.all(axis=(1, 3)).sum()),
                    'gray_subsamples': int(gray[key].sum()),
                    'gray_pixels_non_grazing': int(steep.any(axis=(1, 3)).sum()),
                    'gray_pixels_only_grazing': int((cells.any(axis=(1, 3)) & ~steep.any(axis=(1, 3))).sum())}
    out['geometry_pixels'] = int(geometry.sum())
    return out


def main(argv):
    global GRAZING_COSINE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('audit', 'apply'))
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--stage-in', type=Path)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--grazing-cosine', type=float, default=GRAZING_COSINE,
                        help='Global grazing floor; per-mesh projection_min_cosine can raise it')
    parser.add_argument('--assets', nargs='+', help='Only change texels of these asset ids (others are audited only)')
    parser.add_argument('--min-cosine-override', action='append', default=[], metavar='ASSET=COSINE',
                        help='Per-asset floor for a projection_min_cosine not yet in the staged worker')
    args = parser.parse_args(argv)
    GRAZING_COSINE = args.grazing_cosine
    global ASSET_SCOPE
    ASSET_SCOPE = set(args.assets) if args.assets else None
    for item in args.min_cosine_override:
        asset, value = item.split('=')
        MIN_COSINE_OVERRIDES[asset] = float(value)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from render_slots import acquire
    acquire()
    import bpy
    source_path = args.source.resolve(strict=True)
    source = load_source(source_path)
    output = args.output.resolve()
    if args.mode == 'audit':
        worker = args.worker.resolve(strict=True)
        output.mkdir(parents=True, exist_ok=True)
    else:
        stage_in = args.stage_in.resolve(strict=True)
        worker = stage_in / 'worker.blend'
        integration = json.loads((stage_in / 'integration.json').read_text())
        if sha(worker) != integration['worker_sha256']:
            raise ValueError('Stage-in worker changed after integration')
        output.mkdir(parents=True, exist_ok=False)
    worker_sha = sha(worker)
    bpy.ops.wm.open_mainfile(filepath=str(worker))
    bpy.context.window.scene = bpy.data.scenes[SCENE]
    pass_ = Pass(source)
    unknown = set(MIN_COSINE_OVERRIDES) - {o.get('asset_group') for o in pass_.scene.objects}
    if unknown:
        raise ValueError('Min-cosine override names no staged asset: ' + repr(sorted(unknown)))
    fill_directory = output / 'global-reprojection' if args.mode == 'apply' else None
    if fill_directory:
        fill_directory.mkdir()
    geometry_before = {record['object'].name: hashlib.sha256(record['corners'].tobytes()).hexdigest()
                       for record in pass_.scene.meshes}
    rows, render, gray, cosine, kind = pass_.run(args.mode == 'apply', fill_directory)
    evidence = output / ('global-reprojection-evidence' if args.mode == 'apply' else '')
    save_evidence(evidence, pass_.width, pass_.height, render, gray, cosine, kind, pass_)
    report = {'version': 1, 'mode': args.mode, 'worker': str(worker), 'worker_sha256': worker_sha,
              'source': str(source_path), 'source_sha256': sha(source_path),
              'camera': {'elevation_deg': 35.0, 'projection': 'orthographic; x = world x, '
                         'top row = -(y sin + z cos), depth = -y cos + z sin', 'subsamples': SS,
                         'depth_tolerance': DEPTH_TOLERANCE, 'grazing_cosine': GRAZING_COSINE,
                         'min_cosine_overrides': MIN_COSINE_OVERRIDES,
                         'asset_scope': sorted(ASSET_SCOPE) if ASSET_SCOPE else None},
              'counts': pixel_counts(gray, kind, cosine, pass_.width, pass_.height),
              'state_only_objects_excluded': pass_.scene.state_only,
              'objects': rows, 'evidence': str(evidence)}
    if args.mode == 'apply':
        after = Scene()
        if {r['object'].name: hashlib.sha256(r['corners'].tobytes()).hexdigest() for r in after.meshes} != geometry_before:
            raise RuntimeError('Geometry changed during global reprojection')
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(output / 'worker.blend'))
        shutil.copyfile(stage_in / 'catalog.json', output / 'catalog.json')
        slots = [s for row in rows for s in row['slots'] if s['kind'] == 'ownership']
        report['totals'] = {key: sum(s[key] for s in slots) for key in (
            'neutral_texels_before', 'texels_filled_texel_pass', 'texels_filled_pixel_pass',
            'interior_texels_filled', 'texels_reset_grazing', 'interior_texels_reset_grazing',
            'neutral_texels_after')}
        report['per_asset'] = {}
        for row in rows:
            asset = report['per_asset'].setdefault(row['asset_group'] or row['object'],
                                                   {'texels_filled': 0, 'interior_texels_filled': 0,
                                                    'texels_reset_grazing': 0, 'interior_texels_reset_grazing': 0,
                                                    'gray_subsamples_before': 0, 'gray_subsamples_after': 0})
            for s in row['slots']:
                if s['kind'] == 'ownership':
                    asset['texels_filled'] += s['texels_filled_texel_pass'] + s['texels_filled_pixel_pass']
                    asset['interior_texels_filled'] += s['interior_texels_filled']
                    asset['texels_reset_grazing'] += s['texels_reset_grazing']
                    asset['interior_texels_reset_grazing'] += s['interior_texels_reset_grazing']
                    asset['gray_subsamples_before'] += s['gray_subsamples_before']
                    asset['gray_subsamples_after'] += s['gray_subsamples_after']
        report['stage_in'] = str(stage_in)
        report['output_worker'] = str(output / 'worker.blend')
        report['output_worker_sha256'] = sha(output / 'worker.blend')
        report_path = output / 'global-reprojection.json'
        report_path.write_text(json.dumps(report, indent=1) + '\n')
        staged = dict(integration)
        staged['worker'] = str(output / 'worker.blend')
        staged['worker_sha256'] = report['output_worker_sha256']
        staged['staged_catalog'] = str(output / 'catalog.json')
        staged['global_reprojection'] = {
            'stage_in': str(stage_in), 'stage_in_worker_sha256': worker_sha,
            'script': str(Path(__file__).resolve()), 'script_sha256': sha(__file__),
            'report': str(report_path), 'report_sha256': sha(report_path), 'totals': report['totals'],
            'semantics': 'Publication-level material fix: neutral texels of first-hit source-visible '
                         'surfaces set to source RGB; approved per-asset models are unchanged.'}
        staged['scope'] = integration['scope'] + ' Globally reprojected for source-view completeness.'
        (output / 'integration.json').write_text(json.dumps(staged, indent=2) + '\n')
    else:
        (output / 'audit.json').write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps({'mode': args.mode, 'counts': report['counts'], 'totals': report.get('totals')}), flush=True)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1:])
