"""Door source labels retain strict room/component ownership validation."""
import unittest
from reveal_components import ENDPOINT_COVER_PATCHES, filter_occluders


class Object(dict):
    __hash__ = object.__hash__


class EndpointOwnership(unittest.TestCase):
    def fixture(self, patch):
        cover = Object(source_node='cover', projection_component='roof',
                       reveal_component_role='removable-cover', reveal_component_patch_id=patch)
        retained = Object(source_node='cover', projection_component='wall',
                          reveal_component_role='retained-wall', reveal_component_patch_id=patch)
        selector = dict(source_node='cover', projection_component='roof', patch_id=patch)
        return cover, retained, selector

    def test_all_declared_endpoints_remove_only_their_room_cover(self):
        for label, patch in ENDPOINT_COVER_PATCHES.items():
            cover, retained, selector = self.fixture(patch)
            self.assertEqual(filter_occluders([cover, retained], [selector], projection_label=label), [retained])

    def test_wrong_room_is_rejected(self):
        cover, retained, selector = self.fixture('patch-007')
        with self.assertRaises(ValueError):
            filter_occluders([cover, retained], [selector], projection_label='upper-prison-door-initial')

    def test_unregistered_endpoint_is_rejected(self):
        cover, retained, selector = self.fixture('patch-002')
        with self.assertRaises(ValueError):
            filter_occluders([cover, retained], [selector], projection_label='other-door-initial')

    def test_retained_component_cannot_be_excluded(self):
        cover, retained, selector = self.fixture('patch-002')
        selector['projection_component'] = 'wall'
        with self.assertRaises(ValueError):
            filter_occluders([cover, retained], [selector], projection_label='upper-prison-door-applied')

    def test_ambiguous_or_missing_component_is_rejected(self):
        cover, retained, selector = self.fixture('patch-002')
        for objects in ([retained], [cover, Object(cover), retained]):
            with self.assertRaises(ValueError):
                filter_occluders(objects, [selector], projection_label='upper-prison-door-initial')


if __name__ == '__main__':
    unittest.main()
