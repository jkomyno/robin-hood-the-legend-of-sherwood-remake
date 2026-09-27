"""Cutaway interpolation, holes, winding, and edge-on retained surfaces."""
import unittest
import numpy as np
from shapely import Polygon, box, union_all
from derby_interior_states import cut_weights, raster


class CutawayTests(unittest.TestCase):
    def test_room_opening_preserves_surrounding_wall_and_uvs(self):
        triangle = np.array([[0., 0.], [8., 0.], [0., 8.]])
        opening = box(1, 1, 3, 3)
        weights = cut_weights(triangle, opening)
        retained = union_all([Polygon(w @ triangle) for w in weights])
        self.assertAlmostEqual(retained.area, 28)
        self.assertAlmostEqual(retained.intersection(opening).area, 0)
        self.assertTrue(retained.covers(box(.1, .1, .5, .5)))
        uv = triangle / 8 + [.2, .3]
        for w in weights:
            np.testing.assert_allclose(w.sum(1), 1)
            np.testing.assert_allclose(w @ uv, (w @ triangle) / 8 + [.2, .3])
            points = w @ triangle
            self.assertGreater(np.linalg.det(np.c_[points[1]-points[0], points[2]-points[0]]), 0)

    def test_clockwise_wall_keeps_its_front_face(self):
        triangle = np.array([[0., 0.], [0., 8.], [8., 0.]])
        for weights in cut_weights(triangle, box(1, 1, 3, 3)):
            p = weights @ triangle
            self.assertLess(np.linalg.det(np.c_[p[1]-p[0], p[2]-p[0]]), 0)

    def test_edge_on_wall_is_cut_when_camera_rotates(self):
        projected = np.array([[0., 0.], [0., 4.], [0., 4.]])
        world = np.array([[0., 0., 0.], [0., 4., 0.], [0., 4., 4.]])
        weights = cut_weights(projected, box(-1, 1, 1, 3))
        self.assertTrue(weights)
        for w in weights:
            values = (w @ projected)[:, 1]
            self.assertTrue(values.max() <= 1 + 1e-8 or values.min() >= 3 - 1e-8)
        area = sum(np.linalg.norm(np.cross(*(p[1:] - p[0]))) / 2 for p in [w @ world for w in weights])
        self.assertAlmostEqual(area, 4)

    def test_unaffected_triangle_retains_exact_attributes(self):
        triangle = np.array([[0., 0.], [1., 0.], [0., 1.]])
        np.testing.assert_array_equal(cut_weights(triangle, box(5, 5, 6, 6)), [np.eye(3)])
        self.assertEqual(cut_weights(triangle, box(-1, -1, 2, 2)), [])

    def test_projection_samples_pixel_centers_and_clips_image_bounds(self):
        triangle = np.array([[-1., -1.], [4., -1.], [-1., 4.]])
        x, y, weights = raster(triangle, (2, 2))
        np.testing.assert_allclose(weights @ triangle, np.c_[x + .5, y + .5])
        self.assertTrue(np.all((x >= 0) & (x < 2) & (y >= 0) & (y < 2)))
        self.assertIsNone(raster(np.array([[0., 0.], [0., 1.], [0., 2.]]), (2, 2)))


if __name__ == '__main__':
    unittest.main()
