import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import numpy as np
from generated_visibility import bounded_faces,far_plane,bounded_origin,visible_sample

class GeneratedVisibility(unittest.TestCase):
    def test_scope_is_explicit_and_foreign_faces_fail(self):
        self.assertEqual(bounded_faces({}, {'own':2}),set())
        self.assertEqual(bounded_faces({'texture_generated_bounded_visibility':{'own':[1]}},{'own':2}),{('own',1)})
        for scope in [{'foreign':[0]},{'own':[2]},{'own':[True]},{'own':[0,0]},{'own':[]}]:
            with self.assertRaises(ValueError):bounded_faces({'texture_generated_bounded_visibility':scope},{'own':2})
        with self.assertRaises(ValueError):bounded_faces({'texture_generated_bounded_visibility':{'own':[1]},'texture_receiver_face_indices':{'own':[0]}},{'own':2})
    def test_finite_origin_lies_beyond_all_occluders(self):
        vertices=np.array([[5000,-6000,0],[5010,-6020,100],[4900,-6100,20]])
        d=np.array([.06,.8,.597]);d/=np.linalg.norm(d)
        plane=far_plane(vertices,d);p=vertices[0];o=bounded_origin(p,d,plane)
        self.assertGreaterEqual(float(o@d),float((vertices@d).max())+.999999)
        self.assertLess(np.linalg.norm(o-p),1000)
        np.testing.assert_allclose(np.cross(o-p,d),0,atol=1e-10)
    def test_close_foreign_occluder_still_rejected(self):
        point=np.array([5000.,-6000.,100.]);hit=point+np.array([0,0,.001])
        self.assertFalse(visible_sample(hit,point,('other',0),('own',0)))
        self.assertFalse(visible_sample(hit,point,('own',1),('own',0)))
        self.assertFalse(visible_sample(point+[0,0,.021],point,('own',0),('own',0)))
        self.assertTrue(visible_sample(point,point,('own',0),('own',0)))
    def test_large_scene_bvh_and_near_occluder(self):
        try:
            from mathutils import Vector
            from mathutils.bvhtree import BVHTree
        except ImportError:self.skipTest('Blender BVH regression')
        target=[(4990,-6010,100),(5010,-6010,100),(5010,-5990,100),(4990,-5990,100)]
        point=Vector((5000,-6000,100));d=Vector((.99,0,.06)).normalized()
        tree=BVHTree.FromPolygons(target,[(0,1,2,3)])
        hit,_,index,_=tree.ray_cast(Vector(bounded_origin(point,d,far_plane(target,d))),-d)
        self.assertTrue(visible_sample(hit,point,('own',index),('own',0)))
        verts=target+[(x,y,z+.01)for x,y,z in target]
        tree=BVHTree.FromPolygons(verts,[(0,1,2,3),(4,5,6,7)])
        hit,_,index,_=tree.ray_cast(Vector(bounded_origin(point,d,far_plane(verts,d))),-d)
        self.assertEqual(index,1)
        self.assertFalse(visible_sample(hit,point,('own',index),('own',0)))

if __name__=='__main__':unittest.main(argv=['generated_visibility'])
