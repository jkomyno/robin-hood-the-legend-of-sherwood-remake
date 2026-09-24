import copy,hashlib,tempfile,unittest
from pathlib import Path
from ground_projection_review import validate
class GroundReviewTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);root=Path(self.tmp.name);self.source=root/'source';self.source.write_bytes(b'source');self.evidence=root/'proof';self.evidence.write_bytes(b'measured feet');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
  r=dict(version=1,asset_id='hut',object_name='nottingham Terrain',rationale='Measured feet lie below the flat proxy.',source_sha256=sha(self.source),evidence=str(self.evidence),evidence_sha256=sha(self.evidence))
  self.config=dict(asset_id='hut',map_name='nottingham',source_path=str(self.source),part_ids=['building-281'],outside_geometry={'nottingham Terrain':'immutable-digest'},source_projection_ground_exclusion=r)
  self.before=[dict(projection_label='exterior',source_path=str(self.source),receiver_nodes=['building-281','foreign','ground'],occluder_nodes=['building-281','foreign','ground'])]
  self.after=[{**self.before[0], 'receiver_nodes':['building-281'],'occluder_nodes':['building-281','foreign'],'ground_context_exclusion':{**r,'excluded_source_node':'ground'}}]
 def test_exact_exclusion(self):self.assertEqual(validate(self.config,self.before,self.after)['excluded_source_node'],'ground')
 def test_evidence_changed(self):
  self.evidence.write_bytes(b'changed')
  with self.assertRaises(ValueError):validate(self.config,self.before,self.after)
 def test_source_changed(self):
  self.source.write_bytes(b'changed')
  with self.assertRaises(ValueError):validate(self.config,self.before,self.after)
 def test_other_foreground_removed(self):
  self.after[0]['occluder_nodes'].remove('foreign')
  with self.assertRaises(ValueError):validate(self.config,self.before,self.after)
 def test_receivers_expanded(self):
  self.after[0]['receiver_nodes'].append('foreign')
  with self.assertRaises(ValueError):validate(self.config,self.before,self.after)
 def test_exclusion_object_substituted(self):
  self.config['source_projection_ground_exclusion']['object_name']='Other protected object';self.config['outside_geometry']['Other protected object']='digest'
  with self.assertRaises(ValueError):validate(self.config,self.before,self.after)
 def test_ground_not_protected(self):
  self.config['outside_geometry']={}
  with self.assertRaises(ValueError):validate(self.config,self.before,self.after)
 def test_layer_added(self):
  self.after.append(copy.deepcopy(self.after[0]))
  with self.assertRaises(ValueError):validate(self.config,self.before,self.after)
 def test_record_not_bound(self):
  self.after[0]['ground_context_exclusion']['rationale']='Different'
  with self.assertRaises(ValueError):validate(self.config,self.before,self.after)
 def test_ground_receiver_or_layered(self):
  for change in [{'part_ids':['ground']},{'projection_manifest':'other'}]:
   c={**self.config,**change}
   with self.assertRaises(ValueError):validate(c,self.before,self.after)
if __name__=='__main__':unittest.main()
