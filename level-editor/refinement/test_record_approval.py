"""Synthetic decisions only: legacy compatibility and exact-revision binding."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from record_approval import record
from review_evidence import bind_decision, load_decisions, sha


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root/'manifest.json'
        for name in ('model.blend', 'solid.png', 'textured.png'):
            (self.root/name).write_text('synthetic '+name)
        self.item = {'id':'fixture','status':'ready-for-user','workspace':str(self.root),
                     'model':'model.blend','solid':'solid.png','textured':'textured.png'}

    def save(self):
        self.path.write_text(json.dumps({'items':[self.item]}))

    def exact(self):
        evidence={key:{'path':str(self.root/self.item[key]),'sha256':sha(self.root/self.item[key])}
                  for key in ('solid','textured')}
        identity={'asset_id':'fixture','model_sha256':sha(self.root/'model.blend'),
                  'evidence':{key:entry['sha256'] for key,entry in evidence.items()}}
        self.item['revision']={'model_sha256':identity['model_sha256'],'evidence':evidence,
            'sha256':hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
        self.save()
        return self.item['revision']['sha256']

    def test_legacy_fields_and_three_hashes(self):
        self.save()
        record(self.path,['fixture'],'Synthetic explicit legacy approval')
        item=json.loads(self.path.read_text())['items'][0]
        self.assertEqual(item['status'],'approved')
        self.assertEqual(set(item['approved_sha256']),{'model','solid','textured'})
        self.assertEqual(item['approved_sha256']['model'],sha(self.root/'model.blend'))

    def test_exact_archive_and_stale_binding(self):
        revision=self.exact()
        before=self.path.read_bytes()
        record(self.path,['fixture'],'Synthetic explicit geometry approval',revision_sha256=revision)
        self.assertEqual(self.path.read_bytes(),before)
        records=load_decisions(self.root/'decisions.json',{'fixture'})
        self.assertEqual(records[0]['scope'],'geometry')
        self.assertTrue((self.root/'reviewed-revisions/fixture'/revision/'solid.png').is_file())
        bind_decision(self.item,records)
        self.assertEqual(self.item['user_approval'],'approved')
        self.item['revision']['sha256']='0'*64
        bind_decision(self.item,records)
        self.assertEqual(self.item['decision_state'],'stale')

    def test_incomplete_or_changed_evidence_cannot_approve(self):
        self.item['status']='validation-pending';self.exact()
        with self.assertRaises(ValueError):record(self.path,['fixture'],'Synthetic approval')
        self.assertFalse((self.root/'decisions.json').exists())
        self.item['status']='ready-for-user';self.exact()
        (self.root/'solid.png').write_text('changed')
        with self.assertRaises(ValueError):record(self.path,['fixture'],'Synthetic approval')
        self.assertFalse((self.root/'decisions.json').exists())

    def test_expected_revision_mismatch_and_rejection(self):
        self.exact()
        with self.assertRaises(ValueError):
            record(self.path,['fixture'],'Synthetic approval',revision_sha256='0'*64)
        record(self.path,['fixture'],'Synthetic explicit rejection',result='rejected')
        records=load_decisions(self.root/'decisions.json',{'fixture'})
        self.assertEqual(records[0]['decision'],'rejected')


if __name__=='__main__':unittest.main()
