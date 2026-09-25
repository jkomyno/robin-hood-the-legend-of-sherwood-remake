import unittest,hashlib
import numpy as np
from isolated_surface_components import select

class IsolatedComponentTests(unittest.TestCase):
 def args(self):
  a=np.full((12,12),2,np.uint8);a[5:7,5]=0;p=np.ones(a.shape,bool);y,x=np.mgrid[:12,:12];pos=np.stack([x*.5,y*.5,y*0],-1);t=np.array([[5,5],[5,6]],dtype='<i4');s=dict(target_xy_sha256=hashlib.sha256(t.tobytes()).hexdigest(),max_texels=2,max_fraction=.05,max_distance_texels=1,max_distance_world=.5);return [a,p,pos,t,np.array([0,0]),s]
 def test_exact_component_original_donor(self):
  a=self.args();d,r=select(*a);self.assertEqual(len(d),2);self.assertTrue((a[0][d[:,1],d[:,0]]==2).all())
 def test_rejects_partial_component_source_and_budget(self):
  for variant in ['partial','source','budget','distance']:
   a=self.args()
   if variant=='partial':a[0][7,5]=0
   if variant=='source':a[0][5,5]=1
   if variant=='budget':a[-1]['max_texels']=1
   if variant=='distance':a[-1]['max_distance_world']=.1
   with self.assertRaises(ValueError):select(*a)
 def test_hash_binds_coordinates(self):
  a=self.args();a[3][0]=[3,3]
  with self.assertRaises(ValueError):select(*a)
if __name__=='__main__':unittest.main()
