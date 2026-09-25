import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from prepare_publication_browser import prepare


class FirstPublicationTest(unittest.TestCase):
    def test_explicit_document_is_staged_without_creating_live_document(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary:
            try:
                os.chdir(temporary)
                stage = Path('stage'); stage.mkdir(); (stage/'assets').mkdir()
                library = Path('level-editor/library')
                (library/'scenes').mkdir(parents=True); (library/'3d-assets').mkdir()
                for path in [stage/'assets/index.json', library/'3d-assets/index.json']:
                    path.write_text('{"assets":[]}')
                (library/'scenes/york-volumes.scene.json').write_text('{}')
                model = {'nodes': [{'name':'map','children':[1]}, {'name':'House','extras':{'asset_group':'york-house'},'children':[2]}, {'name':'building-000'}]}
                encoded = json.dumps(model).encode(); encoded += b' ' * (-len(encoded) % 4)
                (stage/'york.scene.glb').write_bytes(struct.pack('<III',0x46546c67,2,20+len(encoded))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded)
                document = {'size':[100,200], 'provenance':{}, 'groups':[{'id':'york-house'}], 'objects':[{'node':'building-000','group':'york-house'}]}
                Path('document.json').write_text(json.dumps(document)); Path('scope.json').write_text('{"asset_ids":[],"already_published":[]}')
                result = prepare(stage,'scope.json','audit/config.json',map_name='york',document_path='document.json')
                self.assertEqual(result['groups'],1)
                self.assertFalse((library/'scenes/york.level3d.json').exists())
                self.assertTrue((stage/'york.level3d.json').exists())
                bad = dict(document,objects=[{'node':'building-000','group':'wrong'}]); Path('bad.json').write_text(json.dumps(bad))
                with self.assertRaisesRegex(ValueError,'ownership differs'):
                    prepare(stage,'scope.json','audit/other.json',map_name='york',document_path='bad.json')
                with self.assertRaisesRegex(ValueError,'cannot replace live'):
                    prepare(stage,'scope.json','audit/live.json',map_name='york',document_path='document.json',live=True)
            finally:
                os.chdir(previous)

if __name__ == '__main__':
    unittest.main()
