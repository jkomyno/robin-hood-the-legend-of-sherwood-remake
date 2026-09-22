"""Regression checks for links retained across review-gallery revisions."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('shared_gallery', Path(__file__).with_name('build_review_gallery.py'))
gallery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gallery)


class StableGalleryLinks(unittest.TestCase):
    def test_removal_and_new_image_keep_previous_links_valid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source.png'
            source.write_bytes(b'original image fixture')
            manifest = root / 'manifest.json'
            output = root / 'gallery'
            items = [{'id': name, 'name': name, 'status': 'ready-for-user',
                      'solid': str(source), 'textured': str(source)} for name in ('first', 'second')]

            def build():
                manifest.write_text(json.dumps({'map': 'Test map', 'items': items}))
                gallery.build(manifest, output, pending_only=True)
                return json.loads((output / 'evidence.json').read_text())['items']

            first_records = build()
            retained = first_records[1]['images']['solid']
            items.pop(0)
            remaining = build()[0]
            self.assertEqual(remaining['images']['solid']['file'], retained['file'])
            self.assertIn('id="second"', (output / 'index.html').read_text())
            self.assertIn('href="#second"', (output / 'index.html').read_text())
            source.write_bytes(b'revised image fixture')
            revised = build()[0]['images']['solid']
            self.assertNotEqual(revised['file'], retained['file'])
            for record in (retained, revised):
                self.assertEqual(hashlib.sha256((output / record['file']).read_bytes()).hexdigest(),
                                 record['sha256'])
            self.assertTrue(list((output / 'history').glob('*/index.html')))


if __name__ == '__main__':
    unittest.main()
