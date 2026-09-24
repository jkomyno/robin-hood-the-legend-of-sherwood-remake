"""Source-coverage audit for one rocks/terrain asset (PROCEDURE section 6).

    /usr/bin/blender --background --threads 2 --python-exit-code 1 \
        --python level-editor/blender/lincoln/rocks_terrain_volumes_audit.py -- --asset <id>

Reopens the saved model.blend and derives the audit domain independently of
the acceptance masks: a first-hit depth raster of every render-visible scene
mesh at the frozen source camera gives the pixels where this asset is the
front surface. Those pixels are then classified against the working masks:

* accepted  - inside the node's include masks and not excluded;
* excluded  - inside a reviewed exclusion (foreground foliage / structure);
* foreign   - outside the node's masks but inside another node's reviewed mask;
* unmasked  - no reviewed native silhouette at all (painted ground, hidden
              faces seen edge-on, or omitted art; explained in the review).

Writes inspection/source-coverage.png (unmarked crop | classification) and
inspection/source-coverage.json. The worker's source-coverage-audit.json is
written by rocks_terrain_volumes_finish.py from these numbers.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rocks_terrain_volumes_core as core  # noqa: E402
from refine_rocks_terrain import ASSETS, ROOT, MaskStore  # noqa: E402

S35, C35 = core.SIN35, core.COS35


def world_tris(obj):
    mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    mesh.calc_loop_triangles()
    mw = obj.matrix_world
    co = np.array([list(mw @ v.co) for v in mesh.vertices]) if len(mesh.vertices) else np.zeros((0, 3))
    idx = np.array([list(t.vertices) for t in mesh.loop_triangles], int).reshape(-1, 3)
    obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
    return co[idx] if len(idx) else np.zeros((0, 3, 3))


def raster(depth, owner, tris, label, x0, y0):
    """Z-buffer rasterise world triangles into source pixels (larger depth = nearer)."""
    h, w = depth.shape
    px = tris[..., 0] - x0
    py = -tris[..., 1] * S35 - tris[..., 2] * C35 - y0
    # Nearness toward the source camera (it looks north and down at 35 deg).
    near = -tris[..., 1] * C35 + tris[..., 2] * S35
    for k in range(len(tris)):
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
        view_d = depth[j0:j1, i0:i1]
        view_o = owner[j0:j1, i0:i1]
        upd = inside & (z > view_d)
        view_d[upd] = z[upd]
        view_o[upd] = label


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--asset', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    workspace = (ASSETS / args.asset).resolve(strict=True)
    config = json.loads((workspace / 'workspace.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(workspace / 'model.blend'))
    scene = bpy.data.scenes[config['scene_name']]
    bpy.context.window.scene = scene
    collection = bpy.data.collections[config['collection_name']]
    meshes = [o for o in collection.all_objects if o.type == 'MESH' and not o.hide_render]
    owned = [o for o in meshes if o.get('asset_group') == args.asset]
    if not owned:
        raise ValueError('No visible owned mesh')
    own_tris = {o['source_node']: world_tris(o) for o in owned}
    allp = np.vstack([t.reshape(-1, 3) for t in own_tris.values()])
    sx = allp[:, 0]
    sy = -allp[:, 1] * S35 - allp[:, 2] * C35
    x0, x1 = max(0, int(sx.min()) - 2), min(2944, int(sx.max()) + 3)
    y0, y1 = max(0, int(sy.min()) - 2), min(2176, int(sy.max()) + 3)
    depth = np.full((y1 - y0, x1 - x0), -np.inf)
    owner = np.zeros((y1 - y0, x1 - x0), int)
    labels = {}
    for obj in meshes:
        b = [obj.matrix_world @ __import__('mathutils').Vector(c) for c in obj.bound_box]
        bx = [p.x for p in b]
        by = [-p.y * S35 - p.z * C35 for p in b]
        if max(bx) < x0 or min(bx) > x1 or max(by) < y0 or min(by) > y1:
            continue
        label = len(labels) + 1
        labels[label] = obj
        tris = own_tris[obj['source_node']] if obj in owned else world_tris(obj)
        raster(depth, owner, tris, label, x0, y0)
    own_labels = {k for k, o in labels.items() if o in owned}
    front = np.isin(owner, list(own_labels))
    silhouette = np.zeros_like(front)
    occluded_by = {}
    for node, tris in own_tris.items():
        d2 = np.full(front.shape, -np.inf)
        o2 = np.zeros(front.shape, int)
        raster(d2, o2, tris, 1, x0, y0)
        mine = o2 > 0
        silhouette |= mine
        hid = mine & ~front
        ids, counts = np.unique(owner[hid], return_counts=True)
        occluded_by[node] = sorted(((int(c), labels[int(i)].get('source_node') or labels[int(i)].name)
                                    for i, c in zip(ids, counts) if i), reverse=True)[:5]
    masks = MaskStore(config['source_mask_manifest'])
    working = json.loads(Path(config['source_mask_manifest']).read_text())
    rows = {r['source_node']: r for r in working['projections']['exterior']['assignments'] if 'source_node' in r}
    accepted = np.zeros_like(front)
    excluded = np.zeros_like(front)
    for label in own_labels:
        node = labels[label]['source_node']
        row = rows[node]
        sel = owner == label
        inc = masks.union([i for i in row['mask_indices'] if i != 428])[y0:y1, x0:x1]
        exc = masks.union(row.get('exclude_mask_indices', []))[y0:y1, x0:x1]
        accepted |= sel & inc & ~exc
        excluded |= sel & inc & exc
    foreign_union = np.zeros(front.shape, bool)
    part_ids = set(config['part_ids'])
    seen = set()
    for node, row in rows.items():
        if node in part_ids:
            continue
        for i in row['mask_indices'] + row.get('exclude_mask_indices', []):
            if i == 428 or i in seen:
                continue
            seen.add(i)
            r = masks.records[i]
            bx, by = r['box_top_left']
            bw, bh = r['box_size']
            if bx > x1 or bx + bw < x0 or by > y1 or by + bh < y0:
                continue
            foreign_union |= masks.get(i)[y0:y1, x0:x1]
    rest = front & ~accepted & ~excluded
    foreign = rest & foreign_union
    unmasked = rest & ~foreign_union
    hidden = silhouette & ~front
    counts = {k: int(v.sum()) for k, v in (('front', front), ('accepted', accepted), ('excluded', excluded),
                                           ('foreign_mask', foreign), ('unmasked', unmasked),
                                           ('hidden_behind_other_meshes', hidden))}
    from PIL import Image
    src = np.array(Image.open(ROOT / 'source-states/covered.png').convert('RGB'))[y0:y1, x0:x1]
    vis = (src * 0.45).astype(np.uint8)
    for sel, col in ((accepted, (0, 230, 230)), (excluded, (230, 0, 230)), (foreign, (240, 200, 0)),
                     (unmasked, (230, 40, 40)), (hidden, (70, 70, 160))):
        vis[sel] = (0.45 * src[sel] + 0.55 * np.array(col)).astype(np.uint8)
    sheet = np.concatenate([src, np.full((src.shape[0], 6, 3), 30, np.uint8), vis], 1)
    image = Image.fromarray(sheet)
    scale = min(1.0, 2000 / image.width)
    if scale < 1:
        image = image.resize((int(image.width * scale), int(image.height * scale)))
    out = workspace / 'inspection'
    out.mkdir(exist_ok=True)
    image.save(out / 'source-coverage.png')
    per_node = {}
    for label in own_labels:
        node = labels[label]['source_node']
        sel = owner == label
        per_node[node] = {'front': int(sel.sum()), 'accepted': int((sel & accepted).sum()),
                          'unmasked': int((sel & unmasked).sum()), 'foreign_mask': int((sel & foreign).sum())}
    report = {'asset_id': args.asset, 'crop': [x0, y0, x1, y1], 'counts': counts, 'per_node': per_node,
              'occluded_by': occluded_by,
              'legend': {'cyan': 'accepted', 'magenta': 'reviewed exclusion (foreground)',
                         'yellow': 'foreign reviewed mask', 'red': 'no reviewed native silhouette',
                         'blue': 'own surface hidden behind another mesh'},
              'model_sha256': hashlib.sha256((workspace / 'model.blend').read_bytes()).hexdigest(),
              'method': 'first-hit z-buffer of all render-visible scene meshes at the frozen source '
                        'camera (pixel = x, y - z), classified against the working masks'}
    (out / 'source-coverage.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'asset': args.asset, **counts}))


if __name__ == '__main__':
    main()
