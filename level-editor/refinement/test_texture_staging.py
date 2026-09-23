"""Synthetic strict texture decisions; no real approvals or publication."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from review_evidence import sha
from texture_staging import validate_texture_handoff
from texture_decisions import IMAGE_FIELDS


class TextureStagingTests(unittest.TestCase):
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
        frames={'asset_id':'fixture','source_blend':str(self.exp/'approved-model.blend'),
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
        self.mock.start();self.addCleanup(self.mock.stop)

    def write_decisions(self,records):self.decisions.write_text(json.dumps({'version':1,'decisions':records}))
    def validate(self):return validate_texture_handoff(self.manifest,'fixture',self.decisions)

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
