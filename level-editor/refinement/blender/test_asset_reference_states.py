"""Display state selection requires explicit geometry authority."""
import unittest
from asset_reference_views import state_objects


class Mesh:
    type = 'MESH'
    hide_render = False

    def __init__(self, node, asset='house', **properties):
        self.properties = dict(source_node=node, asset_group=asset, **properties)

    def get(self, key):
        return self.properties.get(key)


class StateSelectionTests(unittest.TestCase):
    def setUp(self):
        self.floor = Mesh('building-001')
        self.cover = Mesh('building-002', projection_component='roof', reveal_component_patch_id='patch-000')
        self.wall = Mesh('building-002', projection_component='wall', reveal_component_patch_id='patch-000')
        self.neighbor = Mesh('building-003', asset='neighbor')
        self.objects = [self.floor, self.cover, self.wall, self.neighbor]
        self.review = dict(version=1, reviewed=True, reviewer='reviewer', evidence='Visual state review',
                           covered=dict(hidden_nodes=['building-001'], hidden_components=[]),
                           revealed=dict(hidden_nodes=[], hidden_components=[dict(
                               source_node='building-002', projection_component='roof', patch_id='patch-000')]))

    def test_split_cover_is_hidden_without_hiding_wall_or_changing_context(self):
        self.assertEqual(state_objects(self.objects, 'house', 'patch-000', self.review, 'covered'),
                         [self.cover, self.wall])
        self.assertEqual(state_objects(self.objects, 'house', 'patch-000', self.review, 'revealed'),
                         [self.floor, self.wall])
        self.assertTrue(all(not o.hide_render for o in self.objects))

    def test_unreviewed_or_absent_state_evidence_rejected(self):
        self.review['reviewed'] = False
        with self.assertRaises(ValueError):
            state_objects(self.objects, 'house', 'patch-000', self.review, 'covered')
        with self.assertRaises(ValueError):
            state_objects(self.objects, 'house', 'patch-000', {}, 'covered')

    def test_missing_and_wrong_patch_components_rejected(self):
        for key, value in [('projection_component', 'missing'), ('patch_id', 'patch-999')]:
            selector = self.review['revealed']['hidden_components'][0]
            old = selector[key]
            selector[key] = value
            with self.assertRaises(ValueError):
                state_objects(self.objects, 'house', 'patch-000', self.review, 'revealed')
            selector[key] = old
        self.review['covered']['hidden_nodes'].append('building-999')
        with self.assertRaises(ValueError):
            state_objects(self.objects, 'house', 'patch-000', self.review, 'covered')


if __name__ == '__main__':
    unittest.main()
