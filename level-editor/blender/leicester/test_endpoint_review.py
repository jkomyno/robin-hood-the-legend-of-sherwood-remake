"""Independent endpoint evidence, paired decisions and unchanged legacy identity."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import unittest
import test_review_candidates as fixtures
from review_candidates import collect
from review_evidence import geometry_basis


class EndpointReview(unittest.TestCase):
    def setUp(self):
        fixtures.ReviewDecisions.setUp(self)
        self.applied = self.root / 'applied'
        shutil.copytree(self.workspace, self.applied)
        for state, worker in [('initial', self.workspace), ('applied', self.applied)]:
            (worker / 'workspace.json').write_text(json.dumps({'asset_id': 'sample', 'map_name': 'Leicester'}))
            (worker / 'model.blend').write_text('independent ' + state + ' geometry')
            frame = worker / 'modified/views.json'
            frame.write_text(json.dumps({'views': [{'index': i} for i in range(8)]}))
            handoff = json.loads((worker / 'handoff.json').read_text())
            handoff.update(has_discrete_endpoint_state=True, endpoint_state=state,
                           model_sha256=self.sha(worker / 'model.blend'))
            (worker / 'handoff.json').write_text(json.dumps(handoff))
            audit = worker / 'inspection/stored-materials/audit.json'
            value = json.loads(audit.read_text())
            value.update(model_sha256=self.sha(worker / 'model.blend'), frame_manifest_sha256=self.sha(frame))
            audit.write_text(json.dumps(value))
        self.mapping = self.root / 'endpoints.json'
        self.mapping.write_text(json.dumps({'version': 1, 'groups': [{'asset_id': 'sample', 'states': {
            'initial': {'worker': str(self.workspace)}, 'applied': {'worker': str(self.applied)}}}]}))

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def collect(self, decision=None, mapping=True):
        with contextlib.redirect_stdout(io.StringIO()):
            collect(self.catalog, self.assets, self.output, decision,
                    endpoint_mapping=self.mapping if mapping else None)
        return json.loads((self.output / 'review-candidates.json').read_text())['items'][0]

    def decision(self, item, geometry_only=False):
        path = fixtures.ReviewDecisions.decision(self, item)
        if geometry_only:
            data = json.loads(path.read_text())
            data['decisions'][0]['geometry_basis'] = geometry_basis(item)
            path.write_text(json.dumps(data))
        return path

    def test_independent_hashes_one_card_and_all_endpoint_sheets(self):
        item = self.collect()
        self.assertEqual(item['status'], 'ready-for-user')
        self.assertNotEqual(item['endpoint_reviews'][0]['model_sha256'], item['endpoint_reviews'][1]['model_sha256'])
        page = (self.output / 'gallery/index.html').read_text()
        self.assertEqual(page.count('<article id="sample"'), 1)
        self.assertIn('approval covers both initial and applied models', page)
        evidence = json.loads((self.output / 'gallery/evidence.json').read_text())['items'][0]
        for state in ('initial', 'applied'):
            for kind in ('solid', 'textured', 'stored_material_textured'):
                self.assertIn('endpoint_' + state + '_' + kind, evidence['images'])
            self.assertIn('endpoint_' + state + '_model', item['revision']['evidence'])
        self.collect(self.decision(item))
        archive = self.output / 'reviewed-revisions/sample' / item['revision']['sha256']
        self.assertEqual((archive / 'endpoint_applied_model.blend').read_bytes(), (self.applied / 'model.blend').read_bytes())

    def test_missing_applied_evidence_or_mapping_blocks_readiness(self):
        self.assertEqual(self.collect(mapping=False)['status'], 'validation-pending')
        for name in ('model.blend', 'modified/views.json', 'inspection/stored-materials/view-7.png', 'review.md'):
            with self.subTest(name=name):
                path = self.applied / name
                data = path.read_bytes()
                path.unlink()
                item = self.collect()
                self.assertEqual(item['status'], 'validation-pending')
                self.assertFalse(item['generation_eligible'])
                path.write_bytes(data)

    def test_either_endpoint_change_stales_revision_and_geometry_only_decisions(self):
        for worker in (self.workspace, self.applied):
            for geometry_only in (False, True):
                with self.subTest(worker=worker, geometry_only=geometry_only):
                    item = self.collect()
                    self.collect(self.decision(item, geometry_only))
                    path = worker / 'model.blend'
                    original = path.read_bytes()
                    path.write_bytes(original + b' changed')
                    changed = self.collect()
                    self.assertEqual(changed['decision_state'], 'stale')
                    self.assertEqual(changed['user_approval'], 'pending')
                    self.assertEqual(changed['status'], 'validation-pending')
                    path.write_bytes(original)

    def test_applied_frame_or_material_change_stales_approval(self):
        for name in ('modified/views.json', 'inspection/stored-materials/materials.png'):
            with self.subTest(name=name):
                item = self.collect()
                self.collect(self.decision(item))
                path = self.applied / name
                original = path.read_bytes()
                path.write_text('{"changed": true}')
                changed = self.collect()
                self.assertEqual(changed['decision_state'], 'stale')
                self.assertEqual(changed['status'], 'validation-pending')
                path.write_bytes(original)

    def test_unpaired_revision_identity_is_unchanged(self):
        # An unrelated mapping must not salt every catalog revision.
        handoff = self.workspace / 'handoff.json'
        data = json.loads(handoff.read_text())
        data.pop('has_discrete_endpoint_state')
        handoff.write_text(json.dumps(data))
        original = self.collect(mapping=False)
        self.mapping.write_text('{"version":1,"groups":[]}')
        current = self.collect()
        self.assertEqual(original['revision'], current['revision'])
        self.assertEqual(geometry_basis(original), geometry_basis(current))

    def test_generation_reports_in_both_roots_are_attempts(self):
        nested_assets = self.root / 'round-1/assets-v2'
        for root in (nested_assets.parent / 'textures', nested_assets.parent.parent / 'textures'):
            report = root / 'sample/generation-1/generation.json'
            report.parent.mkdir(parents=True)
            report.write_text('{"status":"failed"}')
        with contextlib.redirect_stdout(io.StringIO()):
            collect(self.catalog, nested_assets, self.output)
        progress = json.loads((self.output / 'progress.json').read_text())
        self.assertEqual(progress['texture_generation_attempts'], 2)
        self.assertEqual(progress['texture_generation'], 'attempts-recorded')


if __name__ == '__main__':
    unittest.main()
