import unittest
from types import SimpleNamespace as NS
import numpy as np
from screen_fill import fill_visible_fragments


class VisibleFragmentTest(unittest.TestCase):
    def run_case(self, physical=True, editable=None, second=False):
        rgba=np.full((2,2,4),128,np.uint8);rgba[...,3]=255;rgba[1,1,3]=0
        before=rgba.copy();image=NS(name='atlas',pixels=rgba)
        kind=NS(mask=np.array([[1,0],[2,0]],np.uint8),physical=physical)
        corners=np.array([[[0,0,0],[2,0,0],[2,2,0]],[[0,0,0],[2,2,0],[0,2,0]]],float)
        target=NS(images=[image],image_kind=[kind],corners=corners,normals=np.array([[0,0,1],[0,0,1]]),
                  receiver_tri=np.ones(2,bool),tri_uv=corners[...,:2]/2,tri_image=np.zeros(2,int),region=None)
        camera=NS(toward=np.array([0,0,1.]),top=0,left=0)
        cameras=[(camera,None)]
        if second:
            camera.toward=np.array([0,np.sqrt(.75),.5])
            cameras.append((NS(toward=np.array([0,0,1.]),top=0,left=2),None))
        sheet=np.full((2,4,4),200,np.uint8);sheet[:,2:,:3]=77
        solid=np.ones((2,4),bool)
        editable=solid.copy() if editable is None else editable
        raster=lambda *args:(None,np.array([[0,0],[1,0]]),(corners[...,0],corners[...,1]))
        gr=NS(read_image=lambda im:im.pixels.copy(),write_image=lambda im,data:setattr(im,'pixels',data.copy()))
        result=fill_visible_fragments(target,cameras,sheet,solid,editable,raster,gr,1,.05)
        return before,image.pixels,kind.mask,result

    def test_only_unknown_opaque_receivers_change(self):
        before,after,mask,result=self.run_case()
        self.assertEqual(result,{'atlas':1})
        np.testing.assert_array_equal(after[0,0],before[0,0])
        np.testing.assert_array_equal(after[1],before[1])
        np.testing.assert_array_equal(after[...,3],before[...,3])
        np.testing.assert_array_equal(after[0,1,:3],[200]*3)
        np.testing.assert_array_equal(mask,[[1,2],[2,0]])

    def test_api_edit_domain_is_required(self):
        before,after,mask,result=self.run_case(editable=np.zeros((2,4),bool))
        self.assertFalse(result)
        np.testing.assert_array_equal(after,before)
        np.testing.assert_array_equal(mask,[[1,0],[2,0]])

    def test_most_facing_view_wins_without_averaging(self):
        before,after,mask,result=self.run_case(physical=False,second=True)
        self.assertEqual(result,{'atlas':2})
        np.testing.assert_array_equal(after[[0,1],[1,1],:3],[[77]*3]*2)
        np.testing.assert_array_equal(after[[0,1],[0,0]],before[[0,1],[0,0]])


if __name__=='__main__':unittest.main()
