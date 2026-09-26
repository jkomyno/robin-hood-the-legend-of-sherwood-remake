import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from publish_library import stage_library
from cloudflare_publish import worker_config


def glb(document):
    raw = json.dumps(document).encode()
    raw += b' ' * (-len(raw) % 4)
    return struct.pack('<5I', 0x46546c67, 2, 20 + len(raw), len(raw), 0x4e4f534a) + raw


class PublishLibraryTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.library = self.root/'library'
        self.asset = self.library/'3d-assets/house'
        self.asset.mkdir(parents=True)
        (self.library/'scenes').mkdir()
        (self.asset/'asset.json').write_text(json.dumps(
            {'id': 'house', 'name': 'House', 'source_map': 'Derby', 'model': 'model.glb'}))
        (self.asset/'model.glb').write_bytes(b'original')
        self.lossy(glb({'asset': {'version': '2.0'}}))
        (self.asset/'private.txt').write_text('authoring only')

    def lossy(self, data):
        (self.asset/'lossy.glb').write_bytes(data)
        (self.asset/'lossy.glb.receipt.json').write_text(json.dumps({
            'source': hashlib.sha256(b'original').hexdigest(),
            'output': hashlib.sha256(data).hexdigest()}))

    def stage(self):
        return stage_library(self.library, self.root/'deploy')

    def test_allowlist_and_source_identity(self):
        report = self.stage()
        self.assertEqual(set(report['payloads']), {'3d-assets/house/asset.json',
            '3d-assets/house/lossy.glb', '3d-assets/index.json', 'scenes/index.json'})
        site = self.root/'deploy/site/editor/library'
        index = json.loads((site/'3d-assets/index.json').read_bytes())
        entry = index['assets'][0]
        self.assertEqual(entry['model_sha256'], hashlib.sha256(b'original').hexdigest())
        self.assertEqual(entry['preview_model'], entry['lossy_model'])
        self.assertFalse((site/'3d-assets/house/model.glb').exists())
        config = json.loads((self.root/'deploy/wrangler.json').read_bytes())
        self.assertEqual(config['name'], 'robinhood-editor-library')
        self.assertEqual([r['pattern'] for r in config['routes']], [
            'robinhood.phiresky.xyz/editor/library', 'robinhood.phiresky.xyz/editor/library/*'])
        self.assertFalse(config['workers_dev'])

    def test_stale_source_rejected(self):
        (self.asset/'model.glb').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'receipt'):
            self.stage()

    def test_external_resources_rejected(self):
        self.lossy(glb({'images': [{'uri': 'private.png'}]}))
        with self.assertRaisesRegex(ValueError, 'external resource'):
            self.stage()

    def test_stale_map_pin_rejected(self):
        (self.library/'scenes/test.rhlos-map.json').write_text(json.dumps({
            'version': 1, 'sceneAssets': [{'model': '3d-assets/house/model.glb',
                                        'model_sha256': '0'*64}]}))
        with self.assertRaisesRegex(ValueError, 'no matching optimized'):
            self.stage()

    def test_editor_routes(self):
        config = worker_config('robinhood-editor', '/editor', 'auto-trailing-slash')
        self.assertEqual([r['pattern'] for r in config['routes']], [
            'robinhood.phiresky.xyz/editor', 'robinhood.phiresky.xyz/editor/*'])
        self.assertEqual(config['assets']['html_handling'], 'auto-trailing-slash')


if __name__ == '__main__':
    unittest.main()
