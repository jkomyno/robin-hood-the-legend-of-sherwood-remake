import json
from pathlib import Path
import struct
import tempfile
import unittest

from scene_manifest import export_document, scene_metadata
from canonical_assets import read_model


class LocalMapExportTests(unittest.TestCase):
    def test_map_exports_local_catalog_instances_with_small_payloads_embedded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
                     'nodes': [{'name': 'map', 'children': [1, 3]}],
                     'meshes': [], 'accessors': [], 'bufferViews': [],
                     'buffers': [{'uri': 'mesh.bin', 'byteLength': 72}]}
            obstacles, vertices = [], []
            for i, x in enumerate([100, 500]):
                model['nodes'].extend([
                    {'name': f'House {i}', 'extras': {'asset_group': f'house-{i}'}, 'children': [2+i*2]},
                    {'name': f'building-{i:03}', 'mesh': i, 'extras': {'source_obstacle': i, 'part_name': 'Wall'}}])
                model['meshes'].append({'primitives': [{'attributes': {'POSITION': i}}]})
                model['accessors'].append({'bufferView': i, 'componentType': 5126, 'count': 3,
                                          'type': 'VEC3', 'min': [x, 0, 0], 'max': [x+2, 2, 0]})
                model['bufferViews'].append({'buffer': 0, 'byteOffset': i*36, 'byteLength': 36})
                vertices.extend([x, 0, 0, x+2, 0, 0, x, 2, 0])
                obstacles.append({'points': [{'x': px, 'y': y, 'z_bottom': 0, 'z_top': 2}
                                              for px, y in [(x, 0), (x+2, 0), (x, 2)]],
                                  'projection_area': None, 'opaque': True, 'solid': True, 'mouse': True,
                                  'show_shadow_polygon': True, 'default_material': 0, 'material_indices': []})
            (root/'mesh.bin').write_bytes(struct.pack('<18f', *vertices))
            (root/'source.gltf').write_text(json.dumps(model))
            result = export_document(root/'source.gltf', root/'fixture.rhlos-map.json', 'Fixture',
                                     {'sight_obstacles': obstacles}, size=[1024, 512])
            document = result['document']; library = Path(result['library'])
            self.assertEqual(document['sceneAssets'], [])
            self.assertEqual(len(document['assetSources']), 2)
            self.assertTrue(all(p['node'].startswith('asset:') for p in document['objects']))
            self.assertEqual(document['objects'][0]['transform'], dict(dx=0, dy=0, dz=0, rot_deg=0))
            refs = document['assetSources']
            self.assertEqual(refs[0]['resources'], refs[1]['resources'])
            self.assertEqual(len(list((library/'3d-assets/blobs').iterdir())), 0)
            for ref in refs:
                descriptor = json.loads((library/ref['descriptor']).read_text())
                self.assertNotIn('source_origin_scene', descriptor)
                self.assertNotIn('source_origin_game', descriptor)
                local, binary, _ = read_model(library/ref['model'], library)
                self.assertTrue(ref['model'].endswith('.glb'))
                self.assertEqual(ref['resources'], [])
                self.assertNotIn('uri', local['buffers'][0])
                self.assertEqual(len(binary), 36)
                self.assertLess(max(abs(p['x']) for p in descriptor['parts'][0]['obstacle_local_game']['points']), 3)
            self.assertTrue(scene_metadata(library, document)['nodes'])


if __name__ == '__main__':
    unittest.main()
