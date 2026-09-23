"""Component-qualified multi-patch ownership must be disjoint before baking."""
import unittest
from reveal_components import filter_receivers, validate_receiver_partition


class Mesh:
    def __init__(self,name,component,patch,node='building-249'):
        self.name=name
        self.props=dict(source_node=node,projection_component=component,reveal_component_patch_id=patch)
    def get(self,key):return self.props.get(key)


def selector(component,patch):
    return dict(source_node='building-249',projection_components=[component],patch_id=patch)


class ReceiverPartition(unittest.TestCase):
    def setUp(self):
        # Repeated component names are deliberately qualified by their patch.
        self.upper=Mesh('upper inside','retained','patch-013')
        self.lower=Mesh('lower inside','retained','patch-014')
        self.upper_cover=Mesh('upper outside','cover','patch-013')
        self.lower_cover=Mesh('lower outside','cover','patch-014')
        self.objects=[self.upper,self.lower,self.upper_cover,self.lower_cover]
        self.layers={label:['building-249'] for label in ['exterior','interior-patch-013','interior-patch-014']}
        self.selectors={'exterior':[selector('cover','patch-013'),selector('cover','patch-014')],
            'interior-patch-013':[selector('retained','patch-013')],
            'interior-patch-014':[selector('retained','patch-014')]}

    def test_disjoint_patches_union_exterior_components(self):
        result=validate_receiver_partition(self.objects,self.layers,self.selectors)
        self.assertEqual(result['exterior'],[self.upper_cover,self.lower_cover])
        self.assertEqual(result['interior-patch-013'],[self.upper])
        self.assertEqual(result['interior-patch-014'],[self.lower])

    def test_actual_mesh_overlap_rejected(self):
        self.selectors['interior-patch-014']=[selector('retained','patch-013')]
        with self.assertRaisesRegex(ValueError,'Overlapping receiver mesh'):
            validate_receiver_partition(self.objects,self.layers,self.selectors)

    def test_broad_node_selection_cannot_overlap_split_layer(self):
        for label in self.layers:
            selectors={k:v for k,v in self.selectors.items() if k!=label}
            with self.subTest(label=label),self.assertRaisesRegex(ValueError,'Overlapping receiver mesh'):
                validate_receiver_partition(self.objects,self.layers,selectors)

    def test_duplicate_union_and_ambiguous_component_rejected(self):
        with self.assertRaisesRegex(ValueError,'Duplicate receiver component'):
            filter_receivers(self.objects,[selector('cover','patch-013')]*2)
        duplicate=Mesh('ambiguous upper','retained','patch-013')
        with self.assertRaisesRegex(ValueError,'one reviewed patch component'):
            validate_receiver_partition(self.objects+[duplicate],self.layers,self.selectors)

    def test_hidden_catalog_component_not_silently_reassigned(self):
        result=validate_receiver_partition(self.objects[1:],self.layers,self.selectors,
                                           available_objects=self.objects)
        self.assertEqual(result['interior-patch-013'],[])
        self.assertEqual(result['interior-patch-014'],[self.lower])


if __name__=='__main__':unittest.main()
