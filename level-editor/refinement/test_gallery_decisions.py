"""Guard decisions made while candidates and the pending gallery change."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from record_approval import record_gallery_decision


class GalleryDecisionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.gallery = self.root / 'gallery'
        self.gallery.mkdir()
        self.workspace = self.root / 'asset'
        (self.workspace / 'modified').mkdir(parents=True)
        (self.workspace / 'model.blend').write_bytes(b'reviewed model')
        (self.workspace / 'modified/views.json').write_text('{}')
        (self.workspace / 'modified/solid.png').write_bytes(b'reviewed solid')
        self.records = self.root / 'decisions.json'
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        report = {'model_sha256': digest(self.workspace / 'model.blend'),
                  'packet_hashes': {'modified': {
                      name: digest(self.workspace / 'modified' / name)
                      for name in ('views.json', 'solid.png')}}}
        (self.gallery / 'ownership.json').write_text(json.dumps(report))
        (self.gallery / 'evidence.json').write_text(json.dumps({'items': [{
            'id': 'fixture', 'workspace': str(self.workspace),
            'reports': {'ownership': {'file': 'ownership.json'}}}]}))

    def decide(self, decision):
        return record_gallery_decision(self.gallery, self.records, 'fixture',
                                       decision, 'Synthetic explicit ' + decision)

    def test_archive_and_reopen_hidden_card(self):
        record = self.decide('approved')
        archive = Path(record['evidence_directory'])
        self.assertEqual((archive / 'model.blend').read_bytes(), b'reviewed model')
        self.assertEqual((archive / 'modified/solid.png').read_bytes(), b'reviewed solid')
        history = self.gallery / 'history/previous'
        history.mkdir(parents=True)
        for name in ('ownership.json', 'evidence.json'):
            (self.gallery / name).rename(history / name)
        (self.gallery / 'evidence.json').write_text('{"items": []}')
        self.decide('revision-requested')
        records = json.loads(self.records.read_text())
        self.assertEqual(records['approvals'][0]['decision'], 'revision-requested')
        self.assertEqual(records['history'][0]['decision'], 'approved')
        self.assertTrue((archive / 'model.blend').exists())

    def test_changed_model_cannot_approve(self):
        (self.workspace / 'model.blend').write_bytes(b'new unreviewed model')
        with self.assertRaisesRegex(ValueError, 'model differs'):
            self.decide('approved')
        self.assertFalse(self.records.exists())

    def test_changed_render_cannot_approve(self):
        (self.workspace / 'modified/solid.png').write_bytes(b'new unreviewed render')
        with self.assertRaisesRegex(ValueError, 'packet differs'):
            self.decide('approved')
        self.assertFalse(self.records.exists())


if __name__ == '__main__':
    unittest.main()
