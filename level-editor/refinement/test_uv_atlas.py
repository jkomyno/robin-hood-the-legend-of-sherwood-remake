import copy,hashlib,json,unittest
import numpy as np
from uv_atlas import validate_evidence,raster_lighting

def fixture(world=None,uv=None):
    if world is None:world=[[[0,0,0],[1,0,0],[1,1,0]],[[0,0,0],[1,1,0],[0,1,-.5]]]
    if uv is None:uv=[[[0,0],[1,0],[1,1]],[[0,0],[1,1],[0,1]]]
    geometry={'actual_fixture':world,'uv':uv}
    triangles=[]
    for w,u in zip(world,uv):
        w=np.array(w,float);n=np.cross(w[1]-w[0],w[2]-w[0]);n/=np.linalg.norm(n);triangles.append(dict(world=w.tolist(),uv_top_left=u,normal=n.tolist()))
    return dict(physical_opacity='OPAQUE',direct_image_color=True,geometry=geometry,geometry_uv_matrix_sha256=hashlib.sha256(json.dumps(geometry,sort_keys=True,separators=(',',':')).encode()).hexdigest(),triangles=triangles,atlas_dimensions=[32,32])

LIGHT=dict(toward_sun=[0,0,1],ambient=.16,diffuse=.64,shadow_epsilon=.001)

class UVAtlasTests(unittest.TestCase):
    def test_nonplanar_surface_and_directional_shading(self):
        e=fixture();surface,solid,report=raster_lighting(e,LIGHT)
        self.assertTrue(surface.all());self.assertEqual(report['self_shadow_pixels'],0)
        self.assertEqual(solid[2,20,0],204)
        self.assertLess(solid[20,2,0],204)
        self.assertGreater(solid[20,2,0],40)
        self.assertTrue(np.all(solid[:,:,3]==255))

    def test_uv_overlap_and_degeneracy_fail(self):
        e=fixture();e['triangles'][1]['uv_top_left']=e['triangles'][0]['uv_top_left']
        with self.assertRaisesRegex(ValueError,'Overlapping'):validate_evidence(e)
        e=fixture();e['triangles'][0]['uv_top_left']=[[0,0]]*3
        with self.assertRaisesRegex(ValueError,'Degenerate UV'):validate_evidence(e)

    def test_physical_outside_remains_transparent(self):
        e=fixture();e['triangles']=e['triangles'][:1]
        surface,solid,_=raster_lighting(e,LIGHT)
        self.assertFalse(surface[25,2]);self.assertEqual(solid[25,2,3],0)
        self.assertTrue(surface[2,25]);self.assertEqual(solid[2,25,3],255)

    def test_saved_world_normal_and_geometry_tampering_fail(self):
        e=fixture();e['triangles'][0]['normal']=[1,0,0]
        with self.assertRaisesRegex(ValueError,'normal'):validate_evidence(e)
        e=fixture();e['geometry']['actual_fixture'][0][0][0]=2
        with self.assertRaisesRegex(ValueError,'digest'):validate_evidence(e)
        e=fixture();e['physical_opacity']='MASK'
        with self.assertRaisesRegex(ValueError,'opaque'):validate_evidence(e)

    def test_self_shadow_uses_actual_world_geometry(self):
        bottom=[[0,0,0],[1,0,0],[0,1,0]];top=[[0,0,1],[1,0,1],[0,1,1]]
        uv=[[[0,0],[.4,0],[0,1]],[[.6,0],[1,0],[.6,1]]]
        surface,solid,report=raster_lighting(fixture([bottom,top],uv),LIGHT)
        self.assertGreater(report['self_shadow_pixels'],0)
        self.assertEqual(solid[2,2,0],41)
        self.assertEqual(solid[2,22,0],204)

if __name__=='__main__':unittest.main()
