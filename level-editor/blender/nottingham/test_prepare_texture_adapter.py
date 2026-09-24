"""Approval normalization must not infer authorization from gallery status."""
import copy
import unittest
from prepare_texture_adapter import validate_approval


class ApprovalAdapterTests(unittest.TestCase):
    def setUp(self):
        self.item={'id':'asset','user_approval':'approved'}
        self.fresh={'model_sha256':'model','packet_hashes':{'input':{'views.json':'before'},'modified':{'views.json':'after'}}}
        self.evidence=dict(copy.deepcopy(self.fresh),state_bundle_sha256='states',lighting_review_sha256='light',user_decision_matches_revision=True)
        self.approval={'asset_id':'asset','decision':'approved','exact_text':'asset: approved',
                       'model_sha256':'model','modified_views_sha256':'after','state_bundle_sha256':'states','lighting_review_sha256':'light'}

    def check(self):validate_approval(self.item,self.evidence,self.approval,self.fresh)

    def test_current_explicit_approval(self):self.check()

    def test_stale_revision_fields_rejected(self):
        for key in ['model_sha256','modified_views_sha256','state_bundle_sha256','lighting_review_sha256']:
            with self.subTest(key=key):
                old=self.approval[key];self.approval[key]='stale'
                with self.assertRaises(ValueError):self.check()
                self.approval[key]=old

    def test_gallery_status_cannot_grant_approval(self):
        self.approval['decision']='revision-requested'
        with self.assertRaises(ValueError):self.check()

    def test_changed_packet_rejected_even_if_primary_model_matches(self):
        self.evidence['packet_hashes']['input']['views.json']='changed'
        with self.assertRaises(ValueError):self.check()

    def test_missing_exact_user_text_rejected(self):
        self.approval['exact_text']=''
        with self.assertRaises(ValueError):self.check()


if __name__=='__main__':unittest.main()
