"""Working mask assignments may evolve without changing native evidence or neighbors."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from refinement_workspace import _freeze_masks, _validated_masks


class WorkingMaskTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for index in range(2):
            (self.root/f'{index}.png').write_bytes(bytes([index]))
        inventory = {'masks': [dict(index=i, png=f'{i}.png', box_top_left=[0, 0], box_size=[1, 1]) for i in range(2)]}
        (self.root/'inventory.json').write_text(json.dumps(inventory))
        self.manifest = dict(version=1, mask_inventory=str(self.root/'inventory.json'), projections={
            'exterior': dict(source_sha256='a'*64, state='covered', assignments=[
                dict(reviewed=True, source_node='building-001', mask_indices=[0]),
                dict(reviewed=True, asset_group='neighbor', mask_indices=[0])])})
        self.path = self.root/'source-masks.json'
        self.path.write_text(json.dumps(self.manifest))
        self.config = dict(source_mask_manifest=str(self.path), part_ids=['building-001'], asset_id='house')
        _freeze_masks(self.root, self.config)

    def test_owned_component_can_use_previously_unused_native_bitmap(self):
        self.manifest['projections']['exterior']['assignments'].append(dict(
            reviewed=True, source_node='building-001', projection_component='roof', mask_indices=[1]))
        self.path.write_text(json.dumps(self.manifest))
        evidence = _validated_masks(self.config)
        self.assertNotEqual(evidence['working_sha256'], evidence['initial_assignments_sha256'])

    def test_neighbor_state_source_and_inventory_cannot_change(self):
        for mutation in ('neighbor', 'state', 'source', 'inventory'):
            manifest = copy.deepcopy(self.manifest)
            if mutation == 'neighbor':
                manifest['projections']['exterior']['assignments'][1]['mask_indices'] = [1]
            elif mutation == 'state':
                manifest['projections']['exterior']['state'] = 'revealed'
            elif mutation == 'source':
                manifest['projections']['exterior']['source_sha256'] = 'b'*64
            else:
                replacement = self.root/'replacement.json'
                replacement.write_text((self.root/'inventory.json').read_text())
                manifest['mask_inventory'] = str(replacement)
            self.path.write_text(json.dumps(manifest))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                _validated_masks(self.config)

    def test_unused_native_bitmap_and_initial_assignments_are_protected(self):
        (self.root/'1.png').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            _validated_masks(self.config)
        (self.root/'1.png').write_bytes(bytes([1]))
        (self.root/'mask-reference/assignments.json').write_text('{}')
        with self.assertRaises(ValueError):
            _validated_masks(self.config)

    def test_unreviewed_component_and_unknown_mask_are_rejected(self):
        for extra in (dict(reviewed=False, source_node='building-001', projection_component='roof', mask_indices=[0]),
                      dict(reviewed=True, source_node='building-001', projection_component='roof', mask_indices=[99])):
            manifest = copy.deepcopy(self.manifest)
            manifest['projections']['exterior']['assignments'].append(extra)
            self.path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                _validated_masks(self.config)


if __name__ == '__main__':
    unittest.main()
