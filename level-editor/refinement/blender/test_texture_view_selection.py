import unittest
import numpy as np
from texture_view_selection import policy,ordered,eligible,SINGLE,DEFAULT
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
if __name__=='__main__':unittest.main()
