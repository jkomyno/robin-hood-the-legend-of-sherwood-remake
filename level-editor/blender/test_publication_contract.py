"""Run without Blender: python3 -m unittest discover -s level-editor/blender -p test_publication_contract.py."""
import unittest

from publication_contract import canonical_parts, scene_filename, validate_coverage


class PublicationContractTests(unittest.TestCase):
    def test_coverage_uses_catalog_identities(self):
        catalog = {'map': 'Leicester', 'groups': [{'parts': [
            {'obstacle': 0}, {'obstacle': 273}, {'obstacle': 391}]}]}
        expected = canonical_parts(catalog, 'Leicester')
        validate_coverage({'building-000', 'building-273', 'building-391'}, expected)
        # Equal counts must not conceal substitution of a canonical part.
        with self.assertRaises(ValueError):
            validate_coverage({'building-000', 'building-273', 'building-390'}, expected)
        with self.assertRaises(ValueError):
            canonical_parts(catalog, 'Derby')

    def test_duplicate_ownership_rejected(self):
        with self.assertRaises(ValueError):
            canonical_parts({'map': 'X', 'groups': [
                {'parts': [{'obstacle': 1}]}, {'parts': [{'obstacle': 1}]}]}, 'X')

    def test_filename_is_map_specific_and_local(self):
        self.assertEqual(scene_filename({'map_name': 'Derby'}), 'derby.level3d.json')
        self.assertEqual(scene_filename({'map_name': 'Leicester'}), 'leicester.level3d.json')
        self.assertEqual(scene_filename({'map_name': 'Leicester', 'scene_filename': 'candidate.level3d.json'}), 'candidate.level3d.json')
        for invalid in ('../outside.glb', '/tmp/outside.glb', 'candidate.json'):
            with self.assertRaises(ValueError):
                scene_filename({'map_name': 'Leicester', 'scene_filename': invalid})


if __name__ == '__main__':
    unittest.main()
