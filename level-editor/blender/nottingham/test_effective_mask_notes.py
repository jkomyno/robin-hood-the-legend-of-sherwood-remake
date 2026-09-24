"""Regression tests for layer-scoped source constraint notes."""
import unittest
from build_gallery import neutral_source_constraint_notes


def rule(label, node, unknown=False, component=None):
    row = dict(projection=label, source_node=node,
               constraint_kind='unknown-no-approved-source' if unknown else 'reviewed-native-silhouette')
    if component:
        row['projection_component'] = component
    return row


class EffectiveMaskNotesTest(unittest.TestCase):
    def notes(self, rows, layers):
        return neutral_source_constraint_notes(rows, layers, ['house', 'prop'], 'group')

    def test_independent_prop_layer_does_not_use_black_exterior_default(self):
        rows = [rule('exterior', 'prop', True), rule('mission', 'prop'), rule('exterior', 'house')]
        layers = [dict(projection_label='exterior', receiver_nodes=['house']),
                  dict(projection_label='mission', receiver_nodes=['prop'])]
        self.assertEqual(self.notes(rows, layers), [])
        rows[-2] = rule('mission', 'prop', True)
        self.assertIn('prop [mission]', self.notes(rows, layers)[0])

    def test_selected_component_overrides_node_rejection(self):
        rows = [rule('exterior', 'house', True), rule('exterior', 'house', component='roof')]
        layer = dict(projection_label='exterior', receiver_nodes=['house'],
                     receiver_components=[dict(source_node='house', projection_components=['roof'])])
        self.assertEqual(self.notes(rows, [layer]), [])
        layer['receiver_components'][0]['projection_components'].append('unowned-wall')
        self.assertIn('house/unowned-wall [exterior]', self.notes(rows, [layer])[0])

    def test_unspecified_components_retain_conditional_fallback_warning(self):
        rows = [rule('exterior', 'house', True), rule('exterior', 'house', component='roof')]
        notes = self.notes(rows, [dict(projection_label='exterior', receiver_nodes=['house'])])
        self.assertEqual(len(notes), 1)
        self.assertIn('components without a more-specific assignment', notes[0])

    def test_rejected_component_overrides_accepted_node(self):
        rows = [rule('exterior', 'house'), rule('exterior', 'house', True, 'roof')]
        notes = self.notes(rows, [dict(projection_label='exterior', receiver_nodes=['house'])])
        self.assertIn('house/roof [exterior]', notes[0])

    def test_group_fallback_is_used_only_without_node_rule(self):
        rows = [dict(projection='exterior', asset_group='group', constraint_kind='unknown-no-approved-source'),
                rule('exterior', 'house')]
        notes = self.notes(rows, [dict(projection_label='exterior', receiver_nodes=['house', 'prop'])])
        self.assertIn('prop [exterior]', notes[0])
        self.assertNotIn('house [exterior]', notes[0])


if __name__ == '__main__':
    unittest.main()
