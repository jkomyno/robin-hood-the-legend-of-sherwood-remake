import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from review_evidence import sha
from uv_atlas_publication import validate

class UvAtlasPublicationTests(unittest.TestCase):
    def fixture(self, directory):
        exp=Path(directory); bake=exp/'bake';bake.mkdir()
        for file in ('model.blend','preparation.json'):(exp/file).write_bytes(file.encode())
        (bake/'worker.blend').write_bytes(b'baked')
        Image.new('RGBA',(2,1),(100,80,60,255)).save(exp/'input.png')
        out=Image.new('RGBA',(2,1),(100,80,60,255));out.putpixel((1,0),(120,100,80,255));out.save(bake/'atlas.png')
        mask=Image.new('RGBA',(2,1),(255,255,255,255));mask.putpixel((1,0),(255,255,255,0));mask.save(exp/'mask.png')
        before=dict(asset_id='ground',receiver='Terrain',source_node='ground',model_sha256=sha(exp/'model.blend'),physical_opacity='OPAQUE',direct_image_color=True,geometry={'uv':[[0,0],[1,1]]},geometry_uv_matrix_sha256='bound',atlas_dimensions=[2,1],uv_layer='UVMap',material_slot=0,alpha_mode='CHANNEL_PACKED',interpolation='Closest')
        after=dict(before,model_sha256=sha(bake/'worker.blend'),atlas_sha256=sha(bake/'atlas.png'))
        for path,data in [(exp/'uv-evidence.json',before),(bake/'uv-evidence.json',after)]:path.write_text(json.dumps(data))
        frames=dict(uv_evidence_sha256=sha(exp/'uv-evidence.json'));validation=dict(baked_uv_evidence_sha256=sha(bake/'uv-evidence.json'),preparation_sha256=sha(exp/'preparation.json'),baked_model_sha256=sha(bake/'worker.blend'),generated_sha256=sha(bake/'atlas.png'));approval=dict(saved_model_sha256=sha(exp/'model.blend'))
        return exp,bake,frames,validation,approval
    def test_nonplanar_uv_contract_and_protected_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory);result=validate(*args,args[1]/'worker.blend');self.assertEqual(len(result),5)
    def test_changed_uv_and_source_are_rejected(self):
        for change in ('uv','source'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as directory:
                exp,bake,frames,validation,approval=self.fixture(directory)
                if change=='uv':
                    p=bake/'uv-evidence.json';d=json.loads(p.read_text());d['geometry']['uv'][0]=[.1,.2];p.write_text(json.dumps(d));validation['baked_uv_evidence_sha256']=sha(p)
                else:
                    im=Image.open(bake/'atlas.png');im.putpixel((0,0),(0,0,0,255));im.save(bake/'atlas.png');p=bake/'uv-evidence.json';d=json.loads(p.read_text());d['atlas_sha256']=sha(bake/'atlas.png');p.write_text(json.dumps(d));validation.update(baked_uv_evidence_sha256=sha(p),generated_sha256=sha(bake/'atlas.png'))
                with self.assertRaises(ValueError):validate(exp,bake,frames,validation,approval,bake/'worker.blend')
if __name__=='__main__':unittest.main()
