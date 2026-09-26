"""Security regressions for assets sharing a canonical source node."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from catalog_schema import parse_catalog
from workspace_components import scope_for,validated_scope,owns_assignment
from refinement_workspace import _validated_masks,_files,_sha

CATALOG={'version':2,'map':'scope','canonical_owners':{'building-000':'left'},'groups':[
 {'id':'left','name':'Left section','parts':[{'obstacle':0,'name':'Wall','components':['left-part']}]},
 {'id':'right','name':'Right section','parts':[{'obstacle':0,'name':'Wall','components':['right-part']}]}]}

class WorkspaceScopeTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.ref=self.root/'reference';self.ref.mkdir();self.catalog=self.ref/'grouping.json';self.catalog.write_text(json.dumps(CATALOG));self.config={'asset_id':'left','part_ids':['building-000'],'source_path':str(self.ref/'source.png'),'grouping_manifest_sha256':_sha(self.catalog),'component_ownership':scope_for(parse_catalog(CATALOG),'left')}
 def tearDown(self):self.temp.cleanup()
 def test_only_explicit_owned_component_is_mutable(self):
  self.assertTrue(owns_assignment(self.config,'source_node','building-000','left-part'))
  self.assertFalse(owns_assignment(self.config,'source_node','building-000','right-part'))
  self.assertFalse(owns_assignment(self.config,'source_node','building-000'))
  self.assertTrue(owns_assignment(self.config,'asset_group','left'))
  self.assertFalse(owns_assignment(self.config,'asset_group','right'))
 def test_scope_cannot_be_deleted_or_forged(self):
  bad=copy.deepcopy(self.config);bad.pop('component_ownership')
  with self.assertRaisesRegex(ValueError,'ownership differs'):validated_scope(bad)
  bad=copy.deepcopy(self.config);bad['component_ownership']['owned_components'].append({'source_node':'building-000','projection_component':'right-part'})
  with self.assertRaisesRegex(ValueError,'ownership differs'):validated_scope(bad)
 def test_reference_hash_prevents_authority_rewrite(self):
  self.catalog.write_text(self.catalog.read_text()+' ')
  with self.assertRaisesRegex(ValueError,'reference changed'):validated_scope(self.config)
 def masks(self):
  inventory=self.root/'inventory.json';inventory.write_text(json.dumps({'masks':[{'index':0,'png':'black.png'},{'index':1,'png':'white.png'}]}));origin=self.root/'mask-reference';origin.mkdir();assignment={'reviewed':True,'source_node':'building-000','mask_indices':[0]};data={'version':1,'mask_inventory':str(inventory),'projections':{'exterior':{'source_sha256':'test','state':'test','assignments':[assignment]}}};(origin/'assignments.json').write_text(json.dumps(data));(origin/'native-hashes.json').write_text(json.dumps({str(inventory):_sha(inventory)}));working=self.root/'source-masks.json';working.write_text(json.dumps(data));self.config.update(source_mask_manifest=str(working),mask_reference=str(origin),mask_reference_files=_files(origin));return working,data
 def test_shared_node_mask_change_is_rejected(self):
  path,data=self.masks();data['projections']['exterior']['assignments'][0]['mask_indices']=[1];path.write_text(json.dumps(data))
  with self.assertRaisesRegex(ValueError,'another asset assignment'):_validated_masks(self.config)
 def test_foreign_component_mask_is_rejected(self):
  path,data=self.masks();data['projections']['exterior']['assignments'].append({'reviewed':True,'source_node':'building-000','projection_component':'right-part','mask_indices':[1]});path.write_text(json.dumps(data))
  with self.assertRaisesRegex(ValueError,'another asset assignment'):_validated_masks(self.config)
 def test_owned_component_mask_change_is_allowed(self):
  path,data=self.masks();data['projections']['exterior']['assignments'].append({'reviewed':True,'source_node':'building-000','projection_component':'left-part','mask_indices':[1]});path.write_text(json.dumps(data));self.assertIn('working_sha256',_validated_masks(self.config))
 def test_scenery_workspace_scope_uses_node_identity(self):
  catalog=copy.deepcopy(CATALOG);catalog['groups'].append({'id':'oak','name':'Painted tree','parts':[{'node':'foliage-oak','name':'Painted tree'}]})
  catalog['canonical_owners']['foliage-oak']='oak';self.catalog.write_text(json.dumps(catalog))
  config={'asset_id':'oak','part_ids':['foliage-oak'],'source_path':str(self.ref/'source.png'),'grouping_manifest_sha256':_sha(self.catalog),'component_ownership':scope_for(parse_catalog(catalog),'oak')}
  self.assertEqual(validated_scope(config)['owned_components'],[])
  self.assertTrue(owns_assignment(config,'source_node','foliage-oak'))
  self.assertFalse(owns_assignment(config,'source_node','building-000'))
 def test_legacy_whole_node_assignment_unchanged(self):
  legacy=copy.deepcopy(CATALOG);legacy['version']=1;legacy.pop('canonical_owners');legacy['groups']=legacy['groups'][:1];legacy['groups'][0]['parts'][0].pop('components');self.catalog.write_text(json.dumps(legacy));self.config.pop('component_ownership');self.config['grouping_manifest_sha256']=_sha(self.catalog);self.assertTrue(owns_assignment(self.config,'source_node','building-000'))
if __name__=='__main__':unittest.main()
