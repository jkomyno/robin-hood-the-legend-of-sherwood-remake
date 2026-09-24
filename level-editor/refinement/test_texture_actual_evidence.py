import hashlib
from pathlib import Path
import tempfile
import unittest
from texture_actual_evidence import actual_sheet


class ActualSheetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'bake'
        for folder, data in [('actual', b'old'), ('actual-depth', b'corrected')]:
            path = self.root / folder / 'textured.png'
            path.parent.mkdir(parents=True)
            path.write_bytes(data)

    def review(self, data, **fields):
        return dict(actual_sheet_sha256=hashlib.sha256(data).hexdigest(), **fields)

    def test_default_does_not_prefer_new_directory(self):
        self.assertEqual(actual_sheet(self.root, self.review(b'old')), self.root / 'actual/textured.png')

    def test_explicit_review_selects_corrected_sheet(self):
        self.assertEqual(actual_sheet(self.root, self.review(b'corrected', actual_sheet_path='actual-depth/textured.png')), self.root / 'actual-depth/textured.png')

    def test_stale_hash_rejected(self):
        with self.assertRaises(ValueError):
            actual_sheet(self.root, self.review(b'old', actual_sheet_path='actual-depth/textured.png'))

    def test_path_escape_rejected(self):
        outside = self.root.parent / 'outside.png'
        outside.write_bytes(b'old')
        (self.root / 'escape.png').symlink_to(outside)
        for path in ('../outside.png', str(outside), 'escape.png'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                actual_sheet(self.root, self.review(b'old', actual_sheet_path=path))


if __name__ == '__main__':
    unittest.main()
