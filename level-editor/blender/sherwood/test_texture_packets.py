import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import texture_packets as packets


class SourceProtectionTest(unittest.TestCase):
    def test_batched_raster_keeps_nearest_and_first_face_across_batches(self):
        # More samples than one batch, with equal-depth and nearer replacements.
        corners=np.tile(np.array([[[0,0,1],[2,0,1],[0,2,1]]],float),(70000,1,1))
        corners[66000:,:,2]=2
        class Camera:
            tile=2
            def project(self,points):return points[:,0],points[:,1],points[:,2]
        target=SimpleNamespace(tri_image=np.full(len(corners),-1),image_kind=[])
        packets.TARGETS[id(corners)]=target
        try:
            depth,index,_=packets.raster(Camera(),corners,1)
            self.assertEqual(index[0,0],66000)
            self.assertEqual(depth[0,0],2)
            corners[:,:,2]=1
            depth,index,_=packets.raster(Camera(),corners,1)
            self.assertEqual(index[0,0],0)
        finally:packets.TARGETS.pop(id(corners))

    def test_original_view_is_kept_even_when_only_undersides_need_fill(self):
        class Camera:
            def __init__(self, azimuth, elevation, *args):
                self.toward = np.array([0, 0, np.sin(np.radians(elevation))])
        target = SimpleNamespace(corners=np.zeros((1,3,3)),bound=lambda:np.zeros((1,3)))
        points, normals = np.zeros((2,3)), np.array([[0,0,-1],[0,0,-1]])
        with patch.object(packets.uf,'Camera',Camera), \
             patch.object(packets.uf,'raster',return_value=(None,None,None)), \
             patch.object(packets.uf,'visible',return_value=(np.ones(2,bool),None,None)):
            views, coverage = packets.uf.select_cameras(target,points,normals,required_views=[(0,35)])
        self.assertEqual(views[0],(0,35))
        self.assertEqual(len(set(views)),8)
        self.assertEqual(coverage,1)

    def test_tiny_leaf_samples_preserve_opacity_and_first_hit_order(self):
        corners=np.array([[[0,0,1],[2,0,1],[0,2,1]],
                          [[.1,.1,1],[1,.1,1],[.1,1,1]],
                          [[.1,.1,2],[1,.1,2],[.1,1,2]]],float)
        class Camera:
            tile=2
            def project(self,points):return points[:,0],points[:,1],points[:,2]
        target=SimpleNamespace(tri_image=np.array([-1,-1,0]),
                image_kind=[packets.Kind('ownership',np.zeros((1,1)),True)],
                tri_uv=np.zeros((3,3,2)),atlas=lambda _:np.zeros((1,1,5),np.uint8))
        packets.TARGETS[id(corners)]=target
        try:
            depth,index,_=packets.raster(Camera(),corners,1)
            self.assertEqual(index[0,0],0)
            self.assertEqual(depth[0,0],1)
            corners[1,:,2]=3
            depth,index,_=packets.raster(Camera(),corners,1)
            self.assertEqual(index[0,0],1)
            self.assertEqual(depth[0,0],3)
        finally:packets.TARGETS.pop(id(corners))

    def test_identical_gray_colors_do_not_define_ownership(self):
        atlas=np.full((1,2,4),128,np.uint8);atlas[...,3]=255
        kind=packets.Kind('ownership',np.array([[1,0]],np.uint8),False)
        unknown=packets.island_unknown(kind,atlas,np.array([0,0]),np.array([0,1]),None,None,None)
        self.assertEqual(unknown.tolist(),[False,True])

    def test_transparent_texels_are_not_synthesis_receivers(self):
        atlas=np.full((1,2,4),128,np.uint8);atlas[0,:,3]=[0,255]
        kind=packets.Kind('ownership',np.zeros((1,2),np.uint8),True)
        unknown=packets.island_unknown(kind,atlas,np.array([0,0]),np.array([0,1]),None,None,None)
        self.assertEqual(unknown.tolist(),[False,True])

    def test_raster_sees_surface_behind_transparent_foliage(self):
        # Identical projected triangles, with a physically transparent one in front.
        corners=np.array([[[0,0,1],[4,0,1],[0,4,1]],[[0,0,0],[4,0,0],[0,4,0]]],float)
        class Camera:
            tile=4
            def project(self,points):return points[:,0],points[:,1],points[:,2]
        target=SimpleNamespace(tri_image=np.array([0,-1]),
                image_kind=[packets.Kind('ownership',np.zeros((1,1)),True)],
                tri_uv=np.zeros((2,3,2)),atlas=lambda _:np.zeros((1,1,5),np.uint8))
        packets.TARGETS[id(corners)]=target
        try:
            depth,index,_=packets.raster(Camera(),corners,1)
            self.assertEqual(index[0,0],1)
            self.assertEqual(depth[0,0],0)
        finally:packets.TARGETS.pop(id(corners))


if __name__=='__main__':unittest.main()
