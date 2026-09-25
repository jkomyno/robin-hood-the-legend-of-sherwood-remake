"""Guard source restoration against altering protected or occluded samples."""
import unittest
import numpy as np
from restore_hall_wall_source import patch_texels


class RestorationGuards(unittest.TestCase):
    def test_only_new_visible_source_changes_and_alpha_survives(self):
        original = np.arange(4*4*4, dtype=np.uint8).reshape(4,4,4)
        source = np.full((4,4,4), [173, 81, 42, 255], dtype=np.uint8)
        domain = np.zeros((4,4), dtype=bool)
        domain[0, :3] = True
        rows = [dict(atlas=[x,0], source=[x,0]) for x in range(4)]
        patched, changed, skipped = patch_texels(original, source, domain, rows,
            lambda x,y: x == 1, lambda row: row['source'][0] != 2)
        expected = original.copy()
        expected[0,0,:3] = source[0,0,:3]
        np.testing.assert_array_equal(patched, expected)
        self.assertEqual(len(changed), 1)
        self.assertEqual(skipped, dict(outside_domain=1, prior_allowed=1, blocked=1))
        np.testing.assert_array_equal(patched[:,:,3], original[:,:,3])

    def test_outside_source_never_wraps_into_image(self):
        original = np.full((2,2,4), 88, dtype=np.uint8)
        rows = [dict(atlas=[0,0], source=[-1,0])]
        patched, changed, _ = patch_texels(original, original*2, np.ones((2,2),bool),
                                          rows, lambda *_: False, lambda *_: True)
        np.testing.assert_array_equal(patched, original)
        self.assertEqual(changed, [])

    def test_aliasing_and_invalid_atlas_fail_closed(self):
        original = np.zeros((2,2,4), dtype=np.uint8)
        row = dict(atlas=[0,0],source=[0,0])
        for rows in [[row,row], [dict(atlas=[-1,0],source=[0,0])]]:
            with self.assertRaises(ValueError):
                patch_texels(original, original, np.ones((2,2),bool), rows,
                             lambda *_: False, lambda *_: True)


if __name__ == '__main__':
    unittest.main()
