import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from apply_canonical_library import publish
from canonical_assets import digest


class CanonicalPublicationTests(unittest.TestCase):
    def fixture(self, root):
        live, staged = root/'live', root/'staged'
        for folder in (live/'3d-assets', live/'scenes', staged/'3d-assets/ground', staged/'scenes'):
            folder.mkdir(parents=True)
        index = {'assets':[{'id':'ground', 'descriptor':'ground/asset.json', 'model':'ground/model.gltf'}]}
        descriptor = {'id':'ground', 'model':'model.gltf', 'model_scene':'default', 'resources':[]}
        model = {'asset':{'version':'2.0'}, 'scene':0, 'scenes':[{'name':'default', 'nodes':[]}], 'nodes':[]}
        for name, value in [('3d-assets/index.json', index), ('3d-assets/ground/asset.json', descriptor),
                            ('3d-assets/ground/model.gltf', model)]:
            (staged/name).write_text(json.dumps(value))
        reference = {'id':'ground', 'role':'ground', 'model':'3d-assets/ground/model.gltf',
            'model_sha256':digest((staged/'3d-assets/ground/model.gltf').read_bytes()),
            'descriptor':'3d-assets/ground/asset.json', 'descriptor_sha256':digest((staged/'3d-assets/ground/asset.json').read_bytes()), 'resources':[]}
        (staged/'scenes/fixture.rhlos-map.json').write_text(json.dumps({'objects':[], 'sceneAssets':[reference]}))
        (live/'3d-assets/index.json').write_text('{"assets":[]}')
        (live/'3d-assets/obsolete.glb').write_bytes(b'old geometry')
        (live/'scenes/fixture.rhlos-map.json').write_text('{"old":true}')
        sources = {str(path.relative_to(live)):digest(path.read_bytes()) for path in live.rglob('*') if path.is_file()}
        plan = root/'plan.json'; plan.write_text(json.dumps({'library':str(live), 'output':str(staged), 'sources':sources}))
        return live, staged, plan, sources

    def test_publication_archives_old_files_and_validates_source_guards(self):
        with tempfile.TemporaryDirectory() as temporary:
            live, staged, plan, sources = self.fixture(Path(temporary))
            self.assertFalse(publish(plan)['apply'])
            (live/'3d-assets/obsolete.glb').write_bytes(b'changed concurrently')
            with self.assertRaisesRegex(ValueError, 'Source changed'): publish(plan, True)
            (live/'3d-assets/obsolete.glb').write_bytes(b'old geometry')
            result = publish(plan, True)
            backup = Path(result['backup'])
            for relative, expected in sources.items(): self.assertEqual(digest((backup/relative).read_bytes()), expected)
            self.assertFalse((live/'3d-assets/obsolete.glb').exists())
            self.assertEqual((live/'scenes/fixture.rhlos-map.json').read_bytes(), (staged/'scenes/fixture.rhlos-map.json').read_bytes())

    def test_failed_install_restores_every_previous_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            live, staged, plan, sources = self.fixture(Path(temporary))
            def partial_copy(source, target):
                target.write_bytes(b'partial')
                raise OSError('disk full')
            with patch('apply_canonical_library.shutil.copy2', side_effect=partial_copy):
                with self.assertRaisesRegex(OSError, 'disk full'): publish(plan, True)
            for relative, expected in sources.items(): self.assertEqual(digest((live/relative).read_bytes()), expected)
            self.assertFalse((live/'3d-assets/ground/model.gltf').exists())


if __name__ == '__main__': unittest.main()
