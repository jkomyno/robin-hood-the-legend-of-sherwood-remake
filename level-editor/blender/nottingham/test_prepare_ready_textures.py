"""Resume only intact preparations and distinguish missing evidence from failure."""
import json
from pathlib import Path
import tempfile
import unittest
from prepare_ready_textures import classify, verify_prepared, sha, PILOTS

class ReadyPreparationTests(unittest.TestCase):
    def test_missing_technical_is_not_an_approval_or_corruption_failure(self):
        self.assertEqual(classify(ValueError('Exact saved-state material audit missing; run audit')), 'waiting-technical')
        self.assertEqual(classify(ValueError('Geometry approval model is stale')), 'failed')
        self.assertEqual(classify(ValueError('Prepared artifact changed: input.png')), 'failed')
    def test_pilot_is_reused_at_original_location(self):
        self.assertEqual(PILOTS['nottingham-castle-gate-west-tower']['experiment'].name,'pilot-west-tower')
    def test_resume_verifies_every_prepared_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'input.png').write_bytes(b'approved input')
            approval={'input_sha256':sha(p/'input.png')};(p/'approval.json').write_text(json.dumps(approval))
            (p/'preparation.json').write_text(json.dumps({'files':{'input.png':sha(p/'input.png'),'approval.json':sha(p/'approval.json')}}))
            self.assertEqual(verify_prepared(p),approval)
            (p/'input.png').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'artifact changed'):verify_prepared(p)

if __name__=='__main__':unittest.main()
