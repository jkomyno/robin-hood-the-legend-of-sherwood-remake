import copy
import unittest

from catalog_schema import parse_catalog


def catalog(version=2):
    value = {'version': version, 'map': 'Example', 'groups': [
        {'id': 'house', 'name': 'House', 'parts': [{'obstacle': 200, 'name': 'Wall', 'components': ['west']}]},
        {'id': 'annex', 'name': 'Annex', 'parts': [{'obstacle': 200, 'name': 'Wall', 'components': ['east']}]},
    ], 'canonical_owners': {'building-200': 'house'}}
    if version == 1:
        value['groups'] = value['groups'][:1]
        del value['groups'][0]['parts'][0]['components']
        del value['canonical_owners']
    return value


def meshes():
    return [dict(source_node='building-200', projection_component=component, hide_render=component is None)
            for component in ('west', 'east', None)]


class CatalogTests(unittest.TestCase):
    def test_explicit_mission_part_has_no_obstacle_alias(self):
        value=catalog(1)
        value['groups'].append({'id':'bridge','name':'Drawbridge','parts':[
            {'node':'mission-second-drawbridge','name':'Moving bridge','mission_profile':'Map - Bridge'}]})
        index=parse_catalog(value)
        self.assertEqual(index.sources,{'building-200','mission-second-drawbridge'})
        self.assertEqual(index.owner_for('mission-second-drawbridge')[0]['id'],'bridge')
        part=value['groups'][-1]['parts'][0]
        for bad in ({'obstacle':268},{'node':'building-268'},{'mission_profile':''},{'source_obstacle':268}):
            changed=copy.deepcopy(value);changed['groups'][-1]['parts'][0].update(bad)
            with self.assertRaisesRegex(ValueError,'supplemental mission'):
                parse_catalog(changed)

    def test_partition_routes_components_and_retained_original(self):
        index = parse_catalog(catalog(), {'ground', 'building-200'})
        self.assertEqual(index.owner_for('building-200', 'east')[0]['id'], 'annex')
        self.assertEqual(index.owner_for('building-200')[0]['id'], 'house')
        index.validate_meshes(meshes())

    def test_reject_duplicate_selector(self):
        value = catalog()
        value['groups'][1]['parts'][0]['components'] = ['west']
        with self.assertRaisesRegex(ValueError, 'Duplicate component ownership'):
            parse_catalog(value)

    def test_reject_implicit_selector(self):
        value = catalog()
        del value['groups'][1]['parts'][0]['components']
        with self.assertRaisesRegex(ValueError, 'explicit disjoint components'):
            parse_catalog(value)

    def test_reject_empty_selector_list(self):
        value = catalog()
        value['groups'][1]['parts'][0]['components'] = []
        with self.assertRaisesRegex(ValueError, 'nonempty list'):
            parse_catalog(value)

    def test_exact_component_mesh_coverage(self):
        index = parse_catalog(catalog())
        for records, error in [(meshes()[1:], 'Missing component'),
                               (meshes() + [meshes()[0]], 'Duplicate component'),
                               (meshes() + [dict(source_node='building-200', projection_component='roof')], 'Unexpected source component')]:
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                index.validate_meshes(records)

    def test_componentless_original_must_be_hidden(self):
        records = meshes()
        records[-1]['hide_render'] = False
        with self.assertRaisesRegex(ValueError, 'Visible componentless'):
            parse_catalog(catalog()).validate_meshes(records)

    def test_canonical_owner_and_source_union_required(self):
        for owners in ({}, {'building-200': 'missing'}, {'building-200': 'house', 'building-201': 'house'}):
            value = catalog()
            value['canonical_owners'] = owners
            with self.subTest(owners=owners), self.assertRaises(ValueError):
                parse_catalog(value)
        with self.assertRaisesRegex(ValueError, 'Coverage mismatch'):
            parse_catalog(catalog(), {'building-200', 'building-201'})

    def test_v1_owns_all_refined_components(self):
        index = parse_catalog(catalog(1))
        index.validate_meshes(meshes())
        self.assertEqual(index.owner_for('building-200', 'east')[0]['id'], 'house')
        value = catalog(1)
        value['groups'].append(copy.deepcopy(value['groups'][0]))
        value['groups'][-1].update(id='annex', name='Annex')
        with self.assertRaisesRegex(ValueError, 'unique whole-source'):
            parse_catalog(value)

    def test_v2_unsplit_sources_still_allow_refined_components(self):
        value = catalog(1)
        value.update(version=2, canonical_owners={'building-200': 'house'})
        parse_catalog(value).validate_meshes(meshes())


if __name__ == '__main__':
    unittest.main()
