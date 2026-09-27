"""Legacy migration identities must describe assets without losing source ownership."""
import re
import json
import sys
from pathlib import Path
import unittest
from editor_catalog import NAMES, source_node


class LegacyCatalogTests(unittest.TestCase):
    def test_descriptive_ids_are_unique(self):
        ids=['sherwood-'+re.sub(r'[^a-z0-9]+','-',name.lower()).strip('-') for name in NAMES.values()]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertFalse(any('group-' in value for value in ids))

    def test_standard_catalog_has_unique_complete_ownership(self):
        editor=Path(__file__).resolve().parents[2]
        sys.path.insert(0,str(editor/'refinement/blender'))
        from catalog_schema import parse_catalog
        catalog=json.loads((editor/'refinement/catalogs/sherwood.json').read_text())
        index=parse_catalog(catalog)
        omitted=set(catalog['legacy_migration']['previously_unexported_obstacles'])
        expected={f'building-{i:03}' for i in range(127) if i not in omitted}
        expected.add('foliage-foreground-oak')
        self.assertEqual(index.sources,expected)
        self.assertEqual(len(index.groups),107)
        self.assertTrue(all(not key.startswith('sherwood-group-') for key in index.groups))

    def test_refinement_replaces_original_obstacle_even_when_tree_number_differs(self):
        self.assertEqual(source_node('16 Camp props and traced roots',{'name':'Tree 036 upper traced limb','props':{}}),'building-038')
        self.assertEqual(source_node('16 Camp props and traced roots',{'name':'Central oak left root','props':{}}),'building-052')

    def test_foreground_canopy_does_not_invent_collision(self):
        self.assertEqual(source_node('10 Animated foliage',{'name':'canopy','props':{'supporting_tree':'-5'}}),'foliage-foreground-oak')

    def test_unrecognized_geometry_fails(self):
        with self.assertRaisesRegex(ValueError,'Unmapped legacy mesh'):
            source_node('new collection',{'name':'unknown','props':{}})

if __name__=='__main__':unittest.main()
