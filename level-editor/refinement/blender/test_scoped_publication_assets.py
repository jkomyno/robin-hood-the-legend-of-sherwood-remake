"""Run with unittest; scoped palettes must not narrow whole-map coverage."""
import json,struct,sys,tempfile,types,unittest
from pathlib import Path
from unittest import mock
from verify_publication_assets import verify

class ScopedPublicationTests(unittest.TestCase):
    def test_subset_and_ground_preserve_full_map_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'assets').mkdir()
            def write(path,value):path.write_text(json.dumps(value))
            def glb(path,names):
                data=json.dumps({'nodes':[{'name':n} for n in names]}).encode();data+=b' '*(-len(data)%4)
                path.write_bytes(struct.pack('<III',0x46546c67,2,20+len(data))+struct.pack('<II',len(data),0x4e4f534a)+data)
            catalog={'map':'Leicester','groups':[{'id':'chosen','parts':[{'obstacle':1}]},{'id':'retained','parts':[{'obstacle':2}]}]}
            write(root/'catalog.json',catalog)
            write(root/'plan.json',{'export_asset_ids':['chosen','terrain'],'imports':[{'asset_id':'terrain','source_nodes':['ground']}]})
            # The full map is a JSON/assets document; expanding it is scene_manifest's job, so a
            # stand-in returns the document's node names as the expanded scene.
            expanded=types.SimpleNamespace(scene_metadata=lambda library,document:{'nodes':[{'name':n} for n in document['nodes']]})
            self.enterContext(mock.patch.dict(sys.modules,{'scene_manifest':expanded}))
            write(root/'leicester.rhlos-map.json',{'nodes':['building-001','building-002','ground']})
            write(root/'stage.json',{'plan':str(root/'plan.json'),'map':{'file':str(root/'leicester.rhlos-map.json'),'library':str(root)},'generated_materials':{}})
            assets=[]
            for asset,node in [('chosen','building-001'),('terrain','ground')]:
                write(root/'assets'/(asset+'.json'),{'components':[{'source_node':node}],**({'parts':[],'editor_usage':'map-background'} if node=='ground' else {})});glb(root/'assets'/(asset+'.glb'),[node])
                assets.append({'id':asset,'descriptor':asset+'.json','model':asset+'.glb',**({'editor_usage':'map-background'} if node=='ground' else {})})
            write(root/'assets/index.json',{'assets':assets})
            result=verify(root,root/'catalog.json');self.assertEqual((result['groups'],result['parts'],result['full_map_parts']),(2,1,2))
            write(root/'leicester.rhlos-map.json',{'nodes':['building-001','ground']})
            with self.assertRaisesRegex(ValueError,'Full map canonical coverage'):verify(root,root/'catalog.json')
            write(root/'leicester.rhlos-map.json',{'nodes':['building-001','building-002','ground']})
            write(root/'assets/index.json',{'assets':assets[:1]})
            with self.assertRaisesRegex(ValueError,'Standalone group catalog'):verify(root,root/'catalog.json')

if __name__=='__main__':unittest.main()
