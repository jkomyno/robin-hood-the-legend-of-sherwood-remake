import unittest
import numpy as np
from inferred_gap_repair import repair_face,validate_policy


def policy():
    return dict(version=1,receiver_objects=['own'],max_distance_texels=2,max_distance_world=2,
                bottom_band_world=1,max_face_fraction=.05,max_total_texels=100,max_abs_normal_z=.05)


class GapRepair(unittest.TestCase):
    def fixture(self):
        colors=np.zeros((20,20,4));colors[:,:,:3]=.2;colors[:,:,3]=.7
        generated=np.ones((20,20),dtype=bool);generated[0,:]=False
        protected=np.zeros((20,20),dtype=bool);protected[0,0]=True
        colors[1,:,:3]=[.6,.4,.3];colors[0,0,:3]=[1,.8,.5]
        y,x=np.mgrid[:20,:20];positions=np.stack((x,np.zeros_like(x),y),axis=-1).astype(float)
        return colors,protected,generated,positions

    def test_source_alpha_and_existing_generation_exact(self):
        c,p,g,x=self.fixture();out,filled,stats=repair_face(c,p,g,x,policy(),0)
        self.assertEqual(stats['repaired_texels'],19)
        np.testing.assert_array_equal(out[filled,:3],np.tile([.6,.4,.3],(19,1)))
        np.testing.assert_array_equal(out[~filled],c[~filled]);np.testing.assert_array_equal(out[:,:,3],c[:,:,3])

    def test_no_donor_no_cross_face_transfer(self):
        c,p,g,x=self.fixture();g[:]=False
        out,filled,_=repair_face(c,p,g,x,policy(),0)
        self.assertFalse(filled.any());np.testing.assert_array_equal(out,c)

    def test_distance_band_and_count_guards(self):
        c,p,g,x=self.fixture();x[0,:,2]=-3
        _,filled,_=repair_face(c,p,g,x,policy(),0);self.assertFalse(filled.any())
        c,p,g,x=self.fixture();x[0,:,0]+=50
        _,filled,_=repair_face(c,p,g,x,policy(),0);self.assertFalse(filled.any())
        c,p,g,x=self.fixture();limited=policy();limited['max_total_texels']=2
        with self.assertRaises(ValueError):repair_face(c,p,g,x,limited,0)

    def test_foreign_receiver_and_unbounded_policy_rejected(self):
        with self.assertRaises(ValueError):validate_policy(policy(),['other'])
        bad=policy();bad['max_distance_texels']=50
        with self.assertRaises(ValueError):validate_policy(bad,['own'])
        c,p,g,x=self.fixture();g[0,0]=True
        with self.assertRaises(ValueError):repair_face(c,p,g,x,policy(),0)


if __name__=='__main__':unittest.main()
