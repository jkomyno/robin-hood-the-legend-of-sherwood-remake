import hashlib,json,tempfile,unittest
from pathlib import Path
from reviewed_texture_scope import displayed_objects, layer_objects

class Obj(dict):
    def __init__(self,name,**kw):super().__init__(**kw);self.name=name

class StateVisibilityTests(unittest.TestCase):
    def test_exact_approved_display_filters_only_removed_cover(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'views.json';path.write_text(json.dumps({'asset_id':'x','render_object_names':['wall','floor']}))
            manifest={'asset_id':'x','render_object_names':['wall','floor'],'reviewed_packet':tmp,'reviewed_manifest_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            wall,floor,cover=[Obj(n) for n in ['wall','floor','cover']]
            self.assertEqual(displayed_objects(manifest,[wall,floor,cover]),[wall,floor])
            manifest['render_object_names']=['floor']
            with self.assertRaisesRegex(ValueError,'approved state'):displayed_objects(manifest,[wall,floor,cover])
            manifest['render_object_names']=['wall','floor']
            with self.assertRaisesRegex(ValueError,'absent'):displayed_objects(manifest,[floor,cover])
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError,'frame changed'):displayed_objects(manifest,[wall,floor,cover])
    def test_defaults_keep_all_known_occluders(self):
        objects=[Obj('wall'),Obj('cover')]
        self.assertIs(displayed_objects({},objects),objects)
    def test_shared_node_component_layer_scope(self):
        wall=Obj('outer',source_node='building-137',projection_component='lower-exterior')
        room=Obj('coping',source_node='building-137',projection_component='chamber-coping')
        layer={'receiver_nodes':['building-137'],'receiver_components':[{'source_node':'building-137','projection_components':['chamber-coping']}]}
        self.assertEqual(layer_objects(layer,[wall,room]),[room]);self.assertEqual(layer_objects(layer,[wall]),[])
if __name__=='__main__':unittest.main()
