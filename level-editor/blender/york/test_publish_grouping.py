"""Exercise publication rollback at the point after York's directory is replaced."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import publish_grouping as publication


class InstallationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.library, self.stage = root/'library', root/'stage'
        for directory in ('3d-assets/york/old-group', '3d-assets/derby', 'scenes'):
            (self.library/directory).mkdir(parents=True)
        (self.library/'3d-assets/york/old-group/model.glb').write_bytes(b'old York')
        (self.library/'3d-assets/derby/model.glb').write_bytes(b'other map')
        (self.library/'3d-assets/index.json').write_text('old index')
        (self.library/'scenes/york.rhlos-map.json').write_text('{}')
        (self.stage/'map-assets/3d-assets/york/named-house').mkdir(parents=True)
        (self.stage/'map-assets/3d-assets/blobs').mkdir()
        (self.stage/'map-assets/3d-assets/york/named-house/model.glb').write_bytes(b'new York')
        resource = self.stage/'map-assets/3d-assets/blobs/source.jpg'
        resource.write_bytes(b'shared artwork')
        document = self.stage/'york.rhlos-map.json'
        document.write_text('{"placements": []}')
        (self.stage/'installation-verification.json').write_text('{}')
        self.proof = {'document':str(document), 'document_sha256':publication.sha(document),
                      'files':{'3d-assets/blobs/source.jpg':publication.sha(resource)}}
        self.addCleanup(patch.stopall)
        patch.object(publication, 'LIBRARY', self.library).start()
        patch.object(publication, 'verify', return_value=self.proof).start()
        patch.object(publication, 'scene_metadata').start()

    def test_failed_index_write_restores_assets_map_and_index(self):
        before = publication.tree_hashes(self.library)
        with patch.object(publication, 'write_asset_index', side_effect=RuntimeError('index failure')):
            with self.assertRaisesRegex(RuntimeError, 'index failure'):
                publication.install(self.stage)
        after = publication.tree_hashes(self.library)
        after.pop('.publication.lock', None)
        self.assertEqual(after, before)
        self.assertFalse((self.library/'3d-assets/.york-grouping-incoming').exists())

    def test_success_replaces_generic_assets_and_rollback_preserves_other_map_edits(self):
        with patch.object(publication, 'write_asset_index') as rebuild:
            publication.install(self.stage)
            self.assertFalse((self.library/'3d-assets/york/old-group').exists())
            self.assertEqual((self.library/'3d-assets/york/named-house/model.glb').read_bytes(), b'new York')
            other = self.library/'3d-assets/derby/model.glb'
            other.write_bytes(b'later unrelated update')
            publication.rollback(self.stage)
            self.assertEqual(other.read_bytes(), b'later unrelated update')
            self.assertEqual((self.library/'3d-assets/york/old-group/model.glb').read_bytes(), b'old York')
            self.assertEqual(rebuild.call_count, 2)
            self.assertEqual(json.loads((self.stage/'installation.json').read_text())['status'], 'ROLLED_BACK')

    def test_rollback_refuses_a_later_york_edit(self):
        with patch.object(publication, 'write_asset_index'):
            publication.install(self.stage)
            model = self.library/'3d-assets/york/named-house/model.glb'
            model.write_bytes(b'later York edit')
            with self.assertRaisesRegex(ValueError, 'York changed'):
                publication.rollback(self.stage)
            self.assertEqual(model.read_bytes(), b'later York edit')


if __name__ == '__main__':
    unittest.main()
