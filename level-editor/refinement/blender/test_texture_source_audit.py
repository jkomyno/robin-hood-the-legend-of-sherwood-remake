import unittest
import numpy as np
from audit_texture_source import verify_source_record

class SourceAudit(unittest.TestCase):
    def fixture(self):
        pixels=np.ones((2,2,4));mask=np.array([[1,0],[2,0]],dtype=np.uint8)
        final=pixels.copy();final[0,1,:3]=.4;flags=mask.copy();flags[0,1]=2
        return (pixels,mask,('geometry','all-uv')),(final,flags,('geometry','all-uv'))
    def test_generated_changes_allowed_and_source_retained(self):
        r=verify_source_record(*self.fixture());self.assertEqual(r['source_texels'],1)
    def test_reject_source_mask_alpha_and_geometry_drift(self):
        for kind in ('source','mask','alpha','geometry'):
            old,new=self.fixture();pixels,flags,geometry=new
            if kind=='source':pixels[0,0,0]=.5
            elif kind=='mask':flags[0,0]=2
            elif kind=='alpha':pixels[1,1,3]=0
            else:geometry=('geometry','wrong-uv')
            with self.subTest(kind=kind),self.assertRaises(ValueError):verify_source_record(old,(pixels,flags,geometry))

if __name__=='__main__':unittest.main()
