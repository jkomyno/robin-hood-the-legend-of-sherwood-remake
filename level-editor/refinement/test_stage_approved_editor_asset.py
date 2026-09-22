"""Approval gate tests for private staging; no production decisions or exports."""
import json
from test_record_approval import ApprovalTests
from record_approval import record
from stage_approved_editor_asset import validate


class PrivateStageTests(ApprovalTests):
    def test_stage_requires_current_explicit_approval(self):
        revision=self.exact()
        with self.assertRaises(ValueError):validate(self.path,'fixture')
        record(self.path,['fixture'],'Synthetic approval only',revision_sha256=revision)
        item,workspace,protected=validate(self.path,'fixture',expected_revision=revision)
        self.assertEqual(item['user_approval'],'approved')
        self.assertEqual(workspace,self.root)
        self.assertIn(self.root/'model.blend',protected)
        with self.assertRaises(ValueError):validate(self.path,'fixture',expected_revision='0'*64)
        (self.root/'model.blend').write_text('changed model')
        with self.assertRaises(ValueError):validate(self.path,'fixture')

    def test_rejected_stage_is_blocked(self):
        self.exact()
        record(self.path,['fixture'],'Synthetic rejection only',result='rejected')
        with self.assertRaises(ValueError):validate(self.path,'fixture')


if __name__=='__main__':
    import unittest
    unittest.main()
