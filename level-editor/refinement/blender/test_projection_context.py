"""Ground context exclusions are exact, nonreceiver-only and evidence-bound."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from projection_context import ground_exclusion
class Object(dict):
    name='Terrain';type='MESH';hide_render=False
class GroundExclusionTests(unittest.TestCase):
    def test_scoped_exclusion_and_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'evidence';p.write_bytes(b'bank source')
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            c={'asset_id':'house','source_path':str(p),'source_projection_ground_exclusion':{'version':1,'asset_id':'house','object_name':'Terrain','rationale':'visible bank below foundation','source_sha256':digest,'evidence':str(p),'evidence_sha256':digest}}
            ground=Object(source_node='ground',asset_group=None)
            self.assertEqual(ground_exclusion(c,[ground])['excluded_source_node'],'ground')
            c['source_projection_ground_exclusion']['object_name']='Absent'
            with self.assertRaises(ValueError):ground_exclusion(c,[ground])
            c['source_projection_ground_exclusion']['object_name']='Terrain'
            ground['asset_group']='house'
            with self.assertRaises(ValueError):ground_exclusion(c,[ground])
            ground['asset_group']=None;ground['source_node']='wall'
            with self.assertRaises(ValueError):ground_exclusion(c,[ground])
            ground['source_node']='ground'
            with self.assertRaises(ValueError):ground_exclusion(c,[ground,Object(source_node='ground')])
            p.write_bytes(b'changed')
            with self.assertRaises(ValueError):ground_exclusion(c,[ground])
    def test_default_unchanged(self):
        self.assertIsNone(ground_exclusion({},[]))
if __name__=='__main__':unittest.main()
