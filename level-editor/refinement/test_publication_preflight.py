import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from publication_preflight import run
from review_evidence import sha


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.model=self.root/'model';self.model.write_bytes(b'model')
        self.source=self.root/'source';self.source.write_bytes(b'source')
        self.code=self.root/'validator.py';self.code.write_text('exact code')
        self.item=dict(asset_id='house',blend_path=str(self.model),blend_sha256=sha(self.model),object_names=['wall'],
            source_nodes=['node'],geometry_revision_sha256='revision',texture_states=[],render_object_names=['wall'],
            geometry_manifest='manifest',texture_decisions='decisions',geometry_decisions='geometry',
            protected_files={str(p):sha(p) for p in [self.model,self.source]})
        self.plan={'imports':[self.item]};self.receipt=self.root/'preflight.json';self.calls=[]

    def check(self):
        def validate(*args):self.calls.append('validate');return copy.deepcopy(self.item)
        def verify(item):
            self.calls.append('verify')
            return dict(geometry_verified=True,model_sha256=item['blend_sha256'],object_names=item['object_names'])
        return run(self.plan,self.receipt,validate,verify,runtime={'version':'fixture'},validator_files=[self.code])

    def test_complete_fresh_then_exact_reuse(self):
        first=self.check();self.assertEqual(self.calls,['validate','verify'])
        self.assertEqual(self.check(),first);self.assertEqual(len(self.calls),2)

    def test_rejects_changed_source_model_or_validator(self):
        self.check()
        for path in [self.source,self.model,self.code]:
            previous=path.read_bytes();path.write_bytes(b'changed')
            with self.subTest(path=path),self.assertRaises(ValueError):self.check()
            path.write_bytes(previous)

    def test_rejects_missing_check_and_metadata(self):
        self.check();data=json.loads(self.receipt.read_text())
        data['checks']=[];self.receipt.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'missing geometry'):self.check()
        self.plan['imports'][0]['render_object_names']=[]
        with self.assertRaisesRegex(ValueError,'plan, runtime or validator'):self.check()

    def test_hash_cache_rejects_same_size_rewrite_and_restored_mtime(self):
        before=sha(self.source);stamp=self.source.stat()
        self.source.write_bytes(b'CHANGED'[:stamp.st_size])
        os.utime(self.source,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
        self.assertNotEqual(sha(self.source),before)
        replacement=self.root/'replacement';replacement.write_bytes(b'source')
        replacement.replace(self.source)
        self.assertEqual(sha(self.source),before)

    def test_no_receipt_on_failed_geometry(self):
        def fail(_):raise ValueError('bad geometry')
        with self.assertRaises(ValueError):run(self.plan,self.receipt,lambda *a:self.item,fail,
            runtime={},validator_files=[self.code])
        self.assertFalse(self.receipt.exists())

if __name__=='__main__':unittest.main()
