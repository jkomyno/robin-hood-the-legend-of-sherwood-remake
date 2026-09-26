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
        descriptor = {'id':'ground', 'name':'Ground', 'source_map':'Fixture', 'model':'model.gltf', 'model_scene':'default', 'resources':[]}
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

    def test_publication_discovers_staged_assets_without_reading_the_cached_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            live, staged, plan, _ = self.fixture(Path(temporary))
            (staged/'3d-assets/index.json').write_text('obsolete cache')
            publish(plan, True)
            index = json.loads((live/'3d-assets/index.json').read_text())
            self.assertEqual([entry['id'] for entry in index['assets']], ['ground'])
            self.assertEqual(index['assets'][0]['name'], 'Ground')

    def test_lossy_models_are_carried_only_while_bound_to_the_model(self):
        from apply_canonical_library import graph
        with tempfile.TemporaryDirectory() as temporary:
            live, staged, plan, sources = self.fixture(Path(temporary))
            model = digest((staged/'3d-assets/ground/model.gltf').read_bytes())
            (staged/'3d-assets/ground/lossy.glb').write_bytes(b'lossy')
            receipt = staged/'3d-assets/ground/lossy.glb.receipt.json'
            receipt.write_text(json.dumps({'source':model, 'output':digest(b'lossy')}))
            index = json.loads((staged/'3d-assets/index.json').read_text())
            index['assets'][0]['lossy_model'] = 'ground/lossy.glb'
            (staged/'3d-assets/index.json').write_text(json.dumps(index))
            files = graph(staged, live)[0]
            self.assertIn('3d-assets/ground/lossy.glb', files)
            self.assertIn('3d-assets/ground/lossy.glb.receipt.json', files)
            receipt.write_text(json.dumps({'source':'a'*64, 'output':digest(b'lossy')}))
            with self.assertRaisesRegex(ValueError, 'does not bind'): graph(staged, live)

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
