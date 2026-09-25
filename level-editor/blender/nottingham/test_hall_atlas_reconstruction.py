import unittest
import numpy as np
from reconstruct_hall_generated_states import sample_donor,triangle_samples

class AtlasReconstruction(unittest.TestCase):
    def test_unknown_or_extrapolated_tap_blocks_copy(self):
        rgba=np.ones((2,2,4));ownership=np.array([[1,2],[2,0]],dtype=np.uint8)
        _,valid,_=sample_donor(rgba,ownership,[[.5,.5]])
        self.assertFalse(valid[0])
        ownership[1,1]=3
        self.assertFalse(sample_donor(rgba,ownership,[[.5,.5]])[1][0])

    def test_source_fraction_is_not_hidden_as_generated(self):
        rgba=np.ones((2,2,4));ownership=np.array([[1,2],[2,2]],dtype=np.uint8)
        _,valid,source=sample_donor(rgba,ownership,[[.5,.5]])
        self.assertTrue(valid[0]);self.assertEqual(source[0],.25)

    def test_zero_weight_unknown_tap_does_not_block_exact_center(self):
        rgba=np.ones((2,2,4));ownership=np.array([[2,0],[0,0]],dtype=np.uint8)
        self.assertTrue(sample_donor(rgba,ownership,[[.25,.25]])[1][0])

    def test_gutter_world_samples_stay_on_same_triangle(self):
        x,y,bary,score=triangle_samples([[.2,.2],[.8,.2],[.2,.8]],np.array([10,10]))
        self.assertTrue((score<0).any());self.assertTrue((bary>=0).all())
        np.testing.assert_allclose(bary.sum(axis=1),1)

if __name__=='__main__':unittest.main()
