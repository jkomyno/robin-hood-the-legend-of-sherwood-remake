import json
from pathlib import Path
import struct
import tempfile
import unittest
from canonical_assets import AssetBundle, read_model, digest
from hybrid_library import stage_hybrid
from apply_canonical_library import graph


class HybridLibraryTests(unittest.TestCase):
    def test_cross_asset_threshold_keeps_large_shared_images_and_embeds_everything_else(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); library = root/'source'; (library/'scenes').mkdir(parents=True)
            entries, references = [], []
            for identity in ('a', 'b', 'c'):
                vertices = struct.pack('<9f', 0,0,0, 1,0,0, 0,1,0)
                pixels = (b'shared' if identity in ('a','b') else b'unique')*50000
                model = {'asset':{'version':'2.0'}, 'scene':0, 'scenes':[{'name':'default','nodes':[0]}],
                    'nodes':[{'name':'part','mesh':0}], 'meshes':[{'primitives':[{'attributes':{'POSITION':0},'material':0}]}],
                    'accessors':[{'bufferView':0,'componentType':5126,'count':3,'type':'VEC3','min':[0,0,0],'max':[1,1,0]}],
                    'bufferViews':[{'buffer':0,'byteLength':36}], 'buffers':[{'uri':'vertices','byteLength':36}],
                    'images':[{'uri':'image','mimeType':'image/png'}], 'textures':[{'source':0}],
                    'materials':[{'pbrMetallicRoughness':{'baseColorTexture':{'index':0}}}]}
                bundle = AssetBundle(library)
                external = lambda uri: vertices if uri=='vertices' else pixels
                bundle.add('default',model,b'',external)
                if identity=='c': bundle.add('applied',model,b'',external)
                ref = bundle.write(identity)
                descriptor = {'id':identity,'model':'model.gltf','model_scene':'default','resources':ref['resources']}
                path = library/'3d-assets'/identity/'asset.json'; path.write_text(json.dumps(descriptor))
                entries.append({'id':identity,'descriptor':identity+'/asset.json','model':identity+'/model.gltf'})
                references.append({**ref,'id':identity,'descriptor':'3d-assets/'+identity+'/asset.json','descriptor_sha256':digest(path.read_bytes())})
            (library/'3d-assets/index.json').write_text(json.dumps({'assets':entries}))
            (library/'scenes/map.level3d.json').write_text(json.dumps({'sceneAssets':[],'assetSources':references,'objects':[]}))
            staged = root/'first/staged'; report = stage_hybrid(library, staged)
            self.assertEqual(report['self_contained'],1)
            self.assertEqual(report['shared_payloads'],1)
            self.assertEqual(report['verified_scenes'],4)
            self.assertEqual(len(list((staged/'3d-assets/blobs').iterdir())),1)
            self.assertEqual(graph(staged,library)[1:],(3,1))
            for identity in ('a','b','c'):
                model,binary,external = read_model(staged/'3d-assets'/identity/'model.glb',staged)
                self.assertNotIn('uri',model['buffers'][0])
                self.assertEqual(struct.unpack_from('<9f',binary),struct.unpack('<9f',vertices))
                if identity=='c': self.assertNotIn('uri',model['images'][0])
                else: self.assertEqual(len(external(model['images'][0]['uri'])),300000)
            # Repacking an existing hybrid library must rediscover the same sharing.
            again = root/'second/staged'; repeated = stage_hybrid(staged,again)
            self.assertEqual(repeated,report)
            self.assertEqual(graph(again,staged)[1:],(3,1))
            all_shared = root/'third/staged'
            self.assertEqual(stage_hybrid(staged,all_shared,min_savings=1)['shared_payloads'],2)
            self.assertEqual(graph(all_shared,staged)[1:],(3,1))
            repacked = root/'fourth/staged'
            self.assertEqual(stage_hybrid(all_shared,repacked)['shared_payloads'],1)
            self.assertEqual(graph(repacked,staged)[1:],(3,1))


if __name__=='__main__': unittest.main()
