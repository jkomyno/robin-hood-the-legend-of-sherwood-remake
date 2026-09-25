"""A work-resolution sidecar cannot override changed final review evidence."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from texture_progress import packet, validated_resolutions


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bake = self.root / 'bake-final'
        self.bake.mkdir()
        self.generation = self.root / 'generation-review.json'
        self.generation.write_text(json.dumps({'status': 'needs-fix'}))
        self.review = self.root / 'texture-review.json'
        self.review.write_text(json.dumps({'status': 'ready-for-user', 'bake': 'bake-final'}))
        (self.bake / 'worker.blend').write_bytes(b'original final model')
        (self.bake / 'validation.json').write_text('{}')
        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        self.sidecar = self.root / 'resolutions.json'
        self.sidecar.write_text(json.dumps({'resolutions': [{
            'original_generation_review': str(self.generation),
            'original_generation_review_sha256': digest(self.generation),
            'current_work_status': 'resolved-by-reviewed-projection',
            'resolution_evidence': {str(p): digest(p) for p in [
                self.review, self.bake / 'worker.blend', self.bake / 'validation.json']},
        }]}))

    def test_historical_hold_is_resolved_without_user_approval(self):
        result = packet(self.root, validated_resolutions(self.sidecar))
        self.assertEqual(result['generation_review'], 'needs-fix')
        self.assertEqual(result['current_work_status'], 'resolved-by-reviewed-projection')
        self.assertEqual(result['user_texture_approval'], 'pending')

    def test_changed_model_cannot_resolve_hold(self):
        (self.bake / 'worker.blend').write_bytes(b'different model')
        with self.assertRaisesRegex(ValueError, 'Stale work resolution'):
            validated_resolutions(self.sidecar)

    def test_new_hold_cannot_be_overridden(self):
        self.review.write_text(json.dumps({'status': 'fix-needed', 'bake': 'bake-final'}))
        with self.assertRaisesRegex(ValueError, 'no longer ready'):
            validated_resolutions(self.sidecar)

    def test_changed_bake_pointer_cannot_resolve_hold(self):
        self.review.write_text(json.dumps({'status': 'ready-for-user', 'bake': 'other'}))
        with self.assertRaisesRegex(ValueError, 'current bake'):
            validated_resolutions(self.sidecar)


if __name__ == '__main__':
    unittest.main()
