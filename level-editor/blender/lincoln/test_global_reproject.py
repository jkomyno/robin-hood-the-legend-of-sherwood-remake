"""Covered-state selection of global_reproject (plain Python: python3 -m unittest)."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from global_reproject import covered_state_mesh, STATE_ONLY_KEYS


class CoveredStateMeshTests(unittest.TestCase):
    def test_plain_part_is_covered_geometry(self):
        self.assertTrue(covered_state_mesh({'source_node': 'building-233', 'asset_group': 'lincoln-great-hall'}))

    def test_parts_hidden_when_a_patch_applies_stay(self):
        self.assertTrue(covered_state_mesh({'source_node': 'building-245', 'reveal_hide_when_applied': ['patch-011']}))

    def test_revealed_state_copies_are_excluded(self):
        self.assertFalse(covered_state_mesh({'state_recipe': 'hall-v1', 'state_variant_of': 'building-256'}))
        self.assertFalse(covered_state_mesh({'state_variant_of': 'building-237'}))

    def test_patch_only_objects_are_excluded(self):
        self.assertFalse(covered_state_mesh({'source_node': 'building-463', 'reveal_show_when_applied': ['patch-08']}))

    def test_empty_markers_do_not_exclude(self):
        self.assertTrue(covered_state_mesh({key: '' for key in STATE_ONLY_KEYS}))
        self.assertTrue(covered_state_mesh({'reveal_show_when_applied': []}))


if __name__ == '__main__':
    unittest.main()
