"""Regression checks for partial merlons and crowded posts at repeat joins."""
import unittest
import numpy as np

from build_segments import clip_parts, feature_intervals, repeat_interval


class RepeatIntervalTests(unittest.TestCase):
    def test_cross_crop_preserves_interpolated_texture_coordinates(self):
        positions=np.array([[0.,0,0],[10,0,0],[10,10,0]])
        attrs={'POSITION':positions,'TEXCOORD_0':positions[:,:2]/10}
        parts=clip_parts([(attrs,np.array([[0,1,2]]),3,'curtain')],[None,[2,8]])
        self.assertEqual(len(parts),1)
        clipped,_,material,name=parts[0]
        self.assertEqual((material,name),(3,'curtain'))
        self.assertTrue(np.all((clipped['POSITION'][:,1]>=2)&(clipped['POSITION'][:,1]<=8)))
        np.testing.assert_allclose(clipped['TEXCOORD_0'],clipped['POSITION'][:,:2]/10)
        np.testing.assert_array_equal(attrs['POSITION'],positions)

    def test_low_connecting_wall_does_not_merge_battlements(self):
        positions=[]
        for left,right,bottom,top in [(0,100,0,50),(10,30,50,80),(60,85,50,80)]:
            a,b,c,d=[left,0,bottom],[right,0,bottom],[right,0,top],[left,0,top]
            positions.extend([a,b,c,a,c,d])
        parts=[({'POSITION':np.array(positions)},np.arange(18).reshape(-1,3),None,'wall')]
        self.assertEqual(feature_intervals(parts,60),[[10,30],[60,85]])

    def test_partial_features_are_removed(self):
        features=[(0,20),(40,60),(80,100),(120,140),(160,180)]
        start,end,check=repeat_interval(features,10,170)
        self.assertEqual((start,end),(30,150))
        self.assertEqual(check['features'],3)
        self.assertEqual(check['seam_gap'],20)
        self.assertEqual(check['internal_gaps'],[20,20])

    def test_irregular_masonry_keeps_whole_features(self):
        features=[(0,18),(34,55),(73,98),(115,137),(155,179)]
        start,end,check=repeat_interval(features,20,150)
        self.assertEqual((start,end),(26,146))
        self.assertEqual(check['features'],3)
        self.assertEqual(check['seam_gap'],17)
        self.assertEqual(check['internal_gaps'],[18,17])

    def test_one_gap_cannot_define_a_repeat(self):
        with self.assertRaisesRegex(ValueError,'at least two'):
            repeat_interval([(0,20),(40,60)],0,60)


if __name__=='__main__':
    unittest.main()
