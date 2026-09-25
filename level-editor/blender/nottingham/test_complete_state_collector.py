"""Regression checks for explicit state authority and saved artifact bindings."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('collector', Path(__file__).with_name('build_gallery.py'))
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class CompleteStates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)
        self.config = dict(asset_id='nottingham-castle-main-hall', part_ids=['building-001'],
                           projection_manifest=str(self.p/'authority.json'), source_mask_manifest='masks')
        self.manifest = dict(sources={'exterior':'covered.png', 'interior':'revealed.png'},
                            projection_reviews={'patch-008': {'render_visibility': {
                                'reviewed':True, 'covered':{'hidden_nodes':[], 'hidden_components':[]},
                                'revealed':{'hidden_nodes':['foreign'], 'hidden_components':[]}}}})
        self.available = {'building-001','foreign'}
        for n in ['model.blend','covered.png','revealed.png']:(self.p/n).write_text(n)
        materials = dict(version=1, model_sha256=collector.sha(self.p/'model.blend'),records=[dict(
            object='owned',source_node='building-001',projection_component=None,
            covered_face_materials={'0':{'slot':0,'material':'covered'}},
            revealed_face_materials={'0':{'slot':1,'material':'revealed'}})])
        self.write('material-states.json',materials)
        self.layers={};self.bindings=[]
        for state in ['covered','revealed']:
            row=dict(source_path=str(self.p/(state+'.png')),projection_label='exterior' if state=='covered' else 'interior-patch-008',
                     receiver_nodes=['building-001'],occluder_nodes=sorted(self.available if state=='covered' else {'building-001'}))
            if state=='revealed':row['exclude_occluder_components']=[]
            self.layers[state]=[row]
            frame=self.p/state/'views.json';model=self.p/state/'model.blend';frame.parent.mkdir();model.write_text(state)
            self.write(str(frame),dict(projection_layers=[dict(row,source_sha256=collector.sha(self.p/(state+'.png')))],
                object_names=['owned'],render_object_names=['owned'],source_image=str(self.p/(state+'.png')),
                source_sha256=collector.sha(self.p/(state+'.png')),source_mask_evidence={'mask':'hash'}))
            self.bindings.append(dict(state=state,model=str(model),model_sha256=collector.sha(model),
                frame_manifest=str(frame),frame_manifest_sha256=collector.sha(frame),object_names=['owned'],
                hidden_context_nodes=[] if state=='covered' else ['foreign']))
        self.write('projection-state-layers.json',self.layers)
        self.save_bindings()
        self.addCleanup(patch.stopall)
        patch.dict(sys.modules,{'occlusion_constraints':types.SimpleNamespace(evidence_record=lambda _: {'mask':'hash'})}).start()
        self.supplement=patch.object(collector,'supplemental_packet').start()

    def write(self,name,data):
        p=self.p/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data))

    def save_bindings(self):
        self.write('inspection/state-models/manifest.json',dict(version=1,primary_model_sha256=collector.sha(self.p/'model.blend'),
            material_states_sha256=collector.sha(self.p/'material-states.json'),states=self.bindings))

    def run_guard(self):
        return collector.complete_state_records(self.p,self.config,self.manifest,self.available,{})

    def test_valid_states_still_require_supplemental_packet_checks(self):
        self.assertEqual(self.run_guard()[0]['receiver_nodes'],['building-001'])
        self.assertEqual(self.supplement.call_count,2)

    def test_reject_foreign_receiver_and_removed_occluder(self):
        for key,value in [('receiver_nodes',['building-001','foreign']),('occluder_nodes',['building-001'])]:
            with self.subTest(key=key):
                altered=copy.deepcopy(self.layers);altered['covered'][0][key]=value
                self.write('projection-state-layers.json',altered)
                with self.assertRaises(ValueError):self.run_guard()

    def test_reject_wrong_art_even_with_matching_packet_hash(self):
        altered=copy.deepcopy(self.layers);altered['revealed'][0]['source_path']=str(self.p/'covered.png')
        self.write('projection-state-layers.json',altered)
        with self.assertRaises(ValueError):self.run_guard()

    def test_reject_stale_model_or_materials(self):
        (self.p/'model.blend').write_text('changed')
        with self.assertRaises(ValueError):self.run_guard()

    def test_reject_stale_state_model(self):
        Path(self.bindings[1]['model']).write_text('changed')
        with self.assertRaises(ValueError):self.run_guard()

    def test_reject_rebound_wrong_visibility(self):
        frame=Path(self.bindings[1]['frame_manifest']);packet=json.loads(frame.read_text());packet['object_names']=[]
        self.write(str(frame),packet);self.bindings[1]['frame_manifest_sha256']=collector.sha(frame);self.save_bindings()
        with self.assertRaises(ValueError):self.run_guard()

    def test_reject_unreviewed_foreign_state_hiding(self):
        self.bindings[1]['hidden_context_nodes']=[];self.save_bindings()
        with self.assertRaises(ValueError):self.run_guard()

    def test_reject_partial_face_assignments_even_when_rebound(self):
        p=self.p/'material-states.json';m=json.loads(p.read_text());m['records'][0]['revealed_face_materials']={}
        self.write(str(p),m);self.save_bindings()
        with self.assertRaises(ValueError):self.run_guard()

    def add_contact_contract(self):
        # The supplement is supported only for the exact reviewed hall component.
        self.config['part_ids'].append('building-505');self.available.add('building-505')
        materials=json.loads((self.p/'material-states.json').read_text())
        materials['records'].append(dict(object='contact',source_node='building-505',
            projection_component='castle-hall-northwest-contact',
            covered_face_materials={'0':{'slot':0,'material':'source'}},
            revealed_face_materials={'0':{'slot':0,'material':'source'}}))
        self.write('material-states.json',materials)
        proof=self.p/'inspection/contact-material-provenance.json'
        self.write(str(proof),dict(status='PASS',model_sha256=collector.sha(self.p/'model.blend'),
            all_source_pixels=407,transferred_pixels=407))
        supplement=dict(version=1,model_sha256=collector.sha(self.p/'model.blend'),source_node='building-505',
            component='castle-hall-northwest-contact',patch_id='patch-008',
            cap_proof=dict(path=str(proof),sha256=collector.sha(proof)),states={})
        for b in self.bindings:
            state=b['state']; row=self.layers[state][0]
            row['receiver_nodes']=self.config['part_ids'][:];row['occluder_nodes']=sorted(set(row['occluder_nodes'])|{'building-505'})
            if state=='revealed':
                row['receiver_components']=[dict(source_node='building-505',patch_id='patch-008',
                    projection_components=['castle-hall-retained-roof','castle-hall-removable-cover'])]
                self.layers[state].append(dict(source_path=str(self.p/'covered.png'),projection_label='exterior',
                    receiver_nodes=['building-505'],occluder_nodes=row['occluder_nodes'],receiver_components=[dict(
                        source_node='building-505',patch_id='patch-008',projection_components=['castle-hall-northwest-contact'])]))
            frame=Path(b['frame_manifest']);packet=json.loads(frame.read_text())
            packet['projection_layers']=[dict(r,source_sha256=collector.sha(r['source_path'])) for r in self.layers[state]]
            packet['object_names'].append('contact');packet['render_object_names'].append('contact')
            self.write(str(frame),packet);b['frame_manifest_sha256']=collector.sha(frame);b['object_names'].append('contact')
            proof=self.p/'inspection/state-models'/state/'source-preservation.json'
            self.write(str(proof),dict(status='PASS',model_sha256=b['model_sha256'],extension_hash='exact-material-signature'))
            supplement['states'][state]=dict(path=str(proof),sha256=collector.sha(proof),model_sha256=b['model_sha256'])
        self.write('contact-state-supplement.json',supplement);self.write('projection-state-layers.json',self.layers);self.save_bindings()

    def test_contact_exact_supplement_passes(self):
        self.add_contact_contract();self.run_guard()

    def test_contact_changed_component_source_model_or_proof_fails(self):
        self.add_contact_contract()
        path=self.p/'contact-state-supplement.json';original=json.loads(path.read_text())
        for key,value in [('component','other'),('model_sha256','wrong')]:
            with self.subTest(key=key):
                changed=copy.deepcopy(original);changed[key]=value;self.write(str(path),changed)
                with self.assertRaises(ValueError):self.run_guard()
        self.write(str(path),original)
        changed=copy.deepcopy(self.layers);changed['revealed'][1]['source_path']=str(self.p/'revealed.png')
        self.write('projection-state-layers.json',changed)
        with self.assertRaises(ValueError):self.run_guard()
        self.write('projection-state-layers.json',self.layers)
        Path(original['cap_proof']['path']).write_text('{}')
        with self.assertRaises(ValueError):self.run_guard()

    def test_frozen_state_framing_rejects_wrong_reference_hash_and_model(self):
        self.add_contact_contract()
        supplement_path=self.p/'contact-state-supplement.json';supplement=json.loads(supplement_path.read_text())
        origin=self.p/'original-state-manifest.json'
        self.write(str(origin),dict(states=copy.deepcopy(self.bindings)))
        supplement['original_state_manifest']=dict(path=str(origin),sha256=collector.sha(origin))
        self.write(str(supplement_path),supplement)
        with patch.object(collector,'ORIGINAL_HALL_STATE_MANIFEST',self.p/'different'):
            with self.assertRaises(ValueError):self.run_guard()
        with patch.object(collector,'ORIGINAL_HALL_STATE_MANIFEST',origin):
            supplement['original_state_manifest']['sha256']='wrong';self.write(str(supplement_path),supplement)
            with self.assertRaises(ValueError):self.run_guard()
            supplement['original_state_manifest']['sha256']=collector.sha(origin)
            for state in ('covered','revealed'):
                b=supplement['states'][state];proof=json.loads(Path(b['path']).read_text())
                proof['original_model_sha256']='wrong';self.write(b['path'],proof);b['sha256']=collector.sha(b['path'])
            self.write(str(supplement_path),supplement)
            with self.assertRaises(ValueError):self.run_guard()


class StateRevisions(unittest.TestCase):
    def test_existing_revision_unchanged(self):
        packets = {'covered': {'hashes': {'views.json': 'abc'}}}
        import hashlib
        expected = hashlib.sha256(json.dumps(packets, sort_keys=True).encode()).hexdigest()
        self.assertEqual(collector.state_bundle_hash(packets), expected)
        self.assertIsNone(collector.state_bundle_hash({}))

    def test_material_contract_change_invalidates_state_revision(self):
        packets = {'covered': {'hashes': {'views.json': 'abc'}}}
        before = collector.state_bundle_hash(packets, {'material-states.json': 'old'})
        after = collector.state_bundle_hash(packets, {'material-states.json': 'new'})
        self.assertNotEqual(before, after)


if __name__=='__main__':unittest.main()
