import json
from pathlib import Path
import struct
import tempfile
import unittest

from scene_manifest import export_document, scene_metadata
from canonical_assets import read_model
from stored_map import expand_document


class LocalMapExportTests(unittest.TestCase):
    def test_unifying_models_drops_lossy_derivatives_of_the_previous_source(self):
        from unify_map_assets import stage
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root/'source', root/'output'
            asset = source/'3d-assets/house'; asset.mkdir(parents=True)
            (source/'scenes').mkdir()
            model = {'asset': {'version': '2.0'}, 'scene': 0,
                     'scenes': [{'name': 'default', 'nodes': [0]}], 'nodes': [{'name': 'part'}]}
            (asset/'model.gltf').write_text(json.dumps(model))
            descriptor = {'id': 'house', 'name': 'House', 'model': 'model.gltf',
                          'source_map': 'Derby', 'parts': [], 'resources': []}
            (asset/'asset.json').write_text(json.dumps(descriptor))
            (source/'3d-assets/index.json').write_text(json.dumps({'version': 1, 'assets': [{
                'id': 'house', 'model': 'house/model.gltf', 'descriptor': 'house/asset.json',
                'lossy_model': 'house/old.lossy.glb'}]}))
            stage(source, output)
            entry = json.loads((output/'3d-assets/index.json').read_text())['assets'][0]
            self.assertNotIn('lossy_model', entry)
            self.assertTrue((output/'3d-assets'/entry['model']).is_file())

    def test_map_exports_local_catalog_instances_with_small_payloads_embedded(self):
        self.export_fixture(scenery=False)

    def test_authored_scenery_exports_without_a_game_obstacle(self):
        self.export_fixture(scenery=True)

    def export_fixture(self, scenery):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
                     'nodes': [{'name': 'map', 'children': [1, 3]}],
                     'meshes': [], 'accessors': [], 'bufferViews': [],
                     'buffers': [{'uri': 'mesh.bin', 'byteLength': 72}]}
            obstacles, vertices = [], []
            for i, x in enumerate([100, 500]):
                part = ({'name': 'foliage-oak', 'mesh': i, 'extras': {'scenery': True, 'part_name': 'Painted tree'}}
                        if scenery and i == 1 else
                        {'name': f'building-{i:03}', 'mesh': i, 'extras': {'source_obstacle': i, 'part_name': 'Wall'}})
                model['nodes'].extend([
                    {'name': f'House {i}', 'extras': {'asset_group': f'house-{i}'}, 'children': [2+i*2]}, part])
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
            stored = result['document']; library = Path(result['library'])
            self.assertEqual(stored['version'], 2)
            self.assertNotIn('objects', stored)
            document = expand_document(library, stored)
            self.assertEqual(document['sceneAssets'], [])
            self.assertEqual(len(document['assetSources']), 2)
            self.assertTrue(all(p['node'].startswith('asset:') for p in document['objects']))
            self.assertEqual(document['objects'][0]['transform'], dict(dx=0, dy=0, dz=0, rot_deg=0))
            self.assertTrue(all('parts' not in placement for placement in stored['placements']))
            refs = document['assetSources']
            self.assertEqual(refs[0]['resources'], refs[1]['resources'])
            self.assertEqual(len(list((library/'3d-assets/blobs').iterdir())), 0)
            for ref in refs:
                descriptor = json.loads((library/ref['descriptor']).read_text())
                self.assertEqual(len(descriptor['source_origin_scene']), 3)
                self.assertNotIn('source_origin_game', descriptor)
                if descriptor['parts'][0]['node'] == 'foliage-oak':
                    self.assertEqual(descriptor['parts'], [{'node': 'foliage-oak', 'name': 'Painted tree', 'scenery': True}])
                    # No footprint: anchored at the horizontal mesh bounds centre.
                    self.assertEqual(descriptor['source_origin_scene'], [501, 1, 0])
                    continue
                local, binary, _ = read_model(library/ref['model'], library)
                self.assertTrue(ref['model'].endswith('.glb'))
                self.assertEqual(ref['resources'], [])
                self.assertNotIn('uri', local['buffers'][0])
                self.assertEqual(len(binary), 36)
                self.assertLess(max(abs(p['x']) for p in descriptor['parts'][0]['obstacle_local_game']['points']), 3)
            self.assertTrue(scene_metadata(library, document)['nodes'])
            parts = [p for p in document['objects'] if p['node'].endswith(':foliage-oak')]
            self.assertEqual(len(parts), int(scenery))
            self.assertTrue(all('obstacle' not in p for p in parts))


if __name__ == '__main__':
    unittest.main()
