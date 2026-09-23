import unittest
from build_gallery import source_coverage_audit_matches


class CoverageGateTests(unittest.TestCase):
    def test_missing_failed_and_stale_reviews_block(self):
        evidence = {'model_sha256': 'model', 'packet_hashes': {'modified': {'views.json': 'views'}}}
        passed = {'status': 'PASS', 'model_sha256': 'model', 'modified_views_sha256': 'views', 'inspected_views': list(range(8))}
        self.assertTrue(source_coverage_audit_matches(passed, evidence))
        self.assertFalse(source_coverage_audit_matches({}, evidence))
        for key, value in [('status', 'FAIL'), ('model_sha256', 'old'),
                           ('modified_views_sha256', 'old'), ('inspected_views', [0])]:
            self.assertFalse(source_coverage_audit_matches({**passed, key: value}, evidence))
