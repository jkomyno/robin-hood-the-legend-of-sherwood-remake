"""Synthetic strict texture decisions; no real approvals or publication."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import patch
from review_evidence import sha
from texture_staging import validate_texture_handoff, _derived_packet, _object_ownership
from texture_decisions import IMAGE_FIELDS, fields


class TextureStagingTests(unittest.TestCase):
    def test_exact_endpoint_native_ownership(self):
        class Object(dict):
            name = 'deck'
        obj = Object(source_node='building-1', drawbridge_state='initial',
                     drawbridge_initial_source_node='building-1', drawbridge_applied_source_node='building-2')
        handoff = {'endpoint_id': 'initial', 'source_nodes': ['building-1', 'building-2']}
        self.assertEqual(_object_ownership([obj], handoff)['deck']['native_pair']['applied'], 'building-2')
        for field, bad in [('source_node', 'building-2'), ('drawbridge_state', 'applied'),
                           ('drawbridge_applied_source_node', 'building-3'),
                           ('drawbridge_initial_source_node', None)]:
            changed = Object(obj); changed[field] = bad
            with self.assertRaisesRegex(ValueError, 'exact reviewed native pair'):
                _object_ownership([changed], handoff)
        with self.assertRaisesRegex(ValueError, 'canonical source ownership'):
            _object_ownership([obj], dict(handoff, endpoint_id=None))

    def test_endpoint_static_source_is_explicit_and_complete(self):
        class Object(dict):
            pass
        deck = Object(source_node='building-1', drawbridge_state='initial',
                      drawbridge_initial_source_node='building-1', drawbridge_applied_source_node='building-2')
        deck.name = 'deck'
        canopy = Object(source_node='building-3'); canopy.name = 'canopy'
        h = {'endpoint_id': 'initial', 'source_nodes': ['building-1', 'building-2', 'building-3'],
             'static_source_nodes': ['building-3']}
        self.assertTrue(_object_ownership([deck, canopy], h)['canopy']['static_endpoint_source'])
        with self.assertRaisesRegex(ValueError, 'static and active'):
            _object_ownership([deck], h)
        with self.assertRaisesRegex(ValueError, 'exact reviewed native pair'):
            _object_ownership([deck, canopy], dict(h, static_source_nodes=[]))

    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.exp=self.root/'experiment';self.exp.mkdir();self.bake=self.exp/'bake';self.bake.mkdir()
        self.gen=self.exp/'generation';self.gen.mkdir();self.workspace=self.root/'workspace';self.workspace.mkdir()
        for path in [self.workspace/'model.blend',self.exp/'approved-model.blend']:
            path.write_bytes(b'approved model')
        self.geom={'id':'fixture','revision':{'sha256':'a'*64,'model_sha256':sha(self.workspace/'model.blend')},
                   'user_decision':{'asset_id':'fixture','decision':'approved','revision_sha256':'a'*64}}
        config={'asset_id':'fixture','part_ids':['building-001'],'map_name':'Fixture',
                'collection_name':'Fixture Working','scene_name':'Fixture Scene'}
        (self.workspace/'workspace.json').write_text(json.dumps(config))
        self.manifest=self.root/'geometry.json';self.manifest.write_text('{}')
        (self.root/'decisions.json').write_text('{}')
        for name in ['input.png','solid.png','mask.png']:(self.exp/name).write_bytes(name.encode())
        for name in ['generated-preserved.png','generated-raw.png']:(self.gen/name).write_bytes(name.encode())
        (self.gen/'generation.json').write_text('{"changedProtected":0}')
        (self.bake/'worker.blend').write_bytes(b'baked model')
        (self.bake/'actual.png').write_bytes(b'actual eight views')
        approval={'status':'approved','approved_by':'user','asset_id':'fixture','geometry_revision':'a'*64,
            'saved_model_sha256':self.geom['revision']['model_sha256'],'input_sha256':sha(self.exp/'input.png'),
            'solid_sha256':sha(self.exp/'solid.png')}
        (self.exp/'approval.json').write_text(json.dumps(approval))
        frames={'asset_id':'fixture','geometry_revision':'a'*64,'input_sha256':sha(self.exp/'input.png'),'source_blend':str(self.exp/'approved-model.blend'),
            'object_names':['Reviewed mesh'],'views':[{'index':i} for i in range(8)]}
        (self.exp/'views.json').write_text(json.dumps(frames))
        (self.exp/'preparation.json').write_text(json.dumps({'files':{'input.png':sha(self.exp/'input.png')}}))
        self.validation={'geometry_verified':True,'generated_sha256':sha(self.gen/'generated-preserved.png')}
        self.review={'status':'ready-for-user','all_eight_actual_views_inspected':True,
            'baked_model_sha256':sha(self.bake/'worker.blend'),'actual_sheet_sha256':sha(self.bake/'actual.png')}
        (self.bake/'validation.json').write_text(json.dumps(self.validation))
        (self.exp/'texture-review.json').write_text(json.dumps(self.review))
        self.paths={'solid':self.exp/'solid.png','textured':self.bake/'actual.png',
            'source_comparison':self.exp/'input.png','source_comparison_secondary':self.gen/'generated-preserved.png',
            'source_trace':self.gen/'generated-raw.png','validation':self.bake/'validation.json',
            'review':self.exp/'texture-review.json','model':self.bake/'worker.blend'}
        hashes={k:sha(p) for k,p in self.paths.items()}
        binding={'images':{k:hashes[k] for k in IMAGE_FIELDS},'reports':{k:hashes[k] for k in ['validation','review']}}
        self.decision={'asset_id':'fixture','scope':'texture','decision':'approved','exact_user_text':'Synthetic texture approval',
            'review_revision':hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest(),
            'evidence_sha256':hashes,'evidence_paths':{k:str(p) for k,p in self.paths.items()}}
        self.decisions=self.root/'texture-decisions.json';self.write_decisions([self.decision])
        self.mock=patch('stage_approved_editor_asset.validate',return_value=(self.geom,self.workspace,{}))
        self.validator=self.mock.start();self.addCleanup(self.mock.stop)

    def write_decisions(self,records):self.decisions.write_text(json.dumps({'version':1,'decisions':records}))
    def validate(self):return validate_texture_handoff(self.manifest,'fixture',self.decisions)

    def refresh_binding(self):
        hashes={k:sha(path) for k,path in self.paths.items()}
        images,reports=fields(self.decision)
        binding={'images':{k:hashes[k] for k in images},'reports':{k:hashes[k] for k in reports}}
        self.decision.update(evidence_paths={k:str(p) for k,p in self.paths.items()},evidence_sha256=hashes,
            review_revision=hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest())
        self.write_decisions([self.decision])

    def supplemental(self, identifier='revealed'):
        child=self.root/'supplemental';shutil.copytree(self.exp,child)
        frame=json.loads((child/'views.json').read_text());frame.update(source_blend=str(child/'approved-model.blend'),review_state='revealed')
        (child/'views.json').write_text(json.dumps(frame))
        review={**self.review,'status':'supplemental'}
        (child/'texture-review.json').write_text(json.dumps(review))
        self.review['texture_states']=[{'id':identifier,'name':identifier,'experiment':str(child)}]
        (self.exp/'texture-review.json').write_text(json.dumps(self.review))
        self.decision['texture_states']=[{'id':identifier,'name':identifier,'image_fields':list(IMAGE_FIELDS),
            'report_fields':['validation','review'],'model':str(child/'bake/worker.blend')}]
        for key,path in list(self.paths.items()):
            self.paths['texture_state_'+identifier+'_'+key]=child/path.relative_to(self.exp)
        self.refresh_binding()
        return child

    def test_supplemental_is_fully_validated_and_protected(self):
        child=self.supplemental();result=self.validate();state=result['texture_states'][0]
        self.assertEqual(state['id'],'revealed')
        self.assertEqual(state['blend_path'],str(child/'bake/worker.blend'))
        self.assertIn(str(child/'approval.json'),result['protected_files'])
        approval=json.loads((child/'approval.json').read_text());approval['geometry_revision']='f'*64
        (child/'approval.json').write_text(json.dumps(approval))
        with self.assertRaisesRegex(ValueError,'currently approved geometry'):self.validate()

    def test_missing_state_and_changed_supplemental_bake_rejected(self):
        child=self.supplemental()
        self.decision['texture_states']=[]
        self.paths={k:v for k,v in self.paths.items() if not k.startswith('texture_state_')};self.refresh_binding()
        with self.assertRaisesRegex(ValueError,'every declared'):self.validate()

    def test_supplemental_model_drift_rejected(self):
        child=self.supplemental();(child/'bake/worker.blend').write_bytes(b'changed supplemental')
        with self.assertRaisesRegex(ValueError,'state evidence changed'):self.validate()

    def test_endpoint_pair_uses_separately_approved_geometry(self):
        child=self.supplemental('applied');applied=self.root/'applied';shutil.copytree(self.workspace,applied)
        (applied/'model.blend').write_bytes(b'applied geometry');(child/'approved-model.blend').write_bytes(b'applied geometry')
        endpoints=[]
        for state,workspace,experiment in [('initial',self.workspace,self.exp),('applied',applied,child)]:
            model=workspace/'model.blend';frames=workspace/'frames.json';frames.write_text('{}')
            endpoints.append({'id':state,'status':'ready-for-user','workspace':str(workspace),'model':str(model),
                'frames':str(frames),'workspace_config':str(workspace/'workspace.json'),'model_sha256':sha(model)})
            for path in [model,frames,workspace/'workspace.json']:self.validator.return_value[2][path]=sha(path)
        self.geom['endpoint_reviews']=endpoints
        pairs={entry['id']:entry['model_sha256'] for entry in endpoints}
        for state,experiment in [('initial',self.exp),('applied',child)]:
            path=experiment/'approval.json';approval=json.loads(path.read_text())
            approval.update(endpoint_id=state,paired_model_sha256=pairs,saved_model_sha256=pairs[state]);path.write_text(json.dumps(approval))
        result=self.validate();self.assertEqual(result['endpoint_id'],'initial')
        self.assertEqual(result['texture_states'][0]['approved_source_blend'],str(child/'approved-model.blend'))
        approval=json.loads((child/'approval.json').read_text());approval['endpoint_id']='initial'
        (child/'approval.json').write_text(json.dumps(approval))
        with self.assertRaisesRegex(ValueError,'endpoint identity'):self.validate()

    def test_sampler_only_receipt_extension_requires_bake_hash(self):
        path=self.exp/'views.json';frames=json.loads(path.read_text())
        path.write_text(json.dumps(frames,indent=2)+'\n')
        preparation={'files':{'views.json':sha(path)}}
        (self.exp/'preparation.json').write_text(json.dumps(preparation))
        frames['texture_view_selection']='best-facing-single';path.write_text(json.dumps(frames,indent=2)+'\n')
        self.validation['evidence_sha256']={str(path):sha(path)}
        (self.bake/'validation.json').write_text(json.dumps(self.validation));self.refresh_binding()
        self.validate()
        frames['scene_name']='different camera scene';path.write_text(json.dumps(frames,indent=2)+'\n')
        self.validation['evidence_sha256']={str(path):sha(path)}
        (self.bake/'validation.json').write_text(json.dumps(self.validation));self.refresh_binding()
        with self.assertRaisesRegex(ValueError,'Prepared texture evidence'):self.validate()

    def test_derived_packet_reconstructs_mask_and_rejects_camera_or_mask_drift(self):
        from PIL import Image
        packet=self.root/'reviewed';(packet/'views').mkdir(parents=True)
        original={'asset_id':'fixture','scene_name':'Scene','tile_size':[2,2],
                  'layout':{'columns':4,'rows':2},'views':[]}
        for index in range(8):
            known=packet/'views'/f'view-{index}-known.png';Image.new('RGBA',(2,2),(0,0,0,255)).save(known)
            Image.new('RGBA',(2,2),(128,128,128,255)).save(packet/'views'/f'view-{index}-solid.png')
            original['views'].append({'index':index,'ownership_sha256':sha(known),'camera_matrix_world':[[index]]})
        for filename in ('textured.png','solid.png'):Image.new('RGBA',(8,4),(128,128,128,255)).save(packet/filename)
        for source,target in [('textured.png','input.png'),('solid.png','solid.png')]:shutil.copy2(packet/source,self.exp/target)
        Image.new('RGBA',(8,4),(255,255,255,0)).save(self.exp/'mask.png')
        source_frames=packet/'views.json';source_frames.write_text(json.dumps(original))
        self.geom['revision']['evidence']={'frames':{'path':str(source_frames),'sha256':sha(source_frames)}}
        frames=copy.deepcopy(original);frames.update(reviewed_packet=str(packet),reviewed_manifest_sha256=sha(source_frames))
        frames['layout'].update(width=8,height=4)
        for view in frames['views']:
            index=view['index'];view.update(input=f'views/view-{index}-input.png',mask=f'views/view-{index}-mask.png',
                crop={'left':index%4*2,'top':index//4*2,'width':2,'height':2})
        _derived_packet(self.exp,frames,self.geom,{})
        bad=copy.deepcopy(frames);bad['views'][1]['camera_matrix_world']=[[999]]
        with self.assertRaisesRegex(ValueError,'frozen camera'):_derived_packet(self.exp,bad,self.geom,{})
        Image.new('RGBA',(8,4),(255,255,255,255)).save(self.exp/'mask.png')
        with self.assertRaisesRegex(ValueError,'mask differs'):_derived_packet(self.exp,frames,self.geom,{})

    def test_selects_only_exact_approved_bake(self):
        result=self.validate()
        self.assertEqual(result['blend_path'],str(self.bake/'worker.blend'))
        self.assertEqual(result['object_names'],['Reviewed mesh'])
        self.assertEqual(result['source_nodes'],['building-001'])

    def test_latest_rejection_blocks_older_matching_approval(self):
        rejected={**self.decision,'decision':'rejected','evidence_sha256':{}}
        self.write_decisions([self.decision,rejected])
        with self.assertRaisesRegex(ValueError,'Latest'):self.validate()

    def test_changed_bake_and_geometry_revision_block(self):
        (self.bake/'worker.blend').write_bytes(b'changed bake')
        with self.assertRaises(ValueError):self.validate()
        (self.bake/'worker.blend').write_bytes(b'baked model')
        self.geom['revision']['sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'currently approved geometry'):self.validate()

    def test_geometry_gate_rejection_propagates(self):
        self.mock.stop()
        with patch('stage_approved_editor_asset.validate',side_effect=ValueError('latest geometry rejected')):
            with self.assertRaisesRegex(ValueError,'geometry rejected'):self.validate()
        self.mock.start()

    def test_changed_gallery_binding_and_preparation_block(self):
        old=copy.deepcopy(self.decision);self.decision['review_revision']='0'*64;self.write_decisions([self.decision])
        with self.assertRaisesRegex(ValueError,'gallery revision'):self.validate()
        self.write_decisions([old]);(self.exp/'mask.png').write_bytes(b'changed')
        prep={'files':{'mask.png':'0'*64}};(self.exp/'preparation.json').write_text(json.dumps(prep))
        with self.assertRaisesRegex(ValueError,'Prepared texture evidence'):self.validate()

    def test_duplicate_component_names_block(self):
        p=self.exp/'views.json';f=json.loads(p.read_text());f['object_names']*=2;p.write_text(json.dumps(f))
        with self.assertRaisesRegex(ValueError,'unique'):self.validate()


if __name__=='__main__':unittest.main()
