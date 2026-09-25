import copy
import json
import tempfile
import unittest
from pathlib import Path
from review_evidence import sha
from texture_preparation_identity import resolve


class PreparationIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        model = self.root/'model.blend'; model.write_bytes(b'exact approved model')
        selection = dict(parent_geometry_revision='parent', preparation_model=str(model), preparation_state='covered')
        path = self.root/'selection.json'; path.write_text(json.dumps(selection))
        self.item = dict(id='house', **selection, preparation_selection=str(path),
                         approval_provenance={'exact_user_text': 'approved'},
                         revision={'sha256':'prepared','model_sha256':sha(model),'evidence':{
                             'model':{'path':str(model),'sha256':sha(model)},
                             'selection':{'path':str(path),'sha256':sha(path)}}})
        manifest = self.root/'manifest.json'; manifest.write_text(json.dumps({'items':[self.item]}))
        receipt = dict(source_review_manifest=str(manifest),review_manifest_sha256=sha(manifest),approved_revision='parent')
        (self.root/'preparation.json').write_text(json.dumps(receipt))
        self.approval = dict(geometry_revision='parent',preparation_revision='prepared',review_state='covered',
                             approval_provenance=self.item['approval_provenance'],
                             source_decision={'revision_sha256':'prepared','decision':'approved'})
        self.frames = dict(geometry_revision='parent',preparation_revision='prepared',review_state='covered')

    def run_resolve(self, item=None, approval=None, frames=None):
        return resolve(item or self.item, self.root, {}, self.root,
                       approval or self.approval, frames or self.frames)

    def test_separate_parent_and_preparation_identity(self):
        _, _, revision, model = self.run_resolve()
        self.assertEqual(revision, 'parent'); self.assertEqual(model, self.item['revision']['model_sha256'])

    def test_rejects_actual_model_change(self):
        (self.root/'model.blend').write_bytes(b'changed geometry')
        with self.assertRaisesRegex(ValueError, 'not approved'):self.run_resolve()

    def test_rejects_selection_change(self):
        item=copy.deepcopy(self.item);item['preparation_state']='revealed'
        with self.assertRaisesRegex(ValueError, 'selection changed'):self.run_resolve(item=item)

    def test_rejects_manifest_camera_input_or_ownership_change(self):
        # The preparation receipt binds all fields/evidence of the normalized
        # manifest, including input images, cameras and source ownership.
        for field in ['input_sha256','camera_matrix_world','source_mask_manifest']:
            with self.subTest(field=field):
                p=self.root/'manifest.json';before=p.read_bytes()
                d=json.loads(before);d['items'][0][field]='changed';p.write_text(json.dumps(d))
                with self.assertRaisesRegex(ValueError, 'manifest changed'):self.run_resolve()
                p.write_bytes(before)

    def test_rejects_revision_state_and_approval_drift(self):
        for field,value in [('geometry_revision','other'),('preparation_revision','other'),('review_state','revealed'),('approval_provenance',{}),('source_decision',{})]:
            with self.subTest(field=field):
                a=copy.deepcopy(self.approval);a[field]=value
                with self.assertRaises(ValueError):self.run_resolve(approval=a)
        f=dict(self.frames,preparation_revision='other')
        with self.assertRaises(ValueError):self.run_resolve(frames=f)

    def test_supplemental_state_requires_same_exact_approval_lineage(self):
        from unittest.mock import patch
        primary=copy.deepcopy(self.item)
        primary['revision']['sha256']='primary-preparation'
        primary['preparation_state']='revealed'
        primary['approval_provenance']={'exact_user_text':'approved','selected_state':'revealed'}
        self.item['approval_provenance']={'exact_user_text':'approved','selected_state':'covered'}
        self.approval['approval_provenance']=self.item['approval_provenance']
        manifest=self.root/'manifest.json'
        manifest.write_text(json.dumps({'items':[self.item]}))
        receipt=json.loads((self.root/'preparation.json').read_text())
        receipt['review_manifest_sha256']=sha(manifest)
        (self.root/'preparation.json').write_text(json.dumps(receipt))
        (self.root/'decisions.json').write_text('{}')
        with patch('stage_approved_editor_asset.validate',return_value=(self.item,self.root,{})):
            selected,_,_,_=resolve(primary,self.root,{},self.root,self.approval,self.frames,supplemental=True)
            self.assertEqual(selected['preparation_state'],'covered')
            for field,value in [('exact_user_text','different approval'),('selected_state','covered')]:
                altered=copy.deepcopy(primary);altered['approval_provenance'][field]=value
                with self.subTest(field=field),self.assertRaisesRegex(ValueError,'different approved geometry'):
                    resolve(altered,self.root,{},self.root,self.approval,self.frames,supplemental=True)

    def test_parent_without_bound_selection_fails(self):
        item=copy.deepcopy(self.item);item['revision']['evidence'].pop('selection')
        with self.assertRaises(ValueError):self.run_resolve(item=item)

if __name__=='__main__':unittest.main()
