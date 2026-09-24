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

class BakeGuardTests(unittest.TestCase):
    def packet(self,root):
        from pathlib import Path
        from PIL import Image
        from uv_atlas import sha
        root=Path(root);experiment=root/'experiment';bake=root/'bake';frames=root/'reviewed';experiment.mkdir();bake.mkdir();frames.mkdir();(frames/'views.json').write_text('{}')
        (experiment/'approved-model.blend').write_bytes(b'approved-fixture');(bake/'worker.blend').write_bytes(b'baked-fixture')
        image=np.full((4,4,4),255,np.uint8);image[1,1,:3]=128;mask=np.full_like(image,255);mask[1,1,3]=0;generated=image.copy();generated[1,1,:3]=[25,60,30]
        for path,values in ((experiment/'input.png',image),(experiment/'source-atlas.png',image),(experiment/'mask.png',mask),(bake/'atlas.png',generated)):Image.fromarray(values).save(path)
        Image.fromarray(np.full((4,4),255,np.uint8)).save(experiment/'surface.png')
        evidence=fixture();evidence.update(model_sha256=sha(experiment/'approved-model.blend'),atlas_sha256=sha(experiment/'source-atlas.png'))
        (experiment/'uv-evidence.json').write_text(json.dumps(evidence));actual=copy.deepcopy(evidence);actual.update(model_sha256=sha(bake/'worker.blend'),atlas_sha256=sha(bake/'atlas.png'));(bake/'uv-evidence.json').write_text(json.dumps(actual))
        (experiment/'views.json').write_text(json.dumps(dict(projection_kind='uv-atlas',reviewed_packet=str(frames))))
        (experiment/'preparation.json').write_text(json.dumps(dict(files={p.name:sha(p) for p in experiment.iterdir()})))
        record=dict(projection_kind='uv-atlas',preparation_sha256=sha(experiment/'preparation.json'),frame_manifest_sha256=sha(frames/'views.json'),baked_model_sha256=sha(bake/'worker.blend'),approved_model_sha256=sha(experiment/'approved-model.blend'),baked_uv_evidence_sha256=sha(bake/'uv-evidence.json'),generated_sha256=sha(bake/'atlas.png'))
        return record,experiment,bake

    def test_valid_nonplanar_bake_and_protected_pixel_rejection(self):
        import tempfile
        from PIL import Image
        from uv_atlas import validate_uv_atlas_bake
        with tempfile.TemporaryDirectory() as root:
            record,experiment,bake=self.packet(root)
            self.assertEqual(validate_uv_atlas_bake(record,experiment,bake)['editable_pixels'],1)
            a=np.array(Image.open(bake/'atlas.png'));a[0,0,0]=0;Image.fromarray(a).save(bake/'atlas.png')
            with self.assertRaisesRegex(ValueError,'Protected'):validate_uv_atlas_bake(record,experiment,bake)

    def test_baked_geometry_change_rejected_even_with_updated_evidence_hash(self):
        import tempfile
        from uv_atlas import validate_uv_atlas_bake,sha
        with tempfile.TemporaryDirectory() as root:
            record,experiment,bake=self.packet(root);p=bake/'uv-evidence.json';actual=json.loads(p.read_text());actual['geometry']['actual_fixture'][0][0][0]=.5
            actual['geometry_uv_matrix_sha256']=hashlib.sha256(json.dumps(actual['geometry'],sort_keys=True,separators=(',',':')).encode()).hexdigest();p.write_text(json.dumps(actual));record['baked_uv_evidence_sha256']=sha(p)
            with self.assertRaisesRegex(ValueError,'changed actual geometry'):validate_uv_atlas_bake(record,experiment,bake)
