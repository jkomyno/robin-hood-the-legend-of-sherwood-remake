import copy
import unittest
from asset_scenes import select_scene, scene_identity


class AssetSceneTests(unittest.TestCase):
    def fixture(self):
        return {'scene': 0, 'scenes': [{'name': 'default', 'nodes': [0]}, {'name': 'applied', 'nodes': [2]}],
                'nodes': [{'name': 'building-001', 'children': [1]}, {'mesh': 0},
                          {'name': 'building-001', 'children': [3]}, {'mesh': 0}],
                'meshes': [{'primitives': [{'material': 0}]}], 'materials': [{'name': 'shared'}]}

    def test_separate_hierarchies_share_resources(self):
        original = self.fixture()
        before = copy.deepcopy(original)
        selected = select_scene(original, 'applied')
        self.assertEqual(len(selected['nodes']), 2)
        self.assertEqual(selected['nodes'][0]['children'], [1])
        self.assertEqual(selected['meshes'], original['meshes'])
        self.assertEqual(original, before)

    def test_missing_or_ambiguous_scene_rejected(self):
        for name in ('missing', 1, ''):
            with self.assertRaises(ValueError):
                select_scene(self.fixture(), name)
        model = self.fixture()
        model['scenes'][1]['name'] = 'default'
        with self.assertRaises(ValueError):
            select_scene(model, 'default')

    def test_cycle_rejected(self):
        model = self.fixture()
        model['nodes'][1]['children'] = [0]
        with self.assertRaises(ValueError):
            select_scene(model)

    def test_animations_scoped_to_reachable_nodes(self):
        model = self.fixture()
        model['animations'] = [{'channels': [{'target': {'node': 3}}]}]
        self.assertFalse(select_scene(model)['animations'])
        self.assertTrue(select_scene(model, 'applied')['animations'])

    def test_scene_identity_disambiguates_same_file(self):
        self.assertNotEqual(scene_identity({'model': 'model.glb', 'model_scene': 'default'}),
                            scene_identity({'model': 'model.glb', 'model_scene': 'applied'}))
        with self.assertRaises(ValueError):
            scene_identity({'model': 'model.glb', 'model_scene': 1})


if __name__ == '__main__':
    unittest.main()
