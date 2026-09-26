"""Exact component partition ownership must survive publication identities."""
import copy
import unittest
from publication_contract import canonical_parts, publication_parts, validate_export_records


def catalog():
    return {'version':2,'map':'Fixture','canonical_owners':{'building-012':'left'},'groups':[
        {'id':'left','name':'Left house','parts':[{'obstacle':12,'name':'Base','components':['base-left']}]},
        {'id':'right','name':'Right house','parts':[{'obstacle':12,'name':'Base','components':['base-right']}]}]}


def records():
    return [{'name':name,'source_node':'building-012','projection_component':'base-'+name,'asset_group':name}
            for name in ['left','right']]


class PublicationComponentTests(unittest.TestCase):
    def test_disjoint_split_keeps_native_provenance(self):
        value=catalog()
        self.assertEqual(canonical_parts(value,'Fixture'),{'building-012'})
        identities=publication_parts(value)
        self.assertEqual(set(identities),{'building-012--component-base-left','building-012--component-base-right'})
        self.assertEqual(identities['building-012--component-base-left']['source_node'],'building-012')
        self.assertEqual(validate_export_records(value,records())['right'],'building-012--component-base-right')
        self.assertEqual(len(validate_export_records(value,records()[:1],['left'])),1)

    def test_overlap_and_whole_source_alias_rejected(self):
        value=catalog();value['groups'][1]['parts'][0]['components']=['base-left']
        with self.assertRaises(ValueError):publication_parts(value)
        value=catalog();value['groups'][1]['parts'][0].pop('components')
        with self.assertRaises(ValueError):publication_parts(value)

    def test_missing_duplicate_unknown_and_wrong_owner_meshes_rejected(self):
        for bad in [records()[:1],records()+[dict(records()[0],name='duplicate')],
                    [dict(records()[0],projection_component='unknown'),records()[1]],
                    [dict(records()[0],asset_group='right'),records()[1]],
                    [dict(records()[0],projection_component=None),records()[1]]]:
            with self.assertRaises(ValueError):validate_export_records(catalog(),bad)

    def test_invalid_identity_and_mesh_name_collisions_rejected(self):
        value=catalog();value['groups'][0]['parts'][0]['components']=['../base']
        with self.assertRaises(ValueError):publication_parts(value)
        bad=records();bad[1]['name']='left'
        with self.assertRaises(ValueError):validate_export_records(catalog(),bad)


if __name__=='__main__':unittest.main()
