import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from reviewed_input_contract import sha, validate


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.p = Path(self.temp.name)
        self.old = self.p/'original'
        (self.old/'views').mkdir(parents=True)
        self.source = np.zeros((4,8,4),dtype=np.uint8)
        self.source[:,:,:] = [30,40,50,255]
        solid = self.source.copy(); solid[:,:,:3] = 90
        # Each tile has known geometry, unknown geometry, and background.
        solid[1::2,1::2,3] = 0
        views = []
        for i in range(8):
            known = np.zeros((2,2,4),dtype=np.uint8); known[0,0]=255
            self.save(self.old/'views'/f'view-{i}-known.png',known)
            self.save(self.old/'views'/f'view-{i}-solid.png',solid[:2,:2])
            views.append(dict(index=i,camera_matrix_world=[[i]],ownership_sha256=sha(self.old/'views'/f'view-{i}-known.png')))
        old = dict(asset_id='test',collection_name='test Working',object_names=['a'],tile_size=[2,2],layout=dict(columns=4,rows=2),views=views)
        self.write(self.old/'views.json',old); self.save(self.old/'textured.png',self.source)
        self.m = json.loads(json.dumps(old)); self.m.update(reviewed_packet=str(self.old),reviewed_manifest_sha256=sha(self.old/'views.json'),lighting_config_sha256='a'*64)
        self.m['layout'].update(width=8,height=4)
        for i,v in enumerate(self.m['views']):v['crop']=dict(left=i%4*2,top=i//4*2,width=2,height=2)
        self.unknown=np.ones((4,8),bool); self.unknown[::2,::2]=False; self.unknown[1::2,1::2]=False
        result=self.source.copy();result[self.unknown,:3]=solid[self.unknown,:3]
        mask=np.full((4,8,4),255,np.uint8);mask[self.unknown,3]=0
        self.save(self.p/'input.png',result);self.save(self.p/'solid.png',solid);self.save(self.p/'mask.png',mask)
        self.a=dict(status='approved',asset_id='test',solid_sha256=sha(self.p/'solid.png'),lighting_sha256=sha(self.p/'solid.png'),derived_input=dict(kind='unknown-geometry-lighting-only',original_approved_source_sha256=sha(self.old/'textured.png'),lighting_config_sha256='a'*64,known_and_background_rgba_preserved=True,alpha_preserved=True,approval_scope='authorized'))
        self.sync()
    def save(self,p,a):Image.fromarray(a).save(p)
    def write(self,p,a):p.write_text(json.dumps(a))
    def sync(self):
        self.a['input_sha256']=sha(self.p/'input.png'); self.write(self.p/'approval.json',self.a);self.write(self.p/'views.json',self.m)
    def check(self):validate(self.p/'views.json',lambda p:np.array(Image.open(p).convert('RGBA')))
    def test_valid_derived(self):self.check()
    def test_legacy_exact(self):
        self.save(self.p/'input.png',self.source);self.a.pop('derived_input');self.sync();self.check()
    def test_legacy_changed_rejected(self):
        self.a.pop('derived_input');self.sync()
        with self.assertRaises(ValueError):self.check()
    def test_pixel_mutations_rejected_even_with_updated_input_hash(self):
        original=np.array(Image.open(self.p/'input.png'))
        for y,x,c in [(0,0,0),(1,1,0),(0,1,3),(0,1,0)]:
            changed=original.copy();changed[y,x,c]^=1;self.save(self.p/'input.png',changed);self.sync()
            with self.subTest(pixel=(y,x,c)),self.assertRaises(ValueError):self.check()
    def test_camera_layout_crop_and_provenance_mutations(self):
        pristine=json.loads(json.dumps(self.m)); approval=json.loads(json.dumps(self.a))
        mutations=[lambda:self.m['views'][0].update(camera_matrix_world=[[42]]),lambda:self.m['views'][0]['crop'].update(left=1),lambda:self.m['layout'].update(width=9),lambda:self.a['derived_input'].update(original_approved_source_sha256='b'*64),lambda:self.a.update(solid_sha256='b'*64),lambda:self.a['derived_input'].update(lighting_config_sha256='b'*64)]
        for mutate in mutations:
            self.m=json.loads(json.dumps(pristine));self.a=json.loads(json.dumps(approval));mutate();self.sync()
            with self.assertRaises(ValueError):self.check()
    def test_mask_mutation(self):
        mask=np.array(Image.open(self.p/'mask.png'));mask[0,0,3]=0;self.save(self.p/'mask.png',mask)
        with self.assertRaises(ValueError):self.check()

if __name__=='__main__':unittest.main()
