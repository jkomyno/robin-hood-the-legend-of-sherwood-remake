import json
from pathlib import Path
import tempfile
import unittest

from promote_staged_publication import prepare, apply


class PromotionTests(unittest.TestCase):
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
        prepare(self.stage, self.library, self.main, 'leicester')

    def test_first_publication_creates_main_and_preserves_other_entries(self):
        apply(self.stage / 'promotion.json')
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
            apply(self.stage / 'promotion.json')
        self.assertEqual((self.library / 'scenes/leicester-volumes.scene.glb').read_text(), 'old map')
        self.assertEqual(self.main.read_text(), 'concurrent change')


if __name__ == '__main__':
    unittest.main()
