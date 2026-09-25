import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from supplement_shared_inferred_provenance import updated_ownership


class SupplementalProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.donor = np.arange(32, dtype=np.float32).reshape(2, 4, 4)/40
        self.target = np.ones((2, 4, 4), dtype=np.float32)*.9
        self.donor_mask = np.array([[2, 2, 0, 3], [1, 2, 2, 2]], dtype=np.uint8)
        self.target_mask = np.array([[0, 1, 0, 3], [2, 3, 2, 0]], dtype=np.uint8)
        self.final = self.target.copy()
        self.selected = (self.donor_mask == 2) & (self.target_mask != 1)
        self.final[self.selected, :3] = self.donor[self.selected, :3]

    def test_exact_selection_and_untouched_classes(self):
        ownership, count = updated_ownership(self.donor, self.target, self.final,
                                             self.donor_mask, self.target_mask)
        np.testing.assert_array_equal(ownership, [[2, 1, 0, 3], [2, 2, 2, 2]])
        self.assertEqual(count, 4)
        np.testing.assert_array_equal(self.target_mask, [[0, 1, 0, 3], [2, 3, 2, 0]])

    def test_reject_source_unselected_or_alpha_change(self):
        for row, col, channel in [(0, 1, 0), (0, 2, 0), (0, 0, 3), (1, 1, 1)]:
            final = self.final.copy()
            final[row, col, channel] += .01
            with self.subTest(pixel=(row, col, channel)), self.assertRaises(ValueError):
                updated_ownership(self.donor, self.target, final, self.donor_mask, self.target_mask)

    def test_reject_invalid_provenance_and_nonfinite_atlas(self):
        mask = self.donor_mask.copy()
        mask[0, 0] = 255
        with self.assertRaises(ValueError):
            updated_ownership(self.donor, self.target, self.final, mask, self.target_mask)
        final = self.final.copy()
        final[0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            updated_ownership(self.donor, self.target, final, self.donor_mask, self.target_mask)

    def test_future_bounded_transfer_fails_before_output_creation(self):
        from supplement_shared_inferred_provenance import run
        with tempfile.TemporaryDirectory() as directory:
            bake = Path(directory)
            (bake/'validation.json').write_text(json.dumps({'shared_inferred_transfer': {'allow_bounded_donors': True}}))
            with patch.dict('sys.modules', {'bpy': object()}), self.assertRaisesRegex(ValueError, 'class2 only'):
                run(bake, bake/'supplement')
            self.assertFalse((bake/'supplement').exists())

    def test_identical_rgb_still_records_transferred_provenance(self):
        mask, count = updated_ownership(self.target, self.target, self.target,
                                        self.donor_mask, self.target_mask)
        self.assertEqual(count, 4)
        self.assertEqual(mask[0, 0], 2)


if __name__ == '__main__':
    unittest.main()
