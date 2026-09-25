import unittest
import numpy as np
from isolated_edge_texels import donor


class IsolatedEdgeTests(unittest.TestCase):
    def setUp(self):
        self.own = np.full((5, 5), 2, dtype=np.uint8)
        self.own[2, 2] = 0
        self.physical = np.ones((5, 5), bool)
        y, x = np.mgrid[:5, :5]
        self.positions = np.stack((x, y, np.zeros_like(x)), axis=-1).astype(float)

    def test_only_original_physical_donors(self):
        self.own[1, 2] = 1
        self.own[2, 1] = 3
        self.physical[2, 3] = False
        selected, distance, world = donor(self.own, self.physical, self.positions, (2, 2), max_texels=1, max_world=1)
        self.assertEqual(selected, (3, 2))
        self.assertEqual((distance, world), (1, 1))

    def test_reject_connected_gap_and_protected_target(self):
        self.own[2, 3] = 0
        with self.assertRaises(ValueError):
            donor(self.own, self.physical, self.positions, (2, 2), max_texels=5, max_world=5)
        self.own[2, 2] = 1
        with self.assertRaises(ValueError):
            donor(self.own, self.physical, self.positions, (2, 2), max_texels=5, max_world=5)

    def test_explicit_two_texel_component(self):
        self.own[2, 3] = 0
        donor(self.own, self.physical, self.positions, (2, 2), max_texels=1, max_world=1, expected_component=[(2, 2), (2, 3)])

    def test_world_limit_not_just_atlas_distance(self):
        self.positions[2, 2, 2] = 10
        with self.assertRaises(ValueError):
            donor(self.own, self.physical, self.positions, (2, 2), max_texels=5, max_world=2)


if __name__ == '__main__':
    unittest.main()
