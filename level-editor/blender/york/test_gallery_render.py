import unittest
import numpy as np
from build_gallery import solid


def record(*triangles):
    return {'parts':[{'positions':list(tri),'triangles':[[0,1,2]]} for tri in triangles]}


class SolidPreviewTests(unittest.TestCase):
    def test_crossing_faces_use_pixel_depth_not_triangle_centroids(self):
        ramp=((-10,-10,10),(10,-10,0),(0,10,0))
        flat=((-10,-10,4),(10,-10,4),(0,10,4))
        combined=np.array(solid(record(ramp,flat),0,90))
        ramp_image=np.array(solid(record(ramp),0,90))
        flat_image=np.array(solid(record(flat),0,90))
        self.assertFalse(np.array_equal(ramp_image[260,90],flat_image[260,90]))
        np.testing.assert_array_equal(combined[260,90],ramp_image[260,90])
        np.testing.assert_array_equal(combined[150,200],flat_image[150,200])
        np.testing.assert_array_equal(combined,np.array(solid(record(flat,ramp),0,90)))


if __name__=='__main__':unittest.main()
