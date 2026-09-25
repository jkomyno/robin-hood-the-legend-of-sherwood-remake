import unittest
import numpy as np
from course_patch_guards import coordinates, coplanar_measurements, ownership_classes


class CoursePatchGuards(unittest.TestCase):
    def test_negative_and_overflow_do_not_wrap(self):
        for bad in [[[-1, 0]], [[4, 0]], [[0, 3]]]:
            with self.assertRaises(ValueError):
                coordinates(bad, [[0, 0]], (3, 4))
            with self.assertRaises(ValueError):
                coordinates([[0, 0]], bad, (3, 4))

    def test_fractional_and_nonfinite_rejected(self):
        for bad in [[[.5, 0]], [[float('nan'), 0]], [[float('inf'), 0]]]:
            with self.assertRaises(ValueError):
                coordinates(bad, [[0, 0]], (3, 4))

    def test_duplicate_targets_and_count_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            coordinates([[0, 0], [0, 0]], [[1, 1], [2, 2]], (3, 4))
        with self.assertRaises(ValueError):
            coordinates([[0, 0]], [[1, 1], [2, 2]], (3, 4))

    def test_raster_donor_aliases_allowed(self):
        a, b = coordinates([[0, 0], [1, 0]], [[2, 2], [2, 2]], (3, 4))
        self.assertEqual(a.dtype, np.dtype('<i4'))
        self.assertEqual(len(np.unique(b, axis=0)), 1)

    def test_degenerate_and_nonfinite_plane_rejected(self):
        good = np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0]])
        for bad in [np.zeros((3, 3)), good * float('nan')]:
            with self.assertRaises(ValueError):
                coplanar_measurements([good, bad])

    def test_protected_targets_and_nongenerated_donors_rejected(self):
        own = np.array([[0, 1, 2, 3]])
        ownership_classes(own, [[0, 0]], [[2, 0]])
        for target in [1, 2, 3]:
            with self.assertRaises(ValueError):
                ownership_classes(own, [[target, 0]], [[2, 0]])
        for donor in [0, 1, 3]:
            with self.assertRaises(ValueError):
                ownership_classes(own, [[0, 0]], [[donor, 0]])

    def test_coplanar_and_offset_measured(self):
        a = np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0]])
        self.assertEqual(coplanar_measurements([a, a + [1, 1, 0]]), (0., 0.))
        self.assertEqual(coplanar_measurements([a, a + [0, 0, 2]]), (0., 2.))


if __name__ == '__main__':
    unittest.main()
