import unittest
import numpy as np
from generated_surface_support import support, filtered_color


class GeneratedSupportTests(unittest.TestCase):
    def test_connected_background_rejected_but_window_preserved(self):
        image = np.zeros((12, 12, 4))
        surface = np.zeros((12, 12), bool)
        surface[2:10, 2:10] = True
        image[2:9, 2:10, :3] = .4
        image[5, 5, :3] = 0
        result = support(image, surface, .01)
        self.assertFalse(result[9, 5])
        self.assertTrue(result[5, 5])
        self.assertTrue(result[8, 5])

    def test_bilinear_background_does_not_darken_valid_edge(self):
        result = filtered_color([[.5, .4, .3], [0, 0, 0]], [.25, .75], [True, False])
        np.testing.assert_allclose(result, [.5, .4, .3])
        self.assertIsNone(filtered_color([[0, 0, 0]], [1], [False]))


if __name__ == '__main__':
    unittest.main()
