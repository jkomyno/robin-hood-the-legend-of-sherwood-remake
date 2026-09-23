"""Exact approval resolves only the named historical source-review hold."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from review_evidence import sha
from source_review_resolution import apply_generation_gate


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.handoff = {'texture_issue': {'status': 'correction-awaiting-user-review', 'generation_blocked': True}}
        self.file = self.root / 'handoff.json'; self.file.write_text(json.dumps(self.handoff))
        self.decision = {'asset_id': 'fixture', 'scope': 'geometry', 'decision': 'approved',
                         'revision_sha256': 'a'*64, 'exact_user_text': 'Synthetic corrected packet approved'}
        self.item = {'id': 'fixture', 'technical_eligible': True, 'stored_material_validation': 'PASS',
            'decision_state': 'current', 'user_approval': 'approved', 'user_decision': self.decision,
            'revision': {'sha256': 'a'*64, 'evidence': {'handoff': {'path': str(self.file), 'sha256': sha(self.file)}}}}
        self.resolution = {'asset_id': 'fixture', 'revision_sha256': 'a'*64,
            'approval_decision': copy.deepcopy(self.decision), 'handoff_sha256': sha(self.file),
            'cleared_blockers': {'handoff.texture_issue': self.handoff['texture_issue']}}
        self.path = self.root / 'source-review-resolutions.json'

    def run_gate(self):
        self.path.write_text(json.dumps({'version': 1, 'resolutions': [self.resolution]}))
        return apply_generation_gate(self.item, self.handoff, self.file, self.path)

    def test_exact_resolution_preserves_handoff(self):
        before = self.file.read_bytes()
        self.assertTrue(self.run_gate())
        self.assertEqual(before, self.file.read_bytes())
        self.assertEqual(self.item['source_review_resolution']['record'], self.resolution)

    def test_stale_resolution_binding(self):
        for field, value in [('revision_sha256', 'b'*64), ('handoff_sha256', 'b'*64),
                              ('approval_decision', {}), ('cleared_blockers', {})]:
            with self.subTest(field=field):
                old = copy.deepcopy(self.resolution); self.resolution[field] = value
                self.assertFalse(self.run_gate()); self.resolution = old

    def test_rejection_stale_approval_and_missing_technical(self):
        for field, value in [('user_approval', 'rejected'), ('decision_state', 'stale'),
                              ('technical_eligible', False), ('stored_material_validation', 'pending-or-failed')]:
            with self.subTest(field=field):
                old = copy.deepcopy(self.item); self.item[field] = value
                self.assertFalse(self.run_gate()); self.item = old

    def test_does_not_resolve_actual_texture_defect(self):
        self.handoff['texture_issue'] = {'status': 'incorrect-atlas'}
        self.file.write_text(json.dumps(self.handoff))
        self.item['revision']['evidence']['handoff']['sha256'] = sha(self.file)
        self.resolution['handoff_sha256'] = sha(self.file)
        self.resolution['cleared_blockers'] = {'handoff.texture_issue': self.handoff['texture_issue']}
        self.assertFalse(self.run_gate())

    def test_new_manifest_or_decision_hold_blocks(self):
        for record in (self.item, self.item['user_decision']):
            record['texture_issue'] = 'new incorrect atlas'
            self.assertFalse(self.run_gate())
            del record['texture_issue']

    def test_missing_resolution_blocks(self):
        self.assertFalse(apply_generation_gate(self.item, self.handoff, self.file, self.path))


if __name__ == '__main__': unittest.main()
