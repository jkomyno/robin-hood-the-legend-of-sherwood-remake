"""Blender regression: a successful Pack Islands operator can return an invalid atlas.

Run: blender --background --threads 2 --python-exit-code 1 \
       --python refinement/blender/test_uv_packing.py
"""
from pathlib import Path
import sys
import unittest

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lossy_assets as assets
from render_slots import acquire


class PackingTest(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
        vertices, faces = [], []
        # Disconnected cards, each split into two triangles as in published GLBs.
        for i in range(400):
            x, y = (i % 20) * 2, (i // 20) * 2
            start = len(vertices)
            vertices.extend([(x, y, 0), (x + 1, y, 0), (x + 1, y + 1, 0), (x, y + 1, 0)])
            faces.extend([(start, start + 1, start + 2), (start, start + 2, start + 3)])
        mesh = bpy.data.meshes.new('cards')
        mesh.from_pydata(vertices, [], faces)
        self.obj = bpy.data.objects.new('cards', mesh)
        bpy.context.scene.collection.objects.link(self.obj)
        self.obj.select_set(True)
        bpy.context.view_layer.objects.active = self.obj
        self.uv = np.tile(np.array([0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1], dtype=np.float32), 400)
        for name in (assets.SOURCE_UV, assets.NEW_UV):
            layer = mesh.uv_layers.new(name=name)
            layer.uv.foreach_set('vector', self.uv)
        mesh.uv_layers.active = layer

    def pack(self, margin):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.select_all(action='SELECT')
        result = bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True,
                                      rotate_method='ANY', scale=True, margin_method='FRACTION',
                                      margin=margin, shape_method='AABB')
        bpy.ops.object.mode_set(mode='OBJECT')
        self.assertEqual(result, {'FINISHED'})

    def test_impossible_padding_is_rejected_despite_operator_success(self):
        # Padding alone requires 400 * (2 * .05)^2 = four atlas tiles.
        self.pack(.05)
        with self.assertRaises(assets.UnsafeAtlasError):
            assets.check_packed_objects([self.obj])

    def test_feasible_padding_preserves_triangles(self):
        self.pack(.005)
        assets.check_packed_objects([self.obj])


if __name__ == '__main__':
    acquire()
    unittest.main(argv=[sys.argv[0]])
