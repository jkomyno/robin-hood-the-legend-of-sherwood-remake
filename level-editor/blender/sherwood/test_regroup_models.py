"""Check ownership boundaries that could silently lose or duplicate source meshes."""
import json
from pathlib import Path
import sys
import unittest

EDITOR=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(EDITOR/'refinement/blender'))
from catalog_schema import parse_catalog


class GroupingTests(unittest.TestCase):
    def setUp(self):
        self.old=parse_catalog(json.loads((EDITOR/'refinement/catalogs/sherwood.json').read_text()))
        self.new=parse_catalog(json.loads(Path(__file__).with_name('grouping-candidate.json').read_text()))

    def test_every_original_source_retained(self):
        self.assertEqual(self.old.sources,self.new.sources)
        self.assertEqual(len(self.new.groups),82)

    def test_entire_central_tree_separate_from_built_structure(self):
        for number in (32,33,48,49,52):
            self.assertEqual(self.new.canonical_owners[f'building-{number:03}'],'sherwood-central-oak')
        self.assertEqual(self.new.canonical_owners['building-103'],'sherwood-central-oak-treehouse')
        for number in (88,91,96,99):
            self.assertEqual(self.new.canonical_owners[f'building-{number:03}'],'sherwood-central-oak-platform')

    def test_mixed_source_geometry_has_explicit_disjoint_owners(self):
        for source,component,expected in [
            ('building-024','Ladder oak - rung 01.001','sherwood-ladder-oak-platform'),
            ('building-024','Ladder oak - tapered fluted trunk.001','sherwood-ladder-oak'),
            ('building-102','Ring ladder rung 1.001','sherwood-central-oak-platform'),
            ('building-102','Central hut - wall 1 plank 01.001','sherwood-central-oak-treehouse')]:
            group,_=self.new.owner_for(source,component)
            self.assertEqual(group['id'],expected)
        with self.assertRaisesRegex(ValueError,'Unexpected source component'):
            self.new.owner_for('building-024','unclassified new ladder rung')

    def test_detached_limb_matches_actual_parent_tree(self):
        self.assertEqual(self.new.canonical_owners['building-038'],self.new.canonical_owners['building-036'])


if __name__=='__main__':unittest.main()
