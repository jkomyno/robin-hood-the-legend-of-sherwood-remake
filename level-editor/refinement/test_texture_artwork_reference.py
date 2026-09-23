import json
from pathlib import Path
import unittest

from PIL import Image

from build_texture_gallery import artwork_reference, collect
from texture_decisions import record, sha
from test_texture_states import TextureStateTests


class TextureArtworkReferenceTests(unittest.TestCase):
    setUp = TextureStateTests.setUp
    update = TextureStateTests.update
    make_experiment = TextureStateTests.make_experiment
    build = TextureStateTests.build

    def add_reference(self, experiment):
        packet = experiment / 'frozen-review'
        packet.mkdir()
        source = packet / 'original.png'
        Image.new('RGBA', (20, 18), (140, 90, 50, 255)).save(source)
        with Image.open(source) as image:
            image.crop((2, 3, 18, 15)).save(packet / 'context.png')
        frames = packet / 'views.json'
        frames.write_text(json.dumps({'source_image': str(source), 'source_sha256': sha(source),
            'context_crop': {'left': 2, 'top': 3, 'right': 18, 'bottom': 15}}))
        (experiment / 'views.json').write_text(json.dumps({'reviewed_packet': str(packet),
            'reviewed_manifest_sha256': sha(frames)}))
        return packet

    def test_addition_preserves_review_id_and_existing_approval(self):
        _, old = self.build()
        record(self.output / 'gallery', self.output / 'decisions.json',
               'leicester-bridge: approved [review ' + old[0]['review_revision'][:16] + ']')
        self.add_reference(self.primary)
        self.add_reference(self.secondary)
        fresh = self.root / 'fresh-review'
        collect(self.experiments, fresh, 'Leicester')
        item = json.loads((fresh / 'gallery/evidence.json').read_text())['items'][0]
        self.assertEqual(item['review_revision'], old[0]['review_revision'])
        self.assertEqual(item['images'], old[0]['images'])
        self.assertEqual(set(item['reference_images']), {'original', 'applied-original'})
        for reference in item['reference_images'].values():
            self.assertEqual(sha(fresh / 'gallery' / reference['file']), reference['sha256'])
        page = (fresh / 'gallery/index.html').read_text()
        self.assertIn('Original artwork with surrounding context', page)
        self.assertIn('Applied endpoint: original artwork', page)
        # The pre-feature decision remains bound to the exact same texture evidence.
        result = collect(self.experiments, self.output, 'Leicester')
        self.assertEqual(result['approved'], 1)
        self.assertEqual(result['candidates'], 0)

    def test_wrong_crop_cannot_be_displayed_as_original_art(self):
        packet = self.add_reference(self.primary)
        Image.new('RGBA', (16, 12), (0, 0, 255, 255)).save(packet / 'context.png')
        with self.assertRaisesRegex(ValueError, 'raw source crop'):
            artwork_reference(self.primary)

    def test_changed_source_is_rejected(self):
        packet = self.add_reference(self.primary)
        Image.new('RGBA', (20, 18), (0, 0, 255, 255)).save(packet / 'original.png')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            artwork_reference(self.primary)


if __name__ == '__main__':
    unittest.main()
