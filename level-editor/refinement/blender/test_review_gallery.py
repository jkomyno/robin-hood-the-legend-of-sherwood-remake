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
            self.assertEqual(remaining['review_revision'], first_records[1]['review_revision'])
            self.assertEqual(remaining['images']['solid']['file'], retained['file'])
            self.assertIn('id="second"', (output / 'index.html').read_text())
            self.assertIn('href="#second"', (output / 'index.html').read_text())
            source.write_bytes(b'revised image fixture')
            revised_record = build()[0]
            self.assertNotEqual(revised_record['review_revision'], remaining['review_revision'])
            revised = revised_record['images']['solid']
            self.assertNotEqual(revised['file'], retained['file'])
            for record in (retained, revised):
                self.assertEqual(hashlib.sha256((output / record['file']).read_bytes()).hexdigest(),
                                 record['sha256'])
            self.assertTrue(list((output / 'history').glob('*/index.html')))

    def test_model_revision_and_blocked_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source.png'
            source.write_bytes(b'image')
            model = root / 'model.blend'
            model.write_bytes(b'geometry one')
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'items': [{'id': 'asset', 'name': 'Asset',
                'status': 'fix-needed', 'model': str(model), 'solid': str(source), 'textured': str(source)}]}))
            output = root / 'gallery'
            gallery.build(manifest, output)
            first = json.loads((output / 'evidence.json').read_text())['items'][0]['review_revision']
            self.assertIn('<option value="approved" disabled>', (output / 'index.html').read_text())
            model.write_bytes(b'geometry two')
            gallery.build(manifest, output)
            second = json.loads((output / 'evidence.json').read_text())['items'][0]['review_revision']
            self.assertNotEqual(first, second)

    def test_animation_views_share_one_decision_and_bind_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, state = root / 'source.png', root / 'state.png'
            source.write_bytes(b'base image')
            state.write_bytes(b'initial state')
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'items': [{'id': 'gate', 'name': 'Gate',
                'status': 'ready-for-user', 'solid': str(source), 'textured': str(source),
                'animation_reviews': [{'id': 'initial', 'name': 'Initial', 'solid': str(state),
                    'textured': str(state), 'context': str(source)}]}]}))
            output = root / 'gallery'
            gallery.build(manifest, output)
            page = (output / 'index.html').read_text()
            self.assertEqual(page.count('<article '), 1)
            self.assertEqual(page.count('class="decision"'), 1)
            self.assertIn('<details class="animation-state">', page)
            first = json.loads((output / 'evidence.json').read_text())['items'][0]
            self.assertIn('animation_initial_textured', first['images'])
            state.write_bytes(b'changed state')
            gallery.build(manifest, output)
            second = json.loads((output / 'evidence.json').read_text())['items'][0]
            self.assertNotEqual(first['review_revision'], second['review_revision'])


if __name__ == '__main__':
    unittest.main()
