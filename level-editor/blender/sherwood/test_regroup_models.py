"""Check ownership boundaries that could silently lose or duplicate source meshes."""
import json
from pathlib import Path
import sys
import unittest
from copy import deepcopy
from grouping_decisions import group_signature

EDITOR=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(EDITOR/'refinement/blender'))
from catalog_schema import parse_catalog


class GroupingTests(unittest.TestCase):
    def setUp(self):
        self.old=parse_catalog(json.loads((EDITOR/'refinement/catalogs/sherwood.json').read_text()))
        self.new=parse_catalog(json.loads(Path(__file__).with_name('grouping-candidate.json').read_text()))

    def test_every_original_source_retained(self):
        self.assertEqual(self.old.sources,self.new.sources)
        self.assertEqual(len(self.new.groups),80)

    def test_requested_platforms_merge_into_houses(self):
        for number in (89,100,105,106,107):
            self.assertEqual(self.new.canonical_owners[f'building-{number:03}'],'sherwood-west-treehouse')
        for number in (90,119,120):
            self.assertEqual(self.new.canonical_owners[f'building-{number:03}'],'sherwood-west-border-treehouse')
        self.assertNotIn('sherwood-west-treehouse-platforms',self.new.groups)
        self.assertNotIn('sherwood-west-border-treehouse-platform',self.new.groups)

    def test_group_approval_survives_only_unrelated_metadata_changes(self):
        group=dict(id='house',name='House',objects=['wall','roof'])
        catalog=dict(groups=[dict(id='house',parts=[dict(obstacle=1,name='Walls')])],canonical_owners={'building-001':'house'})
        stage=dict(geometry_uv_material_fingerprint='geometry-a',source_worker_sha256='source-a',worker_sha256='old')
        original=group_signature(group,catalog,stage)
        self.assertEqual(original,group_signature(group,catalog,{**stage,'worker_sha256':'new-metadata-only'}))
        self.assertNotEqual(original,group_signature({**group,'objects':['wall','roof','platform']},catalog,stage))
        self.assertNotEqual(original,group_signature(group,catalog,{**stage,'geometry_uv_material_fingerprint':'changed'}))
        renamed=deepcopy(catalog);renamed['groups'][0]['parts'][0]['name']='Different component'
        self.assertNotEqual(original,group_signature(group,renamed,stage))

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
