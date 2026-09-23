"""Synthetic revision/decision regression checks; no production approvals."""
import contextlib
import io
import hashlib
import json
import shutil
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
        (self.workspace / 'modified/views.json').write_text('{}')
        hashes = {}
        for name in [f'view-{i}.png' for i in range(8)] + ['materials.png', 'asset.glb']:
            path = audit.parent / name
            path.write_text('synthetic material '+name)
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        audit.write_text(json.dumps({'artifact_sha256': hashes,
            'frame_manifest_sha256': hashlib.sha256((self.workspace/'modified/views.json').read_bytes()).hexdigest(),
            'status': 'STRUCTURAL-PASS',
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

    def test_workspace_override_exposes_fresh_revision_without_transferring_approval(self):
        original = self.collect()
        decisions = self.decision(original)
        self.collect(decisions)
        revision = self.root / 'source-revision'
        shutil.copytree(self.workspace, revision)
        (revision / 'workspace.json').write_text(json.dumps({'map_name': 'Leicester', 'asset_id': 'sample'}))
        handoff = json.loads((revision / 'handoff.json').read_text())
        handoff.update(source_review='pending', texture_generation='blocked', texture_issue='Corrected source needs review')
        (revision / 'handoff.json').write_text(json.dumps(handoff))
        overrides = self.root / 'overrides.json'
        overrides.write_text(json.dumps({'version': 1, 'workspaces': {'sample': 'source-revision'}}))
        with contextlib.redirect_stdout(io.StringIO()):
            collect(self.catalog, self.assets, self.output, workspace_overrides=overrides)
        item = json.loads((self.output / 'review-candidates.json').read_text())['items'][0]
        self.assertEqual(item['workspace'], str(revision))
        self.assertEqual(item['status'], 'ready-for-user')
        self.assertEqual(item['decision_state'], 'stale')
        self.assertEqual(item['user_approval'], 'pending')
        self.assertTrue(item['generation_blocked'])
        self.assertFalse(item['generation_eligible'])
        self.assertTrue((self.output / 'reviewed-revisions/sample' / original['revision']['sha256'] / 'solid.png').exists())

    def test_workspace_override_rejects_wrong_identity_and_unknown_asset(self):
        overrides = self.root / 'overrides.json'
        for asset_id, config_id in [('sample', 'other'), ('unknown', 'sample')]:
            (self.workspace / 'workspace.json').write_text(json.dumps({'map_name': 'Leicester', 'asset_id': config_id}))
            overrides.write_text(json.dumps({'version': 1, 'workspaces': {asset_id: str(self.workspace)}}))
            with self.assertRaises(ValueError):
                collect(self.catalog, self.assets, self.output, workspace_overrides=overrides)

    def test_ground_remains_separate_from_catalog(self):
        ground = self.root / 'ground'
        shutil.copytree(self.workspace, ground)
        config = {'map_name': 'Leicester', 'asset_id': 'ground-background', 'part_ids': ['ground']}
        (ground / 'workspace.json').write_text(json.dumps(config))
        with contextlib.redirect_stdout(io.StringIO()):
            collect(self.catalog, self.assets, self.output, ground_workspace=ground)
        manifest = json.loads((self.output / 'review-candidates.json').read_text())
        self.assertEqual(manifest['total_groups'], 1)
        self.assertEqual(manifest['supplemental_count'], 1)
        self.assertEqual(len(manifest['items']), 2)
        self.assertTrue(manifest['items'][1]['supplemental'])
        config['part_ids'] = ['building-123']
        (ground / 'workspace.json').write_text(json.dumps(config))
        with self.assertRaises(ValueError):
            collect(self.catalog, self.assets, self.output, ground_workspace=ground)

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
        self.assertTrue(list((self.output / 'gallery/history').glob('*/images/*solid*.png')))
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

    def test_material_artifact_tamper_or_missing_stales_approval(self):
        item = self.collect()
        self.collect(self.decision(item))
        path = self.workspace / 'inspection/stored-materials/view-3.png'
        original = path.read_bytes()
        path.write_bytes(b'tampered')
        changed = self.collect()
        self.assertEqual(changed['status'], 'validation-pending')
        self.assertEqual(changed['decision_state'], 'stale')
        path.write_bytes(original)
        path.unlink()
        missing = self.collect()
        self.assertEqual(missing['status'], 'validation-pending')
        self.assertEqual(missing['decision_state'], 'stale')

    def test_material_frames_bound_and_artifacts_archived(self):
        item = self.collect()
        self.collect(self.decision(item))
        archive = self.output / 'reviewed-revisions/sample' / item['revision']['sha256']
        self.assertTrue((archive / 'stored_material_asset_glb.glb').is_file())
        self.assertTrue((archive / 'stored_material_view-7_png.png').is_file())
        (self.workspace / 'modified/views.json').write_text('{"changed":true}')
        changed = self.collect()
        self.assertEqual(changed['status'], 'validation-pending')
        self.assertEqual(changed['decision_state'], 'stale')

    def test_revealed_material_states_are_required_and_hashed(self):
        handoff_path = self.workspace / 'handoff.json'
        handoff = json.loads(handoff_path.read_text())
        handoff.update(has_revealed_state=True, revealed_solid='modified/solid.png',
                       revealed_textured='modified/textured.png', revealed_context='input/context.png')
        handoff_path.write_text(json.dumps(handoff))
        self.assertEqual(self.collect()['status'], 'validation-pending')
        states = []
        for state in ('covered', 'revealed'):
            folder = self.workspace / ('inspection/material-' + state)
            shutil.copytree(self.workspace / 'inspection/stored-materials', folder)
            states.append({'id': 'combined-' + state, 'audit': str(folder.relative_to(self.workspace)/'audit.json'),
                           'frame_manifest': 'modified/views.json'})
        handoff['stored_material_states'] = states
        handoff_path.write_text(json.dumps(handoff))
        item = self.collect()
        self.assertEqual(item['status'], 'ready-for-user')
        self.collect(self.decision(item))
        (self.workspace / 'inspection/material-revealed/materials.png').write_text('changed state')
        changed = self.collect()
        self.assertEqual(changed['status'], 'validation-pending')
        self.assertEqual(changed['decision_state'], 'stale')

    def test_incomplete_handoff_does_not_abort_gallery(self):
        (self.workspace/'review.md').unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            collect(self.catalog,self.assets,self.output)
        manifest=json.loads((self.output/'review-candidates.json').read_text())
        self.assertEqual(manifest['items'],[])
        self.assertEqual(manifest['without_packets'][0]['status'],'validation-pending')
        self.assertIn('review.md',manifest['without_packets'][0]['missing_evidence'])

    def test_explicit_geometry_approval_survives_added_audit(self):
        from record_approval import record
        audit=self.workspace/'inspection/stored-materials/audit.json'
        content=audit.read_text()
        audit.unlink()
        item=self.collect()
        record(self.output/'review-candidates.json',['sample'],'Synthetic geometry approval',geometry_only=True)
        pending=self.collect()
        self.assertEqual(pending['user_approval'],'approved')
        self.assertEqual(pending['status'],'validation-pending')
        self.assertFalse(pending['generation_eligible'])
        self.assertEqual(len(json.loads((self.output/'gallery/evidence.json').read_text())['items']),1)
        audit.write_text(content)
        ready=self.collect()
        self.assertEqual(ready['user_approval'],'approved')
        self.assertEqual(ready['status'],'ready-for-user')
        self.assertTrue(ready['generation_eligible'])

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
