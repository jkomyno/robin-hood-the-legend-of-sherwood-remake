"""Run with Blender Python: reviewed foreground masks must preserve depth ownership."""
import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from occlusion_constraints import SourceMaskConstraints, evidence_record
from source_visibility import first_source_hit

class SourceVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.receiver={'source_node':'house'};self.foreign={'source_node':'wall'}
        self.entry={'reviewed':True,'source_node':'wall','receiver_nodes':['house'],
                    'mask_indices':[1],'reason':'Native wall boundary excludes observed roof strip'}
        (self.root/'1.png').write_bytes(b'bound-mask-bytes')
        (self.root/'inventory.json').write_text(json.dumps({'masks':[{'index':1,'box_top_left':[0,0],'box_size':[2,1],'png':'1.png'}]}))
    def tearDown(self):self.temp.cleanup()
    def load(self,entries=None):
        p=self.root/'manifest.json';p.write_text(json.dumps({'version':1,'mask_inventory':'inventory.json','projections':{'exterior':{'source_sha256':'a'*64,'state':'covered','assignments':[],'occluder_constraints':entries if entries is not None else [self.entry]}}}))
        return SourceMaskConstraints(p,'exterior','a'*64,(2,1),image_loader=lambda _:np.array([[True,False]]))
    def cast(self,owners,pixel=(1,0),constraints=None,receiver=None):
        vertices=[];triangles=[]
        for i in range(len(owners)):
            z=len(owners)-i;off=len(vertices);vertices.extend([(0,0,z),(2,0,z),(0,2,z)]);triangles.append((off,off+1,off+2))
        tree=BVHTree.FromPolygons(vertices,triangles,all_triangles=True)
        return first_source_hit(tree,owners,Vector((.2,.2,10)),Vector((0,0,-1)),constraints=constraints or self.load(),receiver=receiver or self.receiver,source_pixel=pixel)
    def test_inside_bitmap_blocks_outside_continues(self):
        owners=[self.foreign,self.receiver]
        self.assertEqual(self.cast(owners,(0,0))[2],0)
        self.assertEqual(self.cast(owners)[2],1)
    def test_multiple_foreign_surfaces_continue_to_receiver(self):
        self.assertEqual(self.cast([self.foreign,self.foreign,self.receiver])[2],2)
    def test_other_occluder_still_blocks(self):
        self.assertEqual(self.cast([self.foreign,{'source_node':'tree'},self.receiver])[2],1)
    def test_nearest_own_surface_is_retained(self):
        self.assertEqual(self.cast([self.foreign,self.receiver,self.receiver])[2],1)
    def test_foreign_receiver_not_authorized(self):
        self.assertEqual(self.cast([self.foreign,self.receiver],receiver={'source_node':'other-house'})[2],0)
    def test_native_evidence_binds_occluder_only_masks(self):
        self.load();self.assertIn(str(self.root/'1.png'),evidence_record(self.root/'manifest.json'))
    def test_reject_unreviewed_self_and_unscoped_rules(self):
        for bad in [{'reviewed':False},{'receiver_nodes':[]},{'receiver_nodes':['wall']},{'reason':''},{'mask_indices':[99]}]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):self.load([{**self.entry,**bad}])
    def test_no_hit_after_foreign_is_not_receiver_ownership(self):
        self.assertIsNone(self.cast([self.foreign])[0])

    def test_bake_and_eight_view_review_use_same_scoped_rule(self):
        import bpy,math,hashlib
        from source_projection_bake import bake
        from refinement_review import render_review
        col=bpy.data.collections.new('OcclusionFixture Working')
        bpy.context.scene.collection.children.link(col)
        up=Vector((0,math.sin(math.radians(35)),math.cos(math.radians(35))))
        toward=Vector((0,-math.cos(math.radians(35)),math.sin(math.radians(35))))
        for node,depth,asset in [('house',0,'receiver'),('wall',2,'foreign')]:
            mesh=bpy.data.meshes.new(node)
            mesh.from_pydata([Vector((x,0,0))+up*y for x,y in ((2,-14),(14,-14),(14,-2),(2,-2))],[],[(0,1,2,3)])
            mesh.materials.append(bpy.data.materials.new(node));mesh.uv_layers.new(name='Source')
            obj=bpy.data.objects.new(node,mesh);obj['source_node']=node;obj['asset_group']=asset;obj.location=toward*depth;col.objects.link(obj)
        for name,mask in [('source',False),('foreground',True)]:
            image=bpy.data.images.new(name,width=16,height=16)
            image.pixels[:]=[c for y in range(16)for x in range(16)for c in ((float(x<8),)*3+(1,) if mask else (1,0,0,1))]
            image.filepath_raw=str(self.root/(name+'.png'));image.file_format='PNG';image.save()
        (self.root/'inventory.json').write_text(json.dumps({'masks':[{'index':1,'box_top_left':[0,0],'box_size':[16,16],'png':'foreground.png'}]}))
        source=self.root/'source.png';path=self.root/'manifest.json'
        manifest={'version':1,'mask_inventory':'inventory.json','projections':{'exterior':{'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'state':'covered','assignments':[],'occluder_constraints':[self.entry]}}}
        path.write_text(json.dumps(manifest))
        a=bake('OcclusionFixture',source,self.root/'bake.json',receiver_asset_id='receiver',source_mask_manifest=path,projection_label='exterior')
        self.assertGreater(a['known_texels'],0);self.assertGreater(a['unknown_texels'],0)
        render_review(self.root/'review',scene_name=bpy.context.scene.name,collection_name=col.name,asset_id='receiver',source_path=source,width=24,height=24,source_mask_manifest=path)
        views=json.loads((self.root/'review/views.json').read_text())['views']
        self.assertEqual(len(views),8);self.assertGreater(sum(v['counts']['source']for v in views),0)
        manifest['projections']['exterior']['occluder_constraints']=[];path.write_text(json.dumps(manifest))
        b=bake('OcclusionFixture',source,self.root/'blocked.json',receiver_asset_id='receiver',source_mask_manifest=path,projection_label='exterior')
        self.assertEqual(b['known_texels'],0)
        render_review(self.root/'blocked-review',scene_name=bpy.context.scene.name,collection_name=col.name,asset_id='receiver',source_path=source,width=24,height=24,source_mask_manifest=path)
        views=json.loads((self.root/'blocked-review/views.json').read_text())['views']
        self.assertEqual(sum(v['counts']['source']for v in views),0)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SourceVisibilityTests))
    if not result.wasSuccessful():raise RuntimeError('Source visibility tests failed')
