"""Compare bake coordinates to Blender's real camera frame for every aspect."""
import sys
import unittest
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from texture_camera import orthographic_extents


class TextureCameraTests(unittest.TestCase):
    def test_default_camera_frame_and_pixel_centers(self):
        scene = bpy.context.scene
        camera = bpy.data.cameras.new('Texture coordinate fixture')
        camera.type = 'ORTHO'
        camera.ortho_scale = 20
        scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
        for width, height in [(384, 256), (256, 384), (256, 256)]:
            with self.subTest(size=(width, height)):
                scene.render.resolution_x, scene.render.resolution_y = width, height
                frame = camera.view_frame(scene=scene)
                left, right = min(v.x for v in frame), max(v.x for v in frame)
                bottom, top = min(v.y for v in frame), max(v.y for v in frame)
                horizontal, vertical = orthographic_extents({'crop': {'width': width, 'height': height}, 'ortho_scale': 20})
                self.assertAlmostEqual(horizontal, right-left, places=5)
                self.assertAlmostEqual(vertical, top-bottom, places=5)
                for px, py in [(0, 0), (width-1, height-1), (width//3, height//3)]:
                    x = left+(px+.5)*(right-left)/width
                    y = bottom+(py+.5)*(top-bottom)/height
                    self.assertAlmostEqual((.5+x/horizontal)*width, px+.5, places=4)
                    self.assertAlmostEqual((.5+y/vertical)*height, py+.5, places=4)
        bpy.data.cameras.remove(camera)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TextureCameraTests))
    if not result.wasSuccessful():
        raise RuntimeError('Texture camera regression failed')
