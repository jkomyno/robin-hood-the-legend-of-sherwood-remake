import json
from pathlib import Path
import tempfile
import unittest

from texture_decisions import IMAGE_FIELDS, bind, record, sha


class TextureDecisionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.gallery = self.root / 'gallery'
        self.gallery.mkdir()
        self.item = {'id': 'asset', 'review_revision': 'a' * 64, 'user_approval': 'pending'}
        for key in (*IMAGE_FIELDS, 'validation', 'review'):
            path = self.root / (key + '.data')
            path.write_text(key)
            self.item[key] = str(path)
        (self.root / 'worker.blend').write_bytes(b'model')
        Path(self.item['review']).write_text(json.dumps({
            'baked_model_sha256': sha(self.root / 'worker.blend'),
            'actual_sheet_sha256': sha(self.item['textured'])}))
        for section, fields in [('images', IMAGE_FIELDS), ('reports', ('validation', 'review'))]:
            self.item[section] = {}
            for key in fields:
                target = self.gallery / key
                target.write_bytes(Path(self.item[key]).read_bytes())
                self.item[section][key] = {'sha256': sha(target), 'file': key}
        (self.gallery / 'evidence.json').write_text(json.dumps({'items': [self.item]}))
        self.decisions = self.root / 'decisions.json'
        self.text = 'asset: approved [review ' + 'a' * 16 + ']'

    def test_approval_archives_model_and_binds_exact_evidence(self):
        record(self.gallery, self.decisions, self.text)
        decisions = json.loads(self.decisions.read_text())['decisions']
        bind(self.item, decisions)
        self.assertEqual(self.item['user_approval'], 'approved')
        self.assertEqual((Path(decisions[0]['archive']) / 'model.blend').read_bytes(), b'model')
        Path(self.item['solid']).write_bytes(b'changed lighting')
        self.item['user_approval'] = 'pending'
        bind(self.item, decisions)
        self.assertEqual(self.item['user_approval'], 'pending')

    def test_changed_model_rejected_before_recording(self):
        (self.root / 'worker.blend').write_bytes(b'changed model')
        with self.assertRaisesRegex(ValueError, 'Baked texture evidence changed'):
            record(self.gallery, self.decisions, self.text)
        self.assertFalse(self.decisions.exists())

    def test_wrong_display_revision_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Displayed texture revision differs'):
            record(self.gallery, self.decisions, self.text.replace('a' * 16, 'b' * 16))
        self.assertFalse(self.decisions.exists())

    def test_later_decision_does_not_revive_older_approval(self):
        record(self.gallery, self.decisions, self.text)
        decisions = json.loads(self.decisions.read_text())['decisions']
        decisions.append({**decisions[0], 'decision': 'rejected', 'evidence_sha256': {}})
        bind(self.item, decisions)
        self.assertEqual(self.item['user_approval'], 'pending')


if __name__ == '__main__':
    unittest.main()
