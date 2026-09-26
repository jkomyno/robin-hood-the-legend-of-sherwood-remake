import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from split_scene_assets import split, canonical, read_glb


class ExactImportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'handoff.glb'
        self.output = self.root / 'library'
        self.geometry = struct.pack('<9f', 0, 0, 0, 1, 0, 0, 0, 1, 0)
        self.texture = b'unchanged encoded image bytes'
        self.binary = self.geometry + self.texture
        self.model = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
            'extensionsUsed': ['KHR_materials_unlit'],
            'nodes': [{'name': 'map', 'children': [1, 3], 'rotation': [-.707, 0, 0, .707],
                       'extras': {'reveal': {'patches': [{'id': 'door', 'name': 'Open door'}]}}},
                      {'name': 'House', 'children': [2], 'extras': {'asset_group': 'house'}},
                      {'name': 'building-007', 'mesh': 0, 'translation': [1, 2, 3], 'extras': {'source_obstacle': 7}},
                      {'name': 'Other house', 'children': [4], 'extras': {'asset_group': 'other'}},
                      {'name': 'building-009', 'mesh': 0, 'extras': {'source_obstacle': 9}}],
            'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'material': 0}]}],
            'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3'}],
            'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': len(self.geometry)},
                            {'buffer': 0, 'byteOffset': len(self.geometry), 'byteLength': len(self.texture)}],
            'buffers': [{'byteLength': len(self.binary)}],
            'materials': [{'extensions': {'KHR_materials_unlit': {}}, 'pbrMetallicRoughness': {'baseColorTexture': {'index': 0}}}],
            'textures': [{'source': 0}], 'images': [{'bufferView': 1, 'mimeType': 'image/png'}]}

    def write(self):
        data = json.dumps(self.model).encode(); data += b' ' * (-len(data) % 4)
        binary = self.binary + b'\0' * (-len(self.binary) % 4)
        self.source.write_bytes(struct.pack('<III', 0x46546c67, 2, 28 + len(data) + len(binary)) +
            struct.pack('<II', len(data), 0x4e4f534a) + data + struct.pack('<II', len(binary), 0x004e4942) + binary)

    def test_extracts_exact_hierarchies_and_shares_encoded_payloads(self):
        self.write()
        report = split(self.source, self.output)
        self.assertEqual(report['verified_assets'], 3)
        self.assertEqual([item['role'] for item in report['sceneAssets']], ['metadata', 'objects', 'objects'])
        self.assertEqual(len(list((self.output / '3d-assets/blobs').glob('*.png'))), 1)
        self.assertEqual(len(list((self.output / '3d-assets/blobs').glob('*.bin'))), 1)
        source, binary, _ = read_glb(self.source)
        reference = report['sceneAssets'][1]
        asset = json.loads((self.output / reference['model']).read_text())
        after = lambda: canonical(asset, b'', asset['scenes'][0]['nodes'], lambda uri: (self.output / uri).read_bytes())
        self.assertEqual(canonical(source, binary, [1]), after())
        asset['nodes'][0]['extras']['asset_group'] = 'changed'
        self.assertNotEqual(canonical(source, binary, [1]), after())
        self.assertEqual(report, split(self.source, self.output))

    def test_corrupt_existing_asset_cannot_be_silently_replaced(self):
        self.write(); report = split(self.source, self.output)
        model = self.output / report['sceneAssets'][0]['model']
        model.write_text('corrupted')
        with self.assertRaisesRegex(ValueError, 'Content-addressed asset differs'):
            split(self.source, self.output)
        self.assertEqual(model.read_text(), 'corrupted')

    def test_unknown_extensions_and_animation_fail_closed(self):
        for field, value in [('extensionsUsed', ['KHR_draco_mesh_compression']), ('animations', [{'name': 'moving'}])]:
            with self.subTest(field=field):
                previous = copy.deepcopy(self.model)
                self.model[field] = value; self.write()
                with self.assertRaisesRegex(ValueError, 'Unsupported|Animated'):
                    split(self.source, self.output)
                self.model = previous


if __name__ == '__main__':
    unittest.main()
