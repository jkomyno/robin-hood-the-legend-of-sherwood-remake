"""Synthetic revision/decision regression checks; no production approvals."""
import contextlib
import io
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from review_candidates import collect


class ReviewDecisions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = self.root / 'catalog.json'
        self.catalog.write_text(json.dumps({'map': 'Leicester', 'groups': [{'id': 'sample', 'name': 'Sample'}]}))
        self.assets = self.root / 'assets'
        self.workspace = self.assets / 'sample'
        self.output = self.root / 'output'
        for name in ('modified/solid.png', 'modified/textured.png', 'input/context.png',
                     'model.blend', 'recipe.py', 'review.md', 'ownership.json'):
            path = self.workspace / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic '+name)
        (self.workspace / 'validation.json').write_text('{"status":"PASS"}')
        audit = self.workspace / 'inspection/stored-materials/audit.json'
        audit.parent.mkdir(parents=True)
        audit.write_text(json.dumps({'status': 'STRUCTURAL-PASS',
            'visual_review': {'status': 'PASS'},
            'model_sha256': hashlib.sha256((self.workspace / 'model.blend').read_bytes()).hexdigest()}))
        (self.workspace / 'handoff.json').write_text(json.dumps({'status': 'ready-for-user',
            'notes': ['Synthetic test only'], 'ownership': 'ownership.json', 'recipe': 'recipe.py',
            'all_eight_views_inspected': True}))

    def collect(self, path=None):
        with contextlib.redirect_stdout(io.StringIO()):
            collect(self.catalog, self.assets, self.output, path)
        return json.loads((self.output / 'review-candidates.json').read_text())['items'][0]

    def decision(self, item, decision='approved'):
        record = {'asset_id': 'sample', 'scope': 'geometry', 'decision': decision,
                  'exact_user_text': 'Synthetic test decision only: '+decision,
                  'revision_sha256': item['revision']['sha256']}
        path = self.root / 'explicit-decisions.json'
        path.write_text(json.dumps({'version': 1, 'decisions': [record]}))
        return path

    def test_missing_pending(self):
        item = self.collect()
        self.assertEqual(item['user_approval'], 'pending')
        self.assertEqual(item['decision_state'], 'missing')

    def test_approval_persists_hides_and_archives_actual_evidence(self):
        item = self.collect()
        path = self.decision(item)
        approved = self.collect(path)
        self.assertEqual(approved['user_approval'], 'approved')
        self.assertEqual(self.collect()['user_approval'], 'approved')
        gallery = json.loads((self.output / 'gallery/evidence.json').read_text())
        self.assertEqual(gallery['items'], [])
        archive = self.output / 'reviewed-revisions/sample' / item['revision']['sha256']
        self.assertEqual((archive / 'solid.png').read_bytes(), (self.workspace / 'modified/solid.png').read_bytes())
        self.assertTrue(list((self.output / 'gallery/history').glob('*/images/*solid.png')))
        self.assertEqual(len(list((self.output / 'decision-history').glob('*.json'))), 1)

    def test_sheet_and_report_changes_invalidate_approval(self):
        for name in ('modified/solid.png', 'ownership.json', 'review.md', 'recipe.py'):
            with self.subTest(file=name):
                item = self.collect()
                self.collect(self.decision(item))
                path = self.workspace / name
                path.write_text(path.read_text()+' changed')
                stale = self.collect()
                self.assertEqual(stale['user_approval'], 'pending')
                self.assertEqual(stale['decision_state'], 'stale')
                self.assertNotEqual(stale['revision']['sha256'], item['revision']['sha256'])
                gallery = json.loads((self.output / 'gallery/evidence.json').read_text())
                self.assertEqual(len(gallery['items']), 1)

    def test_rejection_visible(self):
        item = self.collect()
        rejected = self.collect(self.decision(item, 'rejected'))
        self.assertEqual(rejected['status'], 'rejected')
        self.assertEqual(rejected['user_approval'], 'rejected')
        self.assertEqual(len(json.loads((self.output / 'gallery/evidence.json').read_text())['items']), 1)

    def test_material_gate_does_not_rewrite_worker_handoff(self):
        audit = self.workspace / 'inspection/stored-materials/audit.json'
        audit.unlink()
        item = self.collect()
        self.assertEqual(item['status'], 'validation-pending')
        self.assertEqual(item['worker_status'], 'ready-for-user')
        self.assertEqual(json.loads((self.workspace / 'handoff.json').read_text())['status'], 'ready-for-user')
        with self.assertRaises(ValueError):
            self.collect(self.decision(item))

    def test_implicit_or_wrong_revision_decision_rejected(self):
        item = self.collect()
        path = self.decision(item)
        data = json.loads(path.read_text())
        data['decisions'][0]['decision'] = 'pretty good'
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.collect(path)
        data['decisions'][0]['decision'] = 'approved'
        data['decisions'][0]['revision_sha256'] = 'model-only'
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.collect(path)


if __name__ == '__main__':
    unittest.main()
