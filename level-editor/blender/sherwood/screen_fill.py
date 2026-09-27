"""Recover generated colors at visible fragments missed by atlas-center sampling."""
import numpy as np


def fill_visible_fragments(target, cameras, sheet, solid, editable, raster, gr, ss, minimum_cosine):
    atlases = [gr.read_image(image) for image in target.images]
    eligible = [(kind.mask == 0) & ((atlas[..., 3] >= 128) if kind.physical else True)
                if kind else np.zeros(atlas.shape[:2], bool)
                for kind, atlas in zip(target.image_kind, atlases)]
    scores = [np.full(atlas.shape[:2], -np.inf, np.float32) for atlas in atlases]
    protected = [atlas[~mask].copy() for atlas, mask in zip(atlases, eligible)]
    alphas = [atlas[..., 3].copy() for atlas in atlases]
    for camera, _ in cameras:
        _, index, (xs, ys) = raster(camera, target.corners, ss)
        gy, gx = np.nonzero(index >= 0)
        triangles = index[gy, gx]
        angle = np.abs(target.normals[triangles] @ camera.toward)
        sy, sx = gy//ss+camera.top, gx//ss+camera.left
        take = target.receiver_tri[triangles] & (angle >= minimum_cosine) & solid[sy, sx] & editable[sy, sx]
        gy, gx, triangles, angle, sy, sx = [a[take] for a in (gy, gx, triangles, angle, sy, sx)]
        if not len(triangles):
            continue
        (ax, bx, cx), (ay, by, cy) = xs[triangles].T, ys[triangles].T
        px, py = gx+.5, gy+.5
        area = (bx-ax)*(cy-ay)-(cx-ax)*(by-ay)
        wa = ((bx-px)*(cy-py)-(cx-px)*(by-py))/area
        wb = ((cx-px)*(ay-py)-(ax-px)*(cy-py))/area
        weights = np.stack((wa, wb, 1-wa-wb), axis=1).clip(0, 1)
        weights /= weights.sum(1, keepdims=True)
        uv = np.einsum('nk,nkj->nj', weights, target.tri_uv[triangles])
        in_region = np.ones(len(triangles), bool)
        if target.region:
            world = np.einsum('nk,nkj->nj', weights, target.corners[triangles])
            r = target.region
            in_region = (~target.tri_ground[triangles] |
                         ((world[:, 0] >= r['x'][0]) & (world[:, 0] <= r['x'][1]) &
                          (world[:, 1] >= r['y'][0]) & (world[:, 1] <= r['y'][1])))
        images = target.tri_image[triangles]
        for image_id in np.unique(images[images >= 0]):
            if not target.image_kind[image_id]:
                continue
            picked = np.flatnonzero((images == image_id) & in_region)
            atlas = atlases[image_id]; height, width = atlas.shape[:2]
            xy = uv[picked]*[width, height]
            cols = np.floor(xy[:, 0]).astype(int).clip(0, width-1)
            rows = np.floor(xy[:, 1]).astype(int).clip(0, height-1)
            valid = eligible[image_id][rows, cols]
            picked, xy, rows, cols = [a[valid] for a in (picked, xy, rows, cols)]
            if not len(picked):
                continue
            # Most facing view wins; for a tie choose the fragment nearest the
            # atlas center. Never average incompatible generated details.
            quality = angle[picked]-np.minimum(((xy-[.5, .5]-np.stack((cols, rows), axis=1))**2).sum(1), 1)*1e-4
            flat = rows*width+cols
            order = np.lexsort((-quality, flat))
            unique = order[np.r_[True, np.diff(flat[order]) != 0]]
            picked, rows, cols, quality = [a[unique] for a in (picked, rows, cols, quality)]
            improve = quality > scores[image_id][rows, cols]
            picked, rows, cols, quality = [a[improve] for a in (picked, rows, cols, quality)]
            atlas[rows, cols, :3] = sheet[sy[picked], sx[picked], :3]
            scores[image_id][rows, cols] = quality
    changed = {}
    for image, kind, atlas, mask, score, locked, alpha in zip(
            target.images, target.image_kind, atlases, eligible, scores, protected, alphas):
        filled = np.isfinite(score)
        if not filled.any():
            continue
        assert np.array_equal(atlas[~mask], locked), image.name
        assert np.array_equal(atlas[..., 3], alpha), image.name
        kind.mask[filled] = 2
        if not kind.physical:
            atlas[filled, 3] = 0
        gr.write_image(image, atlas)
        changed[image.name] = int(filled.sum())
    return changed
