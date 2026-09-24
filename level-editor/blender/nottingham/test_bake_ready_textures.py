import json
import tempfile
import unittest
from pathlib import Path
from bake_ready_textures import reviewed_inputs, sha, claim


class ReviewBindings(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.p=Path(self.temp.name)
        names=['input.png','views.json','solid.png','raw.png','preserved.png']
        for name in names:(self.p/name).write_bytes(name.encode())
        self.review=dict(asset_id='asset',status='ready-for-bake',all_eight_views_inspected=True,
            input_sha256=sha(self.p/'input.png'),views_sha256=sha(self.p/'views.json'),solid_sha256=sha(self.p/'solid.png'),
            generated_raw_path=str(self.p/'raw.png'),generated_raw_sha256=sha(self.p/'raw.png'),
            generated_preserved_path=str(self.p/'preserved.png'),generated_preserved_sha256=sha(self.p/'preserved.png'))
        self.save()
    def save(self):(self.p/'generation-review.json').write_text(json.dumps(self.review))
    def test_exclusive_job_claim_releases(self):
        first=claim(self.p)
        self.assertIsNotNone(first)
        try:self.assertIsNone(claim(self.p))
        finally:first.close()
        second=claim(self.p)
        self.assertIsNotNone(second);second.close()
    def test_ready(self):self.assertIsNotNone(reviewed_inputs(self.p,'asset'))
    def test_held_review_not_consumed(self):
        self.review['status']='needs-fix';self.save();self.assertIsNone(reviewed_inputs(self.p,'asset'))
    def test_changed_generated_pixels_rejected(self):
        (self.p/'preserved.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'generated_preserved'):reviewed_inputs(self.p,'asset')
    def test_wrong_identity_or_missing_inspection_rejected(self):
        with self.assertRaises(ValueError):reviewed_inputs(self.p,'other')
        self.review['all_eight_views_inspected']=False;self.save()
        with self.assertRaises(ValueError):reviewed_inputs(self.p,'asset')

if __name__=='__main__':unittest.main()
