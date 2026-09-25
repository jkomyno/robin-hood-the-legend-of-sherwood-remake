import copy
import unittest
from shared_surface_policy import validate


class SharedSurfacePolicy(unittest.TestCase):
    def setUp(self):
        self.policy = dict(version=1, kind='covered-revealed-source-reprojection',
            asset_id='hall', geometry_revision='revision', approved_model_sha256=['a','b'], objects=['roof'])
        identity = dict(asset_group='hall', source_node='building-1', projection_component='retained-roof')
        self.args = dict(asset_id='hall', geometry_revision='revision', model_hashes=['a','b'],
            states=['covered','revealed'], originals=[{'roof':('same-geometry','source-a')},
                                                     {'roof':('same-geometry','source-b')}],
            identities=[{'roof':identity}, {'roof':copy.deepcopy(identity)}],
            material_records=[dict(object='roof', source_node='building-1',
                projection_component='retained-roof', covered_face_materials={'0':'a'},
                revealed_face_materials={'0':'b'})])

    def test_explicit_reprojection_difference_permits_identical_surface(self):
        self.assertEqual(validate(self.policy, **self.args), {'roof'})

    def test_changed_model_revision_or_state_rejected(self):
        for key, value in [('model_hashes',['a','changed']), ('geometry_revision','other'),
                           ('states',['initial','applied'])]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate(self.policy, **{**self.args,key:value})

    def test_unselected_missing_or_duplicate_surface_rejected(self):
        for names in [[], ['roof','roof'], ['floor']]:
            with self.subTest(names=names), self.assertRaises(ValueError):
                validate({**self.policy,'objects':names}, **self.args)

    def test_geometry_or_source_identity_change_rejected(self):
        args=copy.deepcopy(self.args);args['originals'][1]['roof']=('moved','source-b')
        with self.assertRaises(ValueError): validate(self.policy,**args)
        args=copy.deepcopy(self.args);args['identities'][1]['roof']['source_node']='building-2'
        with self.assertRaises(ValueError): validate(self.policy,**args)

    def test_missing_or_ambiguous_source_state_evidence_rejected(self):
        for records in [[], self.args['material_records']*2,
                        [{**self.args['material_records'][0],'revealed_face_materials':{}}]]:
            with self.subTest(records=records), self.assertRaises(ValueError):
                validate(self.policy,**{**self.args,'material_records':records})


if __name__ == '__main__':
    unittest.main()
