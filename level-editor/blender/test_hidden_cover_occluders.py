"""Already-revealed states may retain explicitly excluded covers in layer lists."""
import unittest
from reveal_components import validate_occluder_nodes


class Object(dict):
    __hash__ = object.__hash__
    type = 'MESH'
    hide_render = True


class HiddenCovers(unittest.TestCase):
    def setUp(self):
        self.cover = Object(source_node='cover', projection_component='roof',
                            reveal_component_role='removable-cover',
                            reveal_component_patch_id='patch-008')
        self.selector = dict(source_node='cover', projection_component='roof',
                             patch_id='patch-008')

    def validate(self, objects=None, selectors=None, requested=None):
        return validate_occluder_nodes(requested or ['cover'], [],
            objects if objects is not None else [self.cover],
            selectors if selectors is not None else [self.selector],
            projection_label='interior-patch-008')

    def test_explicit_hidden_cover_is_valid(self):
        self.validate()

    def test_unlisted_hidden_cover_is_not_silently_dropped(self):
        with self.assertRaises(ValueError): self.validate(selectors=[])

    def test_nonexistent_node_still_fails(self):
        with self.assertRaises(ValueError): self.validate(requested=['missing'])

    def test_retained_hidden_mesh_of_same_node_is_not_excluded(self):
        retained = Object(self.cover, projection_component='wall',
                          reveal_component_role='retained-wall')
        with self.assertRaises(ValueError): self.validate(objects=[self.cover, retained])

    def test_wrong_room_or_role_fails(self):
        for key, value in [('reveal_component_patch_id', 'patch-007'),
                           ('reveal_component_role', 'retained-wall')]:
            with self.assertRaises(ValueError):
                self.validate(objects=[Object(self.cover, **{key: value})])

    def test_visible_requested_nodes_do_not_require_cover_selectors(self):
        validate_occluder_nodes(['cover'], [self.cover], [self.cover],
                                projection_label='exterior')


if __name__ == '__main__':
    unittest.main()
