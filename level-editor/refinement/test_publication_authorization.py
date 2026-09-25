import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from publication_authorization import prepare
from texture_decisions import IMAGE_FIELDS, sha


class PublicationAuthorizationTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        paths = {}
        item = dict(id='test-house', status='ready-for-user', user_approval='pending',
                    review_revision='a' * 64, images={}, reports={})
        for key in (*IMAGE_FIELDS, 'validation', 'review', 'model'):
            path = root / (key + '.bin')
            path.write_bytes(key.encode())
            paths[key] = path
            if key != 'model':
                item['images' if key in IMAGE_FIELDS else 'reports'][key] = dict(
                    file=path.name, sha256=sha(path))
        snapshot = root / 'evidence.json'
        snapshot.write_text(json.dumps({'items': [item]}))
        return root, snapshot, paths, {key: sha(path) for key, path in paths.items()}

    def test_publication_leaves_visual_review_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            root, snapshot, paths, hashes = self.fixture(directory)
            original = snapshot.read_bytes()
            with patch('publication_authorization.evidence', return_value=(paths, hashes)):
                result = prepare(root, root / 'authorization.json', 'Publish all ready assets')
            record = result['decisions'][0]
            self.assertFalse(record['individual_visual_review'])
            self.assertEqual(record['authorization_kind'], 'publish-ready-assets')
            self.assertEqual(record['exact_user_text'], 'Publish all ready assets')
            self.assertEqual(snapshot.read_bytes(), original)

    def test_rejects_held_or_changed_displayed_evidence(self):
        for held in (False, True):
            with self.subTest(held=held), tempfile.TemporaryDirectory() as directory:
                root, snapshot, paths, hashes = self.fixture(directory)
                if held:
                    data = json.loads(snapshot.read_text())
                    data['items'][0]['status'] = 'fix-needed'
                    snapshot.write_text(json.dumps(data))
                else:
                    paths['textured'].write_bytes(b'changed')
                with patch('publication_authorization.evidence', return_value=(paths, hashes)):
                    with self.assertRaises(ValueError):
                        prepare(root, root / 'authorization.json', 'Publish all ready assets')
                self.assertFalse((root / 'authorization.json').exists())


if __name__ == '__main__':
    unittest.main()
