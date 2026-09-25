import unittest
import numpy as np
from scoped_projection_merge import newly_generated_mask


class ScopedProjectionMerge(unittest.TestCase):
    def test_existing_source_and_generated_remain_excluded(self):
        p=np.array([[0,1,2,3]])
        np.testing.assert_array_equal(newly_generated_mask(np.ones(p.shape,bool),p,np.full(p.shape,2)),[[True,False,False,False]])

    def test_donor_source_and_extrapolation_are_not_generated(self):
        p=np.zeros((1,4),int)
        np.testing.assert_array_equal(newly_generated_mask(np.ones(p.shape,bool),p,np.array([[0,1,2,3]])),[[False,False,True,False]])

    def test_scope_excludes_other_faces_and_padding(self):
        np.testing.assert_array_equal(newly_generated_mask(np.array([[False,True]]),np.array([[0,0]]),np.array([[2,2]])),[[False,True]])

    def test_mismatch_and_unknown_classes_fail_closed(self):
        with self.assertRaises(ValueError):newly_generated_mask(np.ones((1,2),bool),np.zeros((1,1)),np.zeros((1,2)))
        with self.assertRaises(ValueError):newly_generated_mask(np.ones((1,1),bool),np.array([[4]]),np.array([[2]]))
        with self.assertRaises(ValueError):newly_generated_mask(np.ones((1,1)),np.array([[0]]),np.array([[2]]))


if __name__=='__main__':unittest.main()
