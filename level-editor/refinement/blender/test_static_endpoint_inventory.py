"""Pure validation: a native pair is partitioned by its reviewed static states."""
import copy
import unittest
from verify_publication_assets import verify_static_inventory


def fixture():
    variants = {state: {'model': model, 'parts': [{'node': node}], 'components': [{'source_node': node}]}
                for state, model, node in [('initial', 'model.glb', 'building-001'),
                                           ('applied', 'model-applied.glb', 'building-002')]}
    descriptor = {**variants['initial'], 'state_variants': variants}
    models = {state: {'nodes': [{'name': variant['parts'][0]['node'], 'children': [1]},
                                {'name': variant['parts'][0]['node'] + '__retained', 'mesh': 0}]}
              for state, variant in variants.items()}
    imports = [{'asset_id': 'bridge', 'endpoint_id': 'initial', 'blend_sha256': 'initial-hash',
                'texture_states': [{'endpoint_id': 'applied', 'blend_sha256': 'applied-hash'}]}]
    proof = {'status': 'PASS', 'static_variants': [
        {'asset_id': 'bridge', 'state': state, 'status': 'PASS', 'reviewed_source_blend_sha256': state + '-hash',
         'reviewed_source_nodes': [variant['parts'][0]['node']], 'meshes': 1, 'reviewed_worker_reexport_matches': True}
        for state, variant in variants.items()]}
    return descriptor, models, imports, proof


class StaticInventoryTest(unittest.TestCase):
    def verify(self, data):
        descriptor, models, imports, proof = data
        return verify_static_inventory('bridge', descriptor, models, {'building-001', 'building-002'}, imports, proof)

    def test_disjoint_reviewed_pair(self):
        self.assertEqual(self.verify(fixture()), {'building-001', 'building-002'})

    def test_reject_wrong_state_even_if_catalog_subset(self):
        data = fixture()
        data[0]['state_variants']['applied'] = copy.deepcopy(data[0]['state_variants']['initial'])
        data[1]['applied'] = copy.deepcopy(data[1]['initial'])
        with self.assertRaises(ValueError):
            self.verify(data)

    def test_reject_combined_primary(self):
        data = fixture()
        data[0]['components'] = [{'source_node': 'building-001'}, {'source_node': 'building-002'}]
        with self.assertRaises(ValueError):
            self.verify(data)

    def test_reject_switches_and_animation(self):
        for mutation in ('switch', 'animation'):
            data = fixture()
            if mutation == 'switch':
                data[1]['applied']['nodes'][0]['extras'] = {'reveal_show_when_applied': ['patch-001']}
            else:
                data[1]['applied']['animations'] = [{}]
            with self.assertRaises(ValueError):
                self.verify(data)

    def test_reject_proof_for_other_worker(self):
        data = fixture()
        data[3]['static_variants'][1]['reviewed_source_blend_sha256'] = 'initial-hash'
        with self.assertRaises(ValueError):
            self.verify(data)


if __name__ == '__main__':
    unittest.main()
