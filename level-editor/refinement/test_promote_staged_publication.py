"""Small filesystem fixtures exercise static endpoint promotion without Blender."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import promote_staged_publication as promotion


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.stage, self.library = root / 'stage', root / 'library'
        self.main = root / 'main.blend'
        self.stage.mkdir()
        (self.stage / 'assets/bridge').mkdir(parents=True)
        (self.library / '3d-assets/bridge').mkdir(parents=True)
        (self.library / 'scenes').mkdir()
        self.entry = {'id': 'bridge', 'descriptor': 'bridge/asset.json', 'model': 'bridge/raised.glb'}
        self.descriptor = {'id': 'bridge', 'model': 'raised.glb'}
        self.write_json(self.stage / 'assets/index.json', {'assets': [self.entry]})
        self.write_json(self.library / '3d-assets/index.json', {'assets': []})
        for name in ('asset-verification', 'handoff-verification', 'browser-result'):
            self.write_json(self.stage / f'{name}.json', {'status': 'PASS'})
        for name in ('worker.blend', 'derby.scene.glb', 'derby.level3d.json', 'assets/bridge/raised.glb', 'assets/bridge/lowered.glb'):
            (self.stage / name).write_bytes(('new:' + name).encode())
        self.main.write_bytes(b'old blend')
        self.write_json(self.library / 'scenes/derby-volumes.scene.json', {'protected': True})

    @staticmethod
    def write_json(path, value):
        path.write_text(json.dumps(value))

    def variants(self):
        self.descriptor['state_variants'] = {
            'initial': {'name': 'Raised', 'model': 'raised.glb'},
            'applied': {'name': 'Lowered', 'model': 'lowered.glb'},
        }

    def prepare(self):
        self.write_json(self.stage / 'assets/bridge/asset.json', self.descriptor)
        promotion.prepare(self.stage, self.library, self.main, 'derby')
        return json.loads((self.stage / 'promotion.json').read_text())

    def test_existing_asset_keeps_original_six_file_manifest(self):
        manifest = self.prepare()
        self.assertEqual(len(manifest['files']), 6)
        promotion.apply(self.stage / 'promotion.json')
        self.assertFalse((self.library / '3d-assets/bridge/lowered.glb').exists())

    def test_variants_deduplicate_default_and_copy_both_with_hashes(self):
        self.variants()
        manifest = self.prepare()
        self.assertEqual(len(manifest['files']), 7)
        self.assertEqual(len({item['target'] for item in manifest['files']}), 7)
        promotion.apply(self.stage / 'promotion.json')
        for item in manifest['files']:
            self.assertEqual(promotion.sha(Path(item['target'])), item['source_sha256'])
        self.assertEqual(json.loads((self.stage / 'promotion.json').read_text())['status'], 'APPLIED')

    def test_variant_hash_change_rejects_before_any_write(self):
        self.variants()
        self.prepare()
        (self.stage / 'assets/bridge/lowered.glb').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'input/target changed'):
            promotion.apply(self.stage / 'promotion.json')
        self.assertEqual(self.main.read_bytes(), b'old blend')

    def test_late_variant_failure_rolls_back_old_and_new_files(self):
        self.variants()
        raised = self.library / '3d-assets/bridge/raised.glb'
        raised.write_bytes(b'old raised')
        manifest = self.prepare()
        copy = promotion.shutil.copy2

        def fail_variant(source, target):
            if Path(source) == self.stage / 'assets/bridge/lowered.glb':
                raise OSError('simulated variant copy failure')
            return copy(source, target)

        with patch.object(promotion.shutil, 'copy2', side_effect=fail_variant):
            with self.assertRaisesRegex(OSError, 'simulated'):
                promotion.apply(self.stage / 'promotion.json')
        for item in manifest['files']:
            self.assertEqual(promotion.sha(Path(item['target'])), item['previous_sha256'])

    def test_unsafe_variant_paths_and_symlinks_are_rejected(self):
        self.variants()
        for model in ('/outside.glb', '../outside.glb', 'nested/../../outside.glb', 'a\\b.glb', 'a//b.glb', ''):
            with self.subTest(model=model):
                self.descriptor['state_variants']['applied']['model'] = model
                self.write_json(self.stage / 'assets/bridge/asset.json', self.descriptor)
                with self.assertRaisesRegex(ValueError, 'Unsafe'):
                    promotion.asset_file_pairs(self.stage / 'assets', self.library / '3d-assets', self.entry)
        self.descriptor['state_variants']['applied']['model'] = 'escape.glb'
        self.write_json(self.stage / 'assets/bridge/asset.json', self.descriptor)
        (self.stage / 'assets/bridge/escape.glb').symlink_to(self.main)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            promotion.asset_file_pairs(self.stage / 'assets', self.library / '3d-assets', self.entry)
        self.descriptor['state_variants']['applied']['model'] = 'lowered.glb'
        self.write_json(self.stage / 'assets/bridge/asset.json', self.descriptor)
        (self.library / '3d-assets/bridge/lowered.glb').symlink_to(self.main)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            promotion.asset_file_pairs(self.stage / 'assets', self.library / '3d-assets', self.entry)

    def test_variant_metadata_rejects_unknown_endpoints(self):
        self.descriptor['state_variants'] = {'moving': {'name': 'Moving', 'model': 'lowered.glb'}}
        with self.assertRaisesRegex(ValueError, 'Invalid static'):
            self.prepare()


class FirstPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.stage = self.root / 'stage'
        self.library = self.root / 'library'
        self.main = self.root / 'main' / 'leicester.blend'
        for path in [self.stage / 'assets', self.library / '3d-assets', self.library / 'scenes']:
            path.mkdir(parents=True)
        for name in ['asset-verification.json', 'handoff-verification.json', 'browser-result.json']:
            (self.stage / name).write_text('{"status":"PASS"}')
        (self.stage / 'assets/index.json').write_text('{"assets":[]}')
        (self.library / '3d-assets/index.json').write_text('{"assets":[{"id":"other-map"}]}')
        for name in ['worker.blend', 'leicester.scene.glb', 'leicester.level3d.json']:
            (self.stage / name).write_text('staged ' + name)
        (self.library / 'scenes/leicester-volumes.scene.glb').write_text('old map')
        (self.library / 'scenes/leicester-volumes.scene.json').write_text('protected document')
        promotion.prepare(self.stage, self.library, self.main, 'leicester')

    def test_first_publication_creates_main_and_preserves_other_entries(self):
        promotion.apply(self.stage / 'promotion.json')
        self.assertEqual(self.main.read_text(), 'staged worker.blend')
        index = json.loads((self.library / '3d-assets/index.json').read_text())
        self.assertEqual(index['assets'], [{'id': 'other-map'}])
        self.assertEqual((self.library / 'scenes/leicester-volumes.scene.json').read_text(), 'protected document')
        report = json.loads((self.stage / 'promotion.json').read_text())
        self.assertEqual(report['status'], 'APPLIED')
        previous_map = next(r for r in report['files'] if r['target'].endswith('leicester-volumes.scene.glb'))
        self.assertEqual(Path(previous_map['backup']).read_text(), 'old map')

    def test_new_target_created_after_preparation_blocks_publication(self):
        self.main.parent.mkdir()
        self.main.write_text('concurrent change')
        with self.assertRaisesRegex(ValueError, 'Promotion input/target changed'):
            promotion.apply(self.stage / 'promotion.json')
        self.assertEqual((self.library / 'scenes/leicester-volumes.scene.glb').read_text(), 'old map')
        self.assertEqual(self.main.read_text(), 'concurrent change')


if __name__ == '__main__':
    unittest.main()
