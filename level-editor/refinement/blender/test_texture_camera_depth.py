import unittest

from texture_camera import depth_clip_range


class CameraDepthTests(unittest.TestCase):
    def test_distant_asset_keeps_front_and_rear_without_huge_depth_range(self):
        near, far = depth_clip_range([9800, 9900, 10200])
        self.assertLess(near, 9800)
        self.assertGreater(far, 10200)
        self.assertLess(far - near, 500)

    def test_flat_surface_still_has_nonzero_margin(self):
        near, far = depth_clip_range([10000, 10000])
        self.assertLess(near, 10000)
        self.assertGreater(far, 10000)

    def test_geometry_crossing_camera_uses_positive_near_plane(self):
        near, far = depth_clip_range([-2, 20])
        self.assertGreater(near, 0)
        self.assertGreater(far, 20)

    def test_invalid_or_entirely_rear_geometry_fails(self):
        for depths in ([], [float('nan')], [float('inf')], [-10, -1]):
            with self.subTest(depths=depths), self.assertRaises(ValueError):
                depth_clip_range(depths)


if __name__ == '__main__':
    unittest.main()
