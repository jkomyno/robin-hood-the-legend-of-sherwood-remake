import unittest
import numpy as np
from audit_generated_visibility import verify_samples


class SavedVisibilityAudit(unittest.TestCase):
    def fixture(self):
        before=np.ones((2,3,4));mask=np.array([[1,0,2],[0,2,0]],dtype=np.uint8)
        after=before.copy();final=mask.copy();scope=np.zeros((2,3),bool);scope[0,1:]=True
        after[0,1:,:3]=.6;final[0,1]=2
        after[1,0,:3]=.4;final[1,0]=3
        return before,mask,after,final,scope

    def test_distinguishes_projection_and_inference(self):
        r=verify_samples(*self.fixture())
        self.assertEqual(r['new_projected_class2_texels'],1)
        self.assertEqual(r['new_inferred_class3_texels'],1)
        self.assertEqual(r['changed_existing_generated_texels'],1)

    def test_source_alpha_and_outside_changes_rejected(self):
        for kind in ['source','source-mask','alpha','outside-color','outside-projection']:
            b,m,a,f,s=self.fixture()
            if kind=='source':a[0,0,0]=.1
            elif kind=='source-mask':f[0,0]=2
            elif kind=='alpha':a[0,1,3]=.1
            elif kind=='outside-color':a[1,1,0]=.1
            else:f[1,2]=2;a[1,2,0]=.1
            with self.subTest(kind=kind),self.assertRaises(ValueError):verify_samples(b,m,a,f,s)


if __name__=='__main__':unittest.main()
