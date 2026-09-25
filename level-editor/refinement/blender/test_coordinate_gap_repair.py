import unittest,json,hashlib
import numpy as np
from coordinate_gap_repair import repair_coordinate_band,validate_band

class CoordinateBandRepair(unittest.TestCase):
    def fixture(self):
        colors=np.ones((20,20,4));colors[:,:,:3]=.5
        protected=np.zeros((20,20),bool);protected[0,0]=True
        generated=np.ones((20,20),bool);generated[0,0]=False;generated[10,10]=False;generated[11,10]=False
        colors[10:12,10,:3]=.1
        yy,xx=np.mgrid[:20,:20];positions=np.stack((xx*.5,yy*.5,np.full_like(xx,67,dtype=float)),axis=-1)
        physical=np.ones((20,20),bool);points=[[110,210]]
        rule=dict(z_min=66.4,z_max=69.1,max_physical_texels=1,max_physical_area_world2=.3,max_distance_texels=3.2,max_distance_world=1.6,atlas_pixels=points,atlas_pixels_sha256=hashlib.sha256(json.dumps(points,separators=(',',':')).encode()).hexdigest(),reference_model_sha256='a'*64)
        return colors,protected,generated,positions,physical,(100,200),.25,rule
    def test_exact_band_leaves_connected_hidden_neighbor_and_source(self):
        args=self.fixture();out,selected,stats=repair_coordinate_band(*args)
        self.assertEqual(selected.sum(),1);self.assertEqual(out[10,10,0],.5)
        self.assertTrue(np.array_equal(out[~selected],args[0][~selected]));self.assertTrue(np.array_equal(out[:,:,3],args[0][:,:,3]));self.assertEqual(out[11,10,0],.1)
    def test_rejects_wrong_coordinate_protected_nonphysical_and_budget(self):
        for kind in ['z','protected','physical','area','distance','hash']:
            args=list(self.fixture())
            if kind=='z':args[3][10,10,2]=70
            elif kind=='protected':args[1][10,10]=True
            elif kind=='physical':args[4][10,10]=False
            elif kind=='area':args[7]['max_physical_area_world2']=.1
            elif kind=='distance':args[7]['max_distance_texels']=.5
            else:args[7]['atlas_pixels_sha256']='0'*64
            with self.subTest(kind=kind),self.assertRaises(ValueError):repair_coordinate_band(*args)

if __name__=='__main__':unittest.main()
