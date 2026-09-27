import json
from pathlib import Path
import tempfile
import unittest

from source_authority import require_validated_source, sha
from compile_source_masks import effective_rule, verify_coverage


class SourceAuthorityTests(unittest.TestCase):
    def test_legacy_packet_cannot_generate(self):
        with self.assertRaisesRegex(ValueError, 'has not been validated'):
            require_validated_source({'worker_sha256': 'old-first-hit-worker'})

    def test_validation_is_bound_to_worker_and_original_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, receipt = root/'source.png', root/'validation.json'
            source.write_bytes(b'original pixels')
            data = dict(status='PASS', unresolved_source_nodes=0, unconstrained_receivers=0,
                        worker_sha256='worker-a', evidence={str(source): sha(source)})
            receipt.write_text(json.dumps(data))
            record = dict(worker_sha256='worker-a', source_ownership_validation={
                'path': str(receipt), 'sha256': sha(receipt)})
            require_validated_source(record)
            with self.assertRaisesRegex(ValueError, 'different worker'):
                require_validated_source({**record, 'worker_sha256': 'worker-b'})
            source.write_bytes(b'changed pixels')
            with self.assertRaisesRegex(ValueError, 'evidence changed'):
                require_validated_source(record)

    def test_partial_audit_cannot_generate_even_when_all_receivers_are_constrained(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory)/'validation.json'
            receipt.write_text(json.dumps(dict(status='PASS', unresolved_source_nodes=1,
                unconstrained_receivers=0, worker_sha256='worker-a')))
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                require_validated_source(dict(worker_sha256='worker-a', source_ownership_validation={
                    'path': str(receipt), 'sha256': sha(receipt)}))

    def test_unresolved_assignment_gets_black_bitmap_even_if_marked_reviewed(self):
        rule = effective_rule(dict(source_node='building-024', reviewed=True,
                                   mask_indices=[100]), 'Tree and ladder not yet separated')
        self.assertEqual(rule['mask_indices'], [10000])
        self.assertEqual(rule['ownership_status'], 'unresolved')

    def test_missing_receiver_never_uses_shared_unconstrained_fallback(self):
        class Constraints:
            def for_object(self, obj):
                return None if obj['name'] == 'missing-ladder' else ([], [])
        with self.assertRaisesRegex(ValueError, 'missing-ladder'):
            verify_coverage(Constraints(), [{'name': 'trunk'}, {'name': 'missing-ladder'}])


if __name__ == '__main__':
    unittest.main()
