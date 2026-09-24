import unittest
import numpy as np
from texture_reconciliation import reconcile_tile


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.source = np.full((32, 64, 4), .4)
        self.source[:, :, 3] = 1
        self.known = np.zeros((32, 64), bool)
        self.known[:, :16] = True

    def test_raw_prediction_changes_only_unknown_and_fades(self):
        raw = self.source.copy()
        raw[:, :, :3] *= 2
        preserved = raw.copy()
        preserved[self.known] = self.source[self.known]
        result = reconcile_tile(preserved, self.source, raw, self.known)
        np.testing.assert_array_equal(result[self.known], preserved[self.known])
        self.assertLess(result[16, 16, 0], preserved[16, 16, 0])
        self.assertGreater(result[16, 60, 0], result[16, 16, 0])
        np.testing.assert_array_equal(result[:, :, 3], preserved[:, :, 3])

    def test_identical_dark_source_has_no_artificial_darkening(self):
        self.source[:, :16, :3] = 0
        result = reconcile_tile(self.source, self.source, self.source, self.known)
        np.testing.assert_array_equal(result, self.source)

    def test_absent_support_is_identity(self):
        result = reconcile_tile(self.source, self.source, self.source * .5, self.known & False)
        np.testing.assert_array_equal(result, self.source)

    def test_scoped_wider_fade_preserves_known_and_extends_correction(self):
        raw = self.source.copy()
        raw[:, :, :3] *= 2
        preserved = raw.copy()
        preserved[self.known] = self.source[self.known]
        default = reconcile_tile(preserved, self.source, raw, self.known)
        wider = reconcile_tile(preserved, self.source, raw, self.known, fade_pixels=96)
        np.testing.assert_array_equal(wider[self.known], preserved[self.known])
        np.testing.assert_array_equal(wider[:, :, 3], preserved[:, :, 3])
        self.assertLess(wider[16, 60, 0], default[16, 60, 0])

    def test_invalid_fade_fails(self):
        for value in [0, -1, 1025, float("nan"), float("inf"), True, "96"]:
            with self.assertRaises(ValueError):
                reconcile_tile(self.source, self.source, self.source, self.known, fade_pixels=value)

    def test_wrong_dimensions_fail(self):
        with self.assertRaises(ValueError):
            reconcile_tile(self.source, self.source, self.source[:, :10], self.known)


if __name__ == '__main__':
    unittest.main()
