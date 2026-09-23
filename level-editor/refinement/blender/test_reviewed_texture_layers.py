"""Pure regression checks for scoped exterior writes in multilayer tower packets."""
import copy
import unittest
from reviewed_texture_scope import selected_layers, layer_objects


class LayerTests(unittest.TestCase):
    def setUp(self):
        self.layers = [
            {'projection_label':'exterior', 'receiver_nodes':['building-1','building-2'],
             'receiver_components':[{'source_node':'building-1','projection_components':['shell']}]},
            {'projection_label':'interior-patch-003', 'receiver_nodes':['building-1','building-3']}]

    def test_default_preserves_original_contract(self):
        self.assertIs(selected_layers({'projection_layers':self.layers}), self.layers)

    def test_exterior_filter_retains_original_inventory_and_order(self):
        before = copy.deepcopy(self.layers)
        selected = selected_layers({'projection_layers':self.layers,'texture_projection_labels':['exterior']})
        self.assertEqual(selected, [self.layers[0]])
        self.assertIs(selected[0], self.layers[0])
        self.assertEqual(self.layers, before)
        self.assertEqual(selected_layers({'projection_layers':self.layers,
            'texture_projection_labels':['interior-patch-003','exterior']}), self.layers)

    def test_invalid_or_unknown_labels_fail(self):
        for labels in ([], '', 'exterior', [None], [''], ['exterior','exterior'], ['absent']):
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                selected_layers({'projection_layers':self.layers,'texture_projection_labels':labels})

    def test_overlapping_node_uses_exact_component_scope(self):
        shell={'source_node':'building-1','projection_component':'shell'}
        room={'source_node':'building-1','projection_component':'room'}
        unrestricted={'source_node':'building-2','projection_component':'trim'}
        foreign={'source_node':'building-3','projection_component':'shell'}
        objects=[shell,room,unrestricted,foreign]
        self.assertEqual(layer_objects(self.layers[0],objects),[shell,unrestricted])
        self.assertEqual(layer_objects(self.layers[1],objects),[shell,room,foreign])
        self.assertEqual(objects,[shell,room,unrestricted,foreign])


if __name__=='__main__':unittest.main()
