import unittest
import numpy as np
from inferred_gap_repair import repair_face,validate_policy,face_allowed


def policy():
    return dict(version=1,receiver_objects=['own'],max_distance_texels=2,max_distance_world=2,
                bottom_band_world=1,max_face_fraction=.05,max_total_texels=100,max_abs_normal_z=.05)


class GapRepair(unittest.TestCase):
    def test_explicit_face_scope_rejects_foreign_invalid_and_missing_faces(self):
        p=policy();p['receiver_faces']={'own':[2,5]}
        validate_policy(p,['own'],{'own':6})
        self.assertTrue(face_allowed(p,'own',2));self.assertFalse(face_allowed(p,'own',3))
        self.assertTrue(face_allowed(policy(),'own',3))
        for faces in ({'foreign':[2]},{'own':[]},{'own':[2,2]},{'own':[True]},{'own':[6]}):
            p['receiver_faces']=faces
            with self.assertRaises(ValueError):validate_policy(p,['own'],{'own':6})

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

    def test_measured_band_only_extends_connected_basal_component(self):
        c,p,g,x=self.fixture();g[:]=True;p[:]=False
        g[0:3,0]=False;g[2,3]=False
        settings=policy();settings['max_distance_world']=4
        out,filled,stats=repair_face(c,p,g,x,settings,0,bottom_band_override=3)
        self.assertTrue(filled[2,0]);self.assertFalse(filled[2,3])
        self.assertTrue(stats['connected_basal_component'])
        np.testing.assert_array_equal(out[~filled],c[~filled])
        settings['face_bottom_bands']={'foreign':{'2':3}}
        with self.assertRaises(ValueError):validate_policy(settings)
        settings['face_bottom_bands']={'own':{'2':13}}
        with self.assertRaises(ValueError):validate_policy(settings)

    def test_physical_domain_limits_off_polygon_fill_and_preserves_rgba(self):
        c,p,g,x=self.fixture();domain=np.zeros((20,20),bool);domain[:,5:10]=True
        settings=policy();settings['physical_gutter_texels']=2
        out,filled,stats=repair_face(c,p,g,x,settings,0,physical_domain=domain)
        self.assertEqual(np.flatnonzero(filled[0]).tolist(),list(range(3,12)))
        np.testing.assert_array_equal(out[~filled],c[~filled]);np.testing.assert_array_equal(out[:,:,3],c[:,:,3])
        self.assertEqual(stats['eligible_samples'],180)
        with self.assertRaises(ValueError):repair_face(c,p,g,x,settings,0)
        with self.assertRaises(ValueError):repair_face(c,p,g,x,policy(),0,physical_domain=domain)
        for gutter in (-1,3,True,1.5):
            settings['physical_gutter_texels']=gutter
            with self.assertRaises(ValueError):validate_policy(settings)

    def test_foreign_receiver_and_unbounded_policy_rejected(self):
        with self.assertRaises(ValueError):validate_policy(policy(),['other'])
        bad=policy();bad['max_distance_texels']=50
        with self.assertRaises(ValueError):validate_policy(bad,['own'])
        c,p,g,x=self.fixture();g[0,0]=True
        with self.assertRaises(ValueError):repair_face(c,p,g,x,policy(),0)


if __name__=='__main__':unittest.main()
