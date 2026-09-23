import unittest
import numpy as np
from texture_view_selection import policy,ordered,eligible,preferred_views,SINGLE,DEFAULT
class SelectionTests(unittest.TestCase):
    def test_default_order_unchanged_and_invalid_rejected(self):
        self.assertEqual(policy({}),DEFAULT)
        with self.assertRaises(ValueError):policy({'texture_view_selection':'invented'})
        candidates=[(.5,{'index':1}),(.8,{'index':0})]
        self.assertEqual(ordered(candidates,DEFAULT),candidates[::-1])
    def test_single_prefers_density_and_stable_index_for_ties(self):
        def c(score,index,scale):return score,{'index':index,'ortho_scale':scale,'crop':{'height':512}}
        candidates=[c(.5,0,100),c(.5,2,50),c(.5,1,50),c(.4,3,10)]
        self.assertEqual([v['index'] for _,v in ordered(candidates,SINGLE)],[1,2,0,3])
    def test_single_only_fills_first_visible_unknown(self):
        accepted=np.array([True,False,False]);remaining=np.array([False,False,True]);best=np.array([.7,.7,-np.inf])
        self.assertEqual(eligible(accepted,remaining,.7,best,SINGLE).tolist(),[False,False,True])
        self.assertEqual(eligible(accepted,remaining,.7,best,DEFAULT).tolist(),[False,True,True])
    def test_preferred_camera_precedes_score_but_fallback_order_is_unchanged(self):
        candidates=[(score,{'index':i,'ortho_scale':100,'crop':{'height':512}}) for i,score in enumerate([.2,.9,.7])]
        self.assertEqual([c[1]['index'] for c in ordered(candidates,SINGLE,0)],[0,1,2])
        self.assertEqual([c[1]['index'] for c in ordered(candidates,SINGLE)],[1,2,0])
        # Preference cannot turn a protected or already-filled texel eligible.
        self.assertEqual(eligible(np.array([True,False,False]),np.array([True,False,True]),.2,np.zeros(3),SINGLE).tolist(),[False,False,True])
    def test_preferred_map_is_exact_receiver_polygon_and_camera_scoped(self):
        manifest={'texture_view_selection':SINGLE,'views':[{'index':0},{'index':1}],
                  'texture_preferred_face_views':{'bank':{'2':0,'3':0}}}
        self.assertEqual(preferred_views(manifest,{'bank':4}),{('bank',2):0,('bank',3):0})
        for mapping in [{'foreign':{'0':0}},{'bank':{'4':0}},{'bank':{'-1':0}},{'bank':{'02':0}},
                        {'bank':{'0':2}},{'bank':{'0':True}},{'bank':{}},[]]:
            with self.subTest(mapping=mapping),self.assertRaises(ValueError):
                preferred_views({**manifest,'texture_preferred_face_views':mapping},{'bank':4})
        with self.assertRaises(ValueError):preferred_views({**manifest,'texture_view_selection':DEFAULT},{'bank':4})
        with self.assertRaises(ValueError):preferred_views({**manifest,'texture_receiver_face_indices':{'bank':[2]}},{'bank':4})
        self.assertEqual(preferred_views({'views':[{'index':0}]},{'bank':4}),{})
if __name__=='__main__':unittest.main()
