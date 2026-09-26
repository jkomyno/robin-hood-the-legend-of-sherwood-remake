import json
from pathlib import Path
import tempfile
import unittest
from promote_state_bundles import apply, encoded, prepare, sha


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.lib, self.stage, self.scenes = [self.root / x for x in ('library', 'stage', 'scenes')]
        for p in (self.lib / 'a', self.stage / 'a', self.scenes): p.mkdir(parents=True)
        for name, content in [('model.glb', b'old'), ('model-applied.glb', b'applied'), ('asset.json', b'{}')]:
            (self.lib / 'a' / name).write_bytes(content)
        for name, content in [('model.glb', b'new'), ('asset.json', encoded({'id':'a','name':'custom','tags':['keep'],'source_map':'Derby','model':'model.glb','model_scene':'initial'})), ('preview.glb', b'preview'), ('preview.glb.receipt.json', b'{}')]:
            (self.stage / 'a' / name).write_bytes(content)
        self.entry = {'id':'a','descriptor':'a/asset.json','model':'a/model.glb','model_scene':'initial','preview_model':'a/preview.glb'}
        self.receipt = {'asset_id':'a','source_descriptor_sha256':sha(self.lib/'a/asset.json'), 'source_files':[{'path':n,'sha256':sha(self.lib/'a'/n),'bytes':(self.lib/'a'/n).stat().st_size} for n in ('model.glb','model-applied.glb')], 'output':{'sha256':sha(self.stage/'a/model.glb'),'bytes':3}, 'output_descriptor_sha256':sha(self.stage/'a/asset.json'), 'states':[{'scene':'initial','source_file':'model.glb','source_sha256':sha(self.lib/'a/model.glb'),'source_scene':None,'semantic_sha256':'proof'}]}
        (self.stage/'a/bundle.receipt.json').write_bytes(encoded(self.receipt))
        (self.stage/'bundles.json').write_bytes(encoded([self.receipt]))
        (self.stage/'index.json').write_bytes(encoded({'assets':[self.entry]}))
        self.oldindex = {'assets':[{'id':'a','tags':['keep'],'name':'custom','preview_extra':'keep'}, {'id':'foreign','model':'foreign.glb'}], 'extra':'retain'}
        (self.lib/'index.json').write_bytes(encoded(self.oldindex))
        self.doc = {'assetSources':[{'id':'a','descriptor':'3d-assets/a/asset.json','model':'3d-assets/a/model.glb','model_sha256':sha(self.lib/'a/model.glb'),'descriptor_sha256':sha(self.lib/'a/asset.json')}], 'instances':[{'transform':[1,2,3],'parts':['p']}], 'sceneAssets':[{'sha256':'unchanged'}]}
        (self.scenes/'map.rhlos-map.json').write_bytes(encoded(self.doc))
        (self.lib/'foreign').mkdir()
        (self.lib/'foreign/model.glb').write_bytes(b'foreign model')
        (self.lib/'foreign/asset.json').write_bytes(encoded({
            'id':'foreign', 'name':'Foreign', 'source_map':'York', 'model':'model.glb'}))
        self.plan = prepare(self.lib,self.stage,self.scenes)

    def test_success_preserves_foreign_and_migrates_pins_only(self):
        newer = self.oldindex.copy(); newer['added'] = 'concurrent'
        (self.lib/'index.json').write_bytes(encoded(newer))
        result = apply(self.plan,self.root/'backup')
        self.assertEqual(result['status'],'published')
        index=json.loads((self.lib/'index.json').read_text())
        self.assertEqual(index['assets'][0]['tags'],['keep'])
        self.assertEqual(index['assets'][1]['id'], 'foreign')
        self.assertEqual(index['assets'][1]['name'], 'Foreign')
        self.assertNotIn('added', index)
        doc=json.loads((self.scenes/'map.rhlos-map.json').read_text())
        self.assertEqual(doc['instances'],self.doc['instances'])
        self.assertEqual(doc['sceneAssets'],self.doc['sceneAssets'])
        self.assertEqual(doc['assetSources'][0]['model_scene'],'initial')
        self.assertFalse((self.lib/'a/model-applied.glb').exists())

    def test_index_only_lossy_entries_do_not_declare_assets(self):
        live = json.loads((self.lib/'index.json').read_text())
        live['assets'][0]['lossy_model'] = 'a/lossy.glb'
        (self.lib/'index.json').write_bytes(encoded(live))
        apply(self.plan,self.root/'backup')
        entry = json.loads((self.lib/'index.json').read_text())['assets'][0]
        self.assertNotIn('lossy_model', entry)
        self.assertEqual(entry['tags'], ['keep'])

    def test_stale_unchanged_asset_blocks_before_payload_installation(self):
        live = json.loads((self.lib/'index.json').read_text())
        (self.lib/'foreign/lossy.glb').write_bytes(b'no receipt')
        (self.lib/'index.json').write_bytes(encoded(live))
        before = (self.lib/'index.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'foreign: lossy model or receipt missing'):
            apply(self.plan, self.root/'backup')
        self.assertEqual((self.lib/'a/model.glb').read_bytes(), b'old')
        self.assertEqual((self.lib/'index.json').read_bytes(), before)

    def test_failure_rolls_back(self):
        def hook(phase,n):
            if phase=='after' and n==6: raise RuntimeError('injected')
        with self.assertRaises(RuntimeError): apply(self.plan,self.root/'backup',hook)
        self.assertEqual((self.lib/'a/model.glb').read_bytes(),b'old')
        self.assertTrue((self.lib/'a/model-applied.glb').exists())
        self.assertEqual(json.loads((self.scenes/'map.rhlos-map.json').read_text()),self.doc)
        self.assertEqual(json.loads((self.lib/'index.json').read_text()),self.oldindex)

    def test_index_race_keeps_foreign_writer(self):
        def hook(phase,n):
            if phase=='after' and n==0: (self.lib/'index.json').write_bytes(b'{"assets":[],"foreign":true}')
        with self.assertRaises(ValueError): apply(self.plan,self.root/'backup',hook)
        self.assertEqual(json.loads((self.lib/'index.json').read_text())['foreign'],True)
        self.assertEqual((self.lib/'a/model.glb').read_bytes(),b'old')

    def test_foreign_asset_change_is_not_rolled_back(self):
        def hook(phase,n):
            if phase=='after' and n==0:
                (self.lib/'a/model.glb').write_bytes(b'foreign')
                raise RuntimeError('injected')
        with self.assertRaises(RuntimeError): apply(self.plan,self.root/'backup',hook)
        self.assertEqual((self.lib/'a/model.glb').read_bytes(),b'foreign')
        self.assertEqual(json.loads((self.root/'backup/publication.json').read_text())['status'],'rollback-conflict')

    def test_stale_saved_pin_rejected(self):
        self.doc['assetSources'][0]['model_sha256']='wrong'
        (self.scenes/'map.rhlos-map.json').write_bytes(encoded(self.doc))
        with self.assertRaises(ValueError): prepare(self.lib,self.stage,self.scenes)

    def test_stale_stage_rejected(self):
        (self.stage/'a/model.glb').write_bytes(b'wrong')
        with self.assertRaises(ValueError): apply(self.plan,self.root/'backup')
        self.assertEqual((self.lib/'a/model.glb').read_bytes(),b'old')


if __name__=='__main__': unittest.main()
