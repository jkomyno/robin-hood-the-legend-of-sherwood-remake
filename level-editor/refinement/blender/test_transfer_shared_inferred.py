import unittest
import numpy as np
from transfer_shared_inferred import merge_inferred


class SharedInferred(unittest.TestCase):
    def test_only_proven_generated_colors_change(self):
        donor=np.array([[[.1,.2,.3,1],[.4,.5,.6,1],[.7,.8,.9,1],[.2,.4,.6,1]]])
        target=np.array([[[.8,.7,.6,1],[.3,.2,.1,1],[.2,.3,.4,1],[.9,.8,.7,1]]])
        out,count=merge_inferred(donor,target,np.array([[2,0,2,1]]),np.array([[2,2,1,2]]))
        self.assertEqual(count,1)
        np.testing.assert_array_equal(out[0,0],donor[0,0])
        np.testing.assert_array_equal(out[0,1:],target[0,1:])
        np.testing.assert_array_equal(out[...,3],target[...,3])
        self.assertEqual(target[0,0,0],.8)

    def test_reject_missing_or_invalid_provenance(self):
        a=np.zeros((1,2,4));mask=np.array([[1,2]])
        with self.assertRaises(ValueError):merge_inferred(a,a,np.array([[0,3]]),mask)
        with self.assertRaises(ValueError):merge_inferred(a,a,np.array([[0]]),mask)
        with self.assertRaises(ValueError):merge_inferred(a,np.zeros((1,3,4)),mask,mask)
        b=a.copy();b[0,0,0]=np.nan
        with self.assertRaises(ValueError):merge_inferred(a,b,mask,mask)


if __name__=='__main__':unittest.main()
