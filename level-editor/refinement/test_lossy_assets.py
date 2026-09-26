"""Lossy derivative bookkeeping (receipts, index fields, library writes) without Blender."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'blender'))
import lossy_assets  # noqa: E402


def sha(data):
    return hashlib.sha256(data).hexdigest()


def glb(material):
    """One textured triangle; `material` is the glTF material JSON."""
    positions = struct.pack('<9f', 0, 0, 0, 1, 0, 0, 0, 1, 0)
    uvs = struct.pack('<6f', 0, 0, 1, 0, 0, 1)
    indices = struct.pack('<3H', 0, 1, 2) + b'\0\0'
    image = b'\x89PNG fake'
    body = positions + uvs + indices + image
    body += b'\0' * (-len(body) % 4)
    doc = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'name': 'default', 'nodes': [0]}],
           'nodes': [{'name': 'part', 'mesh': 0}],
           'meshes': [{'primitives': [{'attributes': {'POSITION': 0, 'TEXCOORD_0': 1}, 'indices': 2, 'material': 0}]}],
           'materials': [material], 'textures': [{'source': 0}], 'images': [{'bufferView': 3, 'mimeType': 'image/png'}],
           'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3', 'min': [0, 0, 0], 'max': [1, 1, 0]},
                         {'bufferView': 1, 'componentType': 5126, 'count': 3, 'type': 'VEC2'},
                         {'bufferView': 2, 'componentType': 5123, 'count': 3, 'type': 'SCALAR'}],
           'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': 36}, {'buffer': 0, 'byteOffset': 36, 'byteLength': 24},
                           {'buffer': 0, 'byteOffset': 60, 'byteLength': 6}, {'buffer': 0, 'byteOffset': 68, 'byteLength': len(image)}],
           'buffers': [{'byteLength': len(body)}]}
    chunk = json.dumps(doc).encode()
    chunk += b' ' * (-len(chunk) % 4)
    return (struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(chunk) + 8 + len(body)) + struct.pack('<II', len(chunk), 0x4E4F534A)
            + chunk + struct.pack('<II', len(body), 0x004E4942) + body)


UNLIT = {'pbrMetallicRoughness': {'baseColorTexture': {'index': 0}}, 'extensions': {'KHR_materials_unlit': {}}}


class LossyAssetsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'work')
        self.root = Path(self.temporary.name) / '3d-assets'
        (self.root / 'derby/house').mkdir(parents=True)
        (self.root / 'derby/house/model.glb').write_bytes(glb(UNLIT))
        self.index = {'version': 1, 'assets': [{'id': 'house', 'model': 'derby/house/model.glb',
                                                 'descriptor': 'derby/house/asset.json', 'label': 'kept'}]}
        (self.root / 'index.json').write_text(json.dumps(self.index))
        self.args = lossy_assets.default_settings()

    def tearDown(self):
        self.temporary.cleanup()

    def fake_derive(self, asset_id, model_path, lossy_path, args, work):
        """Stands in for the Blender derivation: writes a lossy model and its receipt."""
        lossy_path.write_bytes(b'lossy:' + model_path.read_bytes()[:8])
        receipt = {'source': sha(model_path.read_bytes()), 'output': sha(lossy_path.read_bytes()),
                   'settings': lossy_assets.settings(args)}
        Path(str(lossy_path) + '.receipt.json').write_text(json.dumps(receipt))
        self.derived.append(asset_id)
        return {'asset_id': asset_id}

    def refresh(self, **options):
        self.derived = []
        with patch.object(lossy_assets, 'derive', self.fake_derive), \
                patch.object(lossy_assets, 'summary_row', lambda report: report):
            return lossy_assets.refresh_derivatives(self.root, Path(self.temporary.name) / 'work', previews=False,
                                                    log=lambda message: None, **options)

    def test_static_check_accepts_display_textures_and_refuses_others(self):
        model = 'derby/house/model.glb'
        self.assertEqual(lossy_assets.static_check(self.root, model), [])
        foliage = dict(UNLIT, emissiveTexture={'index': 0}, emissiveFactor=[1, 1, 1], alphaMode='MASK')
        background = {'pbrMetallicRoughness': {'baseColorFactor': [0, 0, 0, 1]}, 'emissiveTexture': {'index': 0},
                      'emissiveFactor': [1, 1, 1]}
        for material in (foliage, background):
            (self.root / model).write_bytes(glb(material))
            self.assertEqual(lossy_assets.static_check(self.root, model), [])
        for material in (dict(UNLIT, normalTexture={'index': 0}),
                         {'pbrMetallicRoughness': {'baseColorFactor': [0.5, 0, 0, 1]}, 'emissiveTexture': {'index': 0},
                          'emissiveFactor': [1, 1, 1]}):
            (self.root / model).write_bytes(glb(material))
            self.assertTrue(lossy_assets.static_check(self.root, model))

    def test_refresh_derives_once_sets_field_and_rederives_changed_models(self):
        report = self.refresh()
        index = json.loads((self.root / 'index.json').read_text())
        self.assertEqual(index['assets'][0]['lossy_model'], 'derby/house/lossy.glb')
        self.assertEqual(index['assets'][0]['label'], 'kept')
        self.assertEqual((len(report['derived']), self.derived), (1, ['house']))
        self.assertEqual(lossy_assets.verify_derivatives(self.root), [])
        self.assertEqual(self.refresh()['current'], ['house'])
        self.assertEqual(self.derived, [])
        # Republished model bytes invalidate the receipt until the next refresh.
        (self.root / 'derby/house/model.glb').write_bytes(glb(dict(UNLIT, doubleSided=True)))
        self.assertIn('house: lossy receipt does not bind the current model', lossy_assets.verify_derivatives(self.root))
        self.refresh()
        self.assertEqual(self.derived, ['house'])
        self.assertEqual(lossy_assets.verify_derivatives(self.root), [])

    def test_disabled_refresh_removes_the_field_and_refusals_keep_none(self):
        self.refresh()
        report = self.refresh(lossy=False)
        self.assertEqual(report['removed'], ['house'])
        self.assertNotIn('lossy_model', json.loads((self.root / 'index.json').read_text())['assets'][0])
        (self.root / 'derby/house/model.glb').write_bytes(glb(dict(UNLIT, occlusionTexture={'index': 0})))
        report = self.refresh()
        self.assertIn('house', report['refused'])
        self.assertNotIn('lossy_model', json.loads((self.root / 'index.json').read_text())['assets'][0])

    def test_changed_settings_or_tampered_output_are_not_current(self):
        self.refresh()
        lossy = 'derby/house/lossy.glb'
        self.assertTrue(lossy_assets.receipt_current(self.root, 'derby/house/model.glb', lossy, self.args))
        self.assertFalse(lossy_assets.receipt_current(self.root, 'derby/house/model.glb', lossy,
                                                      lossy_assets.default_settings(quality=60)))
        (self.root / lossy).write_bytes(b'tampered')
        self.assertFalse(lossy_assets.receipt_current(self.root, 'derby/house/model.glb', lossy, self.args))
        self.assertIn('house: lossy model bytes differ from its receipt', lossy_assets.verify_derivatives(self.root))

    def test_preview_receipts_must_bind_the_lossy_model(self):
        self.refresh()
        preview = self.root / 'derby/house/preview.glb'
        preview.write_bytes(b'preview')
        lossy_sha = sha((self.root / 'derby/house/lossy.glb').read_bytes())
        Path(str(preview) + '.receipt.json').write_text(json.dumps(
            {'source': lossy_sha, 'source_model': 'derby/house/lossy.glb', 'output': sha(b'preview')}))
        index = json.loads((self.root / 'index.json').read_text())
        index['assets'][0]['preview_model'] = 'derby/house/preview.glb'
        (self.root / 'index.json').write_text(json.dumps(index))
        self.assertEqual(lossy_assets.verify_derivatives(self.root), [])
        Path(str(preview) + '.receipt.json').write_text(json.dumps(
            {'source': 'f' * 64, 'source_model': 'derby/house/lossy.glb', 'output': sha(b'preview')}))
        self.assertTrue(lossy_assets.verify_derivatives(self.root))

    def test_library_publish_and_rollback_restore_the_previous_state(self):
        run = Path(self.temporary.name) / 'run'
        stage = run / 'stage/derby/house/lossy.glb'
        stage.parent.mkdir(parents=True)
        self.fake_derive_into(stage)
        before = (self.root / 'index.json').read_bytes()
        (run / 'backup').mkdir(parents=True)
        (run / 'backup/index.json').write_bytes(before)
        record = {'root': str(self.root), 'files': [], 'index': [], 'reports': {}, 'failures': {}}
        model_sha = sha((self.root / 'derby/house/model.glb').read_bytes())
        lossy_assets.publish_one(self.root, run, 'house', 'derby/house/model.glb', 'derby/house/lossy.glb',
                                 stage, model_sha, record)
        self.assertEqual(json.loads((self.root / 'index.json').read_text())['assets'][0]['lossy_model'],
                         'derby/house/lossy.glb')
        self.assertEqual(lossy_assets.verify_derivatives(self.root), [])
        with self.assertRaisesRegex(ValueError, 'Model changed'):
            lossy_assets.publish_one(self.root, run, 'house', 'derby/house/model.glb', 'derby/house/lossy.glb',
                                     stage, 'a' * 64, dict(record, files=[], index=[]))
        lossy_assets.main_rollback(type('Args', (), {'run': run})())
        self.assertNotIn('lossy_model', json.loads((self.root / 'index.json').read_text())['assets'][0])
        self.assertFalse((self.root / 'derby/house/lossy.glb').exists())

    def fake_derive_into(self, lossy_path):
        self.derived = []
        self.fake_derive('house', self.root / 'derby/house/model.glb', lossy_path, self.args, None)


if __name__ == '__main__':
    unittest.main()
