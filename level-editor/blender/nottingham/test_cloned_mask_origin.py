"""Cloned immutable input must bind its actual original mask assignment bytes."""
import copy,json,tempfile,unittest
from pathlib import Path
from build_gallery import frozen_mask_origins,file_hashes,sha

class ClonedMaskOriginTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.old=self.root/'old';self.new=self.root/'new'
        for path in [self.old,self.new]:
            (path/'input').mkdir(parents=True);(path/'mask-reference').mkdir()
            (path/'input/views.json').write_text('frozen cameras')
            (path/'baseline.blend').write_bytes(b'frozen scene')
            (path/'mask-reference/assignments.json').write_text('frozen assignment bytes')
        # Working masks deliberately evolved; the frozen origin must remain authoritative.
        (self.old/'source-masks.json').write_text('subsequent old working masks')
        old=dict(asset_id='asset',baseline_sha256=sha(self.old/'baseline.blend'),
                 source_mask_manifest=str(self.old/'source-masks.json'),mask_reference=str(self.old/'mask-reference'))
        (self.old/'workspace.json').write_text(json.dumps(old))
        self.config=dict(old,source_mask_manifest=str(self.new/'source-masks.json'),
                         mask_reference=str(self.new/'mask-reference'),input_files=file_hashes(self.new/'input'),
                         cloned_mask_origin=dict(workspace=str(self.old),workspace_sha256=sha(self.old/'workspace.json'),
                                                 manifest=str(self.old/'source-masks.json')))
    def test_verified_clone_uses_exact_frozen_assignment(self):
        mapping=frozen_mask_origins(self.new,self.config)
        self.assertEqual(mapping[self.old/'source-masks.json'],self.new/'mask-reference/assignments.json')
        self.assertEqual(sha(mapping[self.old/'source-masks.json']),sha(self.old/'mask-reference/assignments.json'))
    def test_wrong_alias_rejected(self):
        config=copy.deepcopy(self.config);config['cloned_mask_origin']['manifest']=str(self.old/'unrelated.json')
        with self.assertRaisesRegex(ValueError,'path differs'):frozen_mask_origins(self.new,config)
    def test_changed_origin_configuration_rejected(self):
        config=copy.deepcopy(self.config);config['cloned_mask_origin']['workspace_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'configuration changed'):frozen_mask_origins(self.new,config)
    def test_changed_frozen_assignment_rejected(self):
        (self.new/'mask-reference/assignments.json').write_text('forged assignment bytes')
        with self.assertRaisesRegex(ValueError,'assignments differ'):frozen_mask_origins(self.new,self.config)
    def test_changed_input_rejected(self):
        (self.new/'input/views.json').write_text('changed cameras')
        with self.assertRaisesRegex(ValueError,'input differs'):frozen_mask_origins(self.new,self.config)

if __name__=='__main__':unittest.main()
