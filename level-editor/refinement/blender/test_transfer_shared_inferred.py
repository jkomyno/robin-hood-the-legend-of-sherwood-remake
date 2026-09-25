import unittest
import numpy as np
from transfer_shared_inferred import merge_inferred, transferred_ownership, require_empty_receiver


class SharedInferred(unittest.TestCase):
    def test_missing_provenance_only_allowed_for_empty_mesh(self):
        require_empty_receiver(0,0)
        for polygons,loops in [(1,3),(0,3),(1,0)]:
            with self.assertRaises(ValueError):require_empty_receiver(polygons,loops)

    def test_only_proven_generated_colors_change(self):
        donor=np.array([[[.1,.2,.3,1],[.4,.5,.6,1],[.7,.8,.9,1],[.2,.4,.6,1]]])
        target=np.array([[[.8,.7,.6,1],[.3,.2,.1,1],[.2,.3,.4,1],[.9,.8,.7,1]]])
        out,count=merge_inferred(donor,target,np.array([[2,0,2,1]]),np.array([[2,2,1,2]]))
        self.assertEqual(count,1)
        np.testing.assert_array_equal(out[0,0],donor[0,0])
        np.testing.assert_array_equal(out[0,1:],target[0,1:])
        np.testing.assert_array_equal(out[...,3],target[...,3])
        self.assertEqual(target[0,0,0],.8)

    def test_bounded_donors_require_opt_in_and_preserve_class(self):
        donor=np.array([[3,3,2,0,1]],dtype=np.uint8)
        target=np.array([[0,1,3,2,3]],dtype=np.uint8)
        default,chosen=transferred_ownership(donor,target)
        np.testing.assert_array_equal(default,[[0,1,2,2,3]])
        np.testing.assert_array_equal(chosen,[[False,False,True,False,False]])
        result,chosen=transferred_ownership(donor,target,allow_bounded_donors=True)
        np.testing.assert_array_equal(result,[[3,1,2,2,3]])
        np.testing.assert_array_equal(chosen,[[True,False,True,False,False]])
        np.testing.assert_array_equal(target,[[0,1,3,2,3]])

    def test_bounded_copy_preserves_source_alpha_and_target_only_pixels(self):
        donor=np.ones((1,4,4));target=np.zeros((1,4,4))
        target[...,3]=[.1,.2,.3,.4]
        out,count=merge_inferred(donor,target,np.array([[3,3,0,1]]),np.array([[0,1,2,3]]),allow_bounded_donors=True)
        self.assertEqual(count,1)
        np.testing.assert_array_equal(out[0,0,:3],[1,1,1])
        np.testing.assert_array_equal(out[0,1:],target[0,1:])
        np.testing.assert_array_equal(out[...,3],target[...,3])

    def test_reject_missing_or_invalid_provenance(self):
        a=np.zeros((1,2,4));mask=np.array([[1,2]])
        with self.assertRaises(ValueError):merge_inferred(a,a,np.array([[0,4]]),mask)
        with self.assertRaises(ValueError):merge_inferred(a,a,np.array([[0]]),mask)
        with self.assertRaises(ValueError):merge_inferred(a,np.zeros((1,3,4)),mask,mask)
        b=a.copy();b[0,0,0]=np.nan
        with self.assertRaises(ValueError):merge_inferred(a,b,mask,mask)


if __name__=='__main__':unittest.main()
