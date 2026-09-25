"""Deletion must fail closed for changed or publication-protected autosaves."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from cleanup_review_autosaves import preflight, sha


class CleanupGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.work = self.root / 'work'
        self.work.mkdir()
        self.backup = self.work / 'model.blend1'
        self.backup.write_bytes(b'old save')
        self.current = self.work / 'model.blend'
        self.current.write_bytes(b'current approved model')
        self.manifest = self.root / 'manifest.json'
        self.manifest.write_text(json.dumps([dict(path='work/model.blend1',
            bytes=self.backup.stat().st_size, sha256=sha(self.backup))]))
        self.union = self.root / 'union.json'
        self.union.write_text(json.dumps(dict(status='FINAL-126-IMPORTS', files={})))

    def check(self):
        return preflight(self.root, self.work, self.manifest, sha(self.manifest),
                         self.union, sha(self.union), 1)

    def test_valid_preflight_is_read_only(self):
        self.assertEqual(len(self.check()), 1)
        self.assertEqual(self.backup.read_bytes(), b'old save')
        self.assertEqual(self.current.read_bytes(), b'current approved model')

    def test_partial_union_rejected(self):
        self.union.write_text(json.dumps(dict(status='PARTIAL-105-IMPORTS', files={})))
        with self.assertRaisesRegex(ValueError, 'Final complete'):
            self.check()

    def test_hash_reference_elsewhere_protects_backup(self):
        self.union.write_text(json.dumps(dict(status='FINAL-126-IMPORTS',
            files={str(self.work / 'other.blend'): sha(self.backup)})))
        with self.assertRaisesRegex(ValueError, 'protected'):
            self.check()

    def test_changed_backup_rejected(self):
        self.backup.write_bytes(b'new save')
        with self.assertRaisesRegex(ValueError, 'content changed'):
            self.check()

    def test_hard_link_rejected(self):
        os.link(self.backup, self.work / 'retained.blend')
        with self.assertRaisesRegex(ValueError, 'link count changed'):
            self.check()

    def test_missing_current_model_rejected(self):
        self.current.unlink()
        with self.assertRaisesRegex(ValueError, 'Paired current'):
            self.check()

    def test_changed_reviewed_list_rejected(self):
        expected = sha(self.manifest)
        self.manifest.write_text('[]')
        with self.assertRaisesRegex(ValueError, 'manifest'):
            preflight(self.root, self.work, self.manifest, expected,
                      self.union, sha(self.union), 1)


if __name__ == '__main__':
    unittest.main()
