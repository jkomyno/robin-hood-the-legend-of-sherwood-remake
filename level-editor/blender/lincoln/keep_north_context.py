"""Neighbour-contact renders of a keep_north workspace (diagnostic, no source pixels).

  /usr/bin/blender --background --threads 2 --python-exit-code 1 \
      --python level-editor/blender/lincoln/keep_north_context.py -- --asset <id> --assets-dir <dir>

Orthographic BVH ray casts at 35 degrees elevation from four azimuths over all
visible working meshes.  Owned meshes are tinted orange, neighbours gray, so
contacts, gaps and interpenetration with the refined neighbours are visible.
Writes inspection/neighbour-context.png.
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SUN = Vector((0.5712401270866394, -0.3459553122520447, 0.7443115711212158)).normalized()


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', required=True)
    ap.add_argument('--assets-dir', required=True)
    ap.add_argument('--pixels', type=int, default=420)
    args = ap.parse_args(argv)
    ws = Path(args.assets_dir) / args.asset
    from render_slots import acquire
    acquire()
    bpy.ops.wm.open_mainfile(filepath=str(ws / 'model.blend'))
    verts, tris, own = [], [], []
    opts = []
    for obj in bpy.data.collections['lincoln Working'].all_objects:
        if obj.type != 'MESH' or obj.hide_render:
            continue
        mine = obj.get('asset_group') == args.asset
        off = len(verts)
        verts.extend(obj.matrix_world @ v.co for v in obj.data.vertices)
        obj.data.calc_loop_triangles()
        for t in obj.data.loop_triangles:
            tris.append(tuple(off + i for i in t.vertices))
            own.append(mine)
        if mine:
            opts.extend(verts[off:])
    tree = BVHTree.FromPolygons(verts, tris, all_triangles=True)
    lo = Vector([min(p[i] for p in opts) for i in range(3)])
    hi = Vector([max(p[i] for p in opts) for i in range(3)])
    centre = (lo + hi) / 2
    radius = (hi - lo).length / 2 * 1.35
    elev = math.radians(35)
    tiles = []
    N = args.pixels
    for az in (0, 90, 180, 270):
        a = math.radians(az)
        # camera looks from the south (az 0) toward north, rotating clockwise
        fwd = Vector((math.sin(a) * math.cos(elev), math.cos(a) * math.cos(elev), -math.sin(elev)))
        right = Vector((math.cos(a), -math.sin(a), 0))
        up = right.cross(fwd).normalized()
        img = np.zeros((N, N, 3), np.uint8)
        for j in range(N):
            for i in range(N):
                u = (i + .5) / N * 2 - 1
                v = 1 - (j + .5) / N * 2
                origin = centre + right * u * radius + up * v * radius - fwd * 20000
                hit, normal, idx, _ = tree.ray_cast(origin, fwd)
                if hit is None:
                    img[j, i] = (20, 20, 30)
                    continue
                if normal.dot(fwd) > 0:
                    normal = -normal
                g = 0.25 + 0.7 * max(0.0, normal.dot(SUN))
                img[j, i] = (int(255 * g), int(150 * g), int(60 * g)) if own[idx] else (int(200 * g),) * 3
        tiles.append(img)
    sheet = np.concatenate(tiles, 1)
    from PIL import Image
    out = ws / 'inspection/neighbour-context.png'
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(sheet).save(out)
    print(out)


if __name__ == '__main__':
    main()
