"""Publication rejects stale derivatives without replacing a previously valid catalog."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from asset_index import validate_asset_index, write_asset_index


class AssetIndexTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.index = {'version': 1, 'assets': [
            {'id': 'house', 'model': 'model.glb', 'lossy_model': 'lossy.glb'}]}
        (self.root/'model.glb').write_bytes(b'original')
        (self.root/'lossy.glb').write_bytes(b'optimized')
        self.receipt = {key: hashlib.sha256((self.root/name).read_bytes()).hexdigest()
                        for key, name in [('source', 'model.glb'), ('output', 'lossy.glb')]}
        (self.root/'lossy.glb.receipt.json').write_text(json.dumps(self.receipt))
        write_asset_index(self.root, self.index)
        self.previous = (self.root/'index.json').read_bytes()

    def reject(self, pattern):
        with self.assertRaisesRegex(ValueError, pattern):
            write_asset_index(self.root, self.index)
        self.assertEqual((self.root/'index.json').read_bytes(), self.previous)
        self.assertEqual(list(self.root.glob('.index.json-*.tmp')), [])

    def test_source_change_rejects_entire_index_including_unchanged_entries(self):
        (self.root/'model.glb').write_bytes(b'republished')
        self.index['assets'].append({'id': 'new', 'model': 'new.glb'})
        self.reject('house: lossy receipt does not bind the current model')

    def test_corrupt_output_is_rejected(self):
        (self.root/'lossy.glb').write_bytes(b'corrupt')
        self.reject('house: lossy model bytes differ')

    def test_missing_and_malformed_receipts_are_rejected(self):
        receipt = self.root/'lossy.glb.receipt.json'
        for raw in ['[]', '{', '{}', '{"source": 1, "output": null}']:
            with self.subTest(raw=raw):
                receipt.write_text(raw)
                self.reject('house:')
        receipt.unlink()
        self.reject('house: lossy model or receipt missing')

    def test_missing_models_are_rejected(self):
        (self.root/'lossy.glb').unlink()
        self.reject('house: lossy model or receipt missing')
        (self.root/'lossy.glb').write_bytes(b'optimized')
        (self.root/'model.glb').unlink()
        self.reject('house: cannot validate lossy asset')

    def test_preflight_validates_staged_payloads_and_unchanged_live_assets(self):
        stage = self.root/'stage'; stage.mkdir()
        (stage/'model.glb').write_bytes(b'new source')
        (stage/'lossy.glb').write_bytes(b'new output')
        (stage/'receipt.json').write_text(json.dumps({
            'source': hashlib.sha256(b'new source').hexdigest(),
            'output': hashlib.sha256(b'new output').hexdigest()}))
        files = {'model.glb': stage/'model.glb', 'lossy.glb': stage/'lossy.glb',
                 'lossy.glb.receipt.json': stage/'receipt.json'}
        validate_asset_index(self.root, self.index, files=files)
        del files['model.glb']
        with self.assertRaisesRegex(ValueError, 'house: lossy receipt does not bind'):
            validate_asset_index(self.root, self.index, files=files)
        self.assertEqual((self.root/'index.json').read_bytes(), self.previous)

    def test_raw_bytes_are_preserved_and_no_lossy_model_is_required(self):
        data = b'{"version":1,"assets":[{"id":"source-only","model":"model.glb"}]}\n'
        write_asset_index(self.root, data)
        self.assertEqual((self.root/'index.json').read_bytes(), data)

    def test_failed_replace_preserves_index_and_cleans_temporary(self):
        with patch('asset_index.os.replace', side_effect=OSError('injected')):
            with self.assertRaisesRegex(OSError, 'injected'):
                write_asset_index(self.root, {'assets': []})
        self.assertEqual((self.root/'index.json').read_bytes(), self.previous)
        self.assertEqual(list(self.root.glob('.index.json-*.tmp')), [])

    def test_duplicate_ids_and_unsafe_paths_are_rejected(self):
        self.index['assets'].append(dict(self.index['assets'][0]))
        self.reject('Duplicate asset index ID')
        self.index['assets'].pop()
        for value in ['../escape.glb', '/absolute.glb', 'a//b.glb', '', None]:
            with self.subTest(value=value):
                self.index['assets'][0]['lossy_model'] = value
                self.reject('Unsafe asset index path')


if __name__ == '__main__':
    unittest.main()
