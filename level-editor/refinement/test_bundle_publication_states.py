import json
from pathlib import Path
import tempfile
import struct
import unittest
from unittest.mock import patch
from bundle_publication_states import sha, verify_bundled_reference, bundle_exported_variants
from promote_staged_publication import asset_file_pairs


class BundlePublicationTests(unittest.TestCase):
    def test_canonical_endpoint_checks_decoded_resources_and_rejects_tampering(self):
        from canonical_assets import AssetBundle, read_model
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = struct.pack('<9f', 0, 0, 0, 1, 0, 0, 0, 1, 0)
            source = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
                'nodes': [{'name': 'endpoint', 'mesh': 0}],
                'meshes': [{'primitives': [{'attributes': {'POSITION': 0}}]}],
                'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3',
                               'min': [0, 0, 0], 'max': [1, 1, 0]}],
                'bufferViews': [{'buffer': 0, 'byteLength': len(binary)}],
                'buffers': [{'uri': 'mesh.bin', 'byteLength': len(binary)}]}
            (root/'mesh.bin').write_bytes(binary)
            reference = root/'reference.gltf'; reference.write_text(json.dumps(source))
            model, data, external = read_model(reference, root)
            bundle = AssetBundle(root/'library'); bundle.add('applied', model, data, external)
            ref = bundle.write('house')
            report = {'model': str(root/'library'/ref['model']), 'model_sha256': ref['model_sha256'],
                      'model_scene': 'applied'}
            self.assertEqual(verify_bundled_reference(report, reference)['scene'], 'applied')
            (root/'library'/ref['resources'][0]['path']).write_bytes(struct.pack('<9f', 0, 0, 0, 2, 0, 0, 0, 1, 0))
            with self.assertRaisesRegex(ValueError, 'Canonical endpoint differs'):
                verify_bundled_reference(report, reference)

    def test_shared_model_promotes_once_with_bound_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage, library = root / 'stage', root / 'library'
            asset = stage / 'house'
            asset.mkdir(parents=True)
            model, descriptor_path = asset / 'model.glb', asset / 'asset.json'
            model.write_bytes(b'all-scenes')
            descriptor_path.write_text(json.dumps({'id': 'house', 'model': 'model.glb', 'model_scene': 'default',
                'standalone_variants': {state: {'name': state, 'model': 'model.glb', 'model_scene': state}
                                        for state in ('initial', 'applied')}}))
            receipt = asset / 'bundle.receipt.json'
            receipt.write_text(json.dumps({'asset_id': 'house', 'output': {'sha256': sha(model)},
                                            'output_descriptor_sha256': sha(descriptor_path)}))
            entry = {'id': 'house', 'descriptor': 'house/asset.json', 'model': 'house/model.glb'}
            pairs = asset_file_pairs(stage, library, entry)
            self.assertEqual({source.name for source, _ in pairs}, {'model.glb', 'asset.json', 'bundle.receipt.json'})
            self.assertEqual(len(pairs), 3)
            model.write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                asset_file_pairs(stage, library, entry)

    def test_independent_verified_source_and_scene_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference, model, receipt_path = [root / name for name in ('reference.glb', 'model.glb', 'bundle.receipt.json')]
            reference.write_bytes(b'reviewed')
            model.write_bytes(b'combined')
            receipt = {'asset_id': 'house', 'output': {'sha256': sha(model)}, 'states': [
                {'scene': 'applied', 'source_sha256': sha(reference), 'semantic_sha256': 'scene-content'}]}
            receipt_path.write_text(json.dumps(receipt))
            report = {'asset_id': 'house', 'model': str(model), 'model_scene': 'applied',
                      'model_sha256': sha(model), 'original_model_sha256': sha(reference),
                      'bundle_receipt': str(receipt_path), 'bundle_receipt_sha256': sha(receipt_path)}
            result = {'semantic_sha256': 'scene-content', 'scene': 'applied',
                      'reference_sha256': sha(reference), 'bundle_sha256': sha(model)}
            with patch('bundle_publication_states.subprocess.check_output', return_value=json.dumps(result)) as verify:
                verify_bundled_reference(report, reference)
                self.assertIn('--reference', verify.call_args.args[0])
            with patch('bundle_publication_states.subprocess.check_output', return_value=json.dumps({**result, 'semantic_sha256': 'wrong'})):
                with self.assertRaises(ValueError):
                    verify_bundled_reference(report, reference)
            reference.write_bytes(b'wrong-state')
            with self.assertRaises(ValueError):
                verify_bundled_reference(report, reference)

    def test_pack_preserves_original_hash_and_removes_obsolete_variant(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset = root / 'assets/house'
            asset.mkdir(parents=True)
            (asset / 'model.glb').write_bytes(b'initial')
            (asset / 'model-applied.glb').write_bytes(b'applied')
            descriptor = {'id': 'house', 'model': 'model.glb', 'state_variants': {
                'initial': {'model': 'model.glb'}, 'applied': {'model': 'model-applied.glb'}}}
            (asset / 'asset.json').write_text(json.dumps(descriptor))
            report = {'asset_id': 'house', 'state': 'applied', 'model_sha256': sha(asset / 'model-applied.glb')}
            old_hash = report['model_sha256']

            def pack(args, **kwargs):
                staged = Path(args[-1])
                staged.mkdir(parents=True)
                (staged / 'model.glb').write_bytes(b'both-states')
                descriptor['model_scene'] = 'initial'
                descriptor['state_variants'] = {state: {'model': 'model.glb', 'model_scene': state} for state in ('initial', 'applied')}
                (staged / 'asset.json').write_text(json.dumps(descriptor))
                (staged / 'bundle.receipt.json').write_text(json.dumps({'asset_id': 'house',
                    'output': {'sha256': sha(staged / 'model.glb')}, 'states': [
                        {'scene': 'applied', 'source_sha256': old_hash}]}))
            with patch('bundle_publication_states.subprocess.run', side_effect=pack):
                result = bundle_exported_variants(root, [report])[0]
            self.assertEqual(result['original_model_sha256'], old_hash)
            self.assertEqual(result['model_scene'], 'applied')
            self.assertEqual(result['model_sha256'], sha(asset / 'model.glb'))
            self.assertFalse((asset / 'model-applied.glb').exists())


if __name__ == '__main__':
    unittest.main()
