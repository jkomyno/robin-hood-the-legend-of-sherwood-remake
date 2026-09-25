"""Full-map source-camera first-hit label map of an integrated Lincoln scene.

    /usr/bin/blender --background <scene.blend> --threads 2 --python-exit-code 1 \
        --python level-editor/blender/lincoln/rocks_terrain_volumes_firsthit.py -- <out.npz>

Writes ``label`` (int32, 2176x2944, 0 = no mesh), ``depth`` (nearness toward
the source camera) and ``names`` (source_node per label, index 0 = '') for
every render-visible mesh of the working collection. Pixel convention: native
(x, y, z) projects to (x, y - z); pixel centres are sampled.
"""
import sys
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rocks_terrain_volumes_core as core  # noqa: E402


def main():
    out = sys.argv[sys.argv.index('--') + 1]
    collection = next(c for c in bpy.data.collections if c.name.endswith(' Working'))
    depth = np.full((2176, 2944), -np.inf)
    label = np.zeros((2176, 2944), np.int32)
    names = ['']
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in collection.all_objects:
        if obj.type != 'MESH' or obj.hide_render:
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        mesh.calc_loop_triangles()
        mw = obj.matrix_world
        co = np.array([list(mw @ v.co) for v in mesh.vertices])
        idx = np.array([list(t.vertices) for t in mesh.loop_triangles], int).reshape(-1, 3)
        evaluated.to_mesh_clear()
        if not len(idx):
            continue
        names.append(obj.get('source_node') or obj.name)
        core.zbuffer(depth, label, co[idx], len(names) - 1, 0, 0)
    np.savez_compressed(out, label=label, depth=depth, names=np.array(names, object))
    print('labels', len(names) - 1, 'covered px', int((label > 0).sum()))


if __name__ == '__main__':
    main()
