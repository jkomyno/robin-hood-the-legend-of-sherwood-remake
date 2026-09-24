import json
from pathlib import Path
import tempfile
import unittest
from lighting_review import load_lighting_review, sha


class LightingReviewTests(unittest.TestCase):
    def test_bindings_and_complete_displayed_states(self):
        with tempfile.TemporaryDirectory() as directory:
            w = Path(directory)
            (w / 'modified').mkdir()
            (w / 'lighting-review').mkdir()
            frame = w / 'modified/views.json'
            frame.write_text('{}')
            solid = w / 'lighting-review/solid.png'
            solid.write_bytes(b'reviewed image')
            profile = w / 'map-lighting.json'
            profile.write_text(json.dumps({'lighting': {'toward_sun': [1, 0, 1]}}))
            evidence = {'asset_id': 'asset', 'model_sha256': 'model',
                        'packet_hashes': {'modified': {'views.json': sha(frame)}}, 'state_packets': {}}
            self.assertEqual(load_lighting_review(w, evidence, profile), (None, {}))
            report = {'version': 1, 'status': 'PASS', 'asset_id': 'asset', 'model_sha256': 'model',
                      'modified_views_sha256': sha(frame), 'lighting_config_sha256': sha(profile),
                      'lighting': {'toward_sun': [1, 0, 1]}, 'packets': [{
                          'original_solid': str(w / 'modified/solid.png'), 'frame_manifest': str(frame),
                          'frame_manifest_sha256': sha(frame), 'solid': str(solid),
                          'solid_sha256': sha(solid), 'inspected_views': list(range(8))}]}
            path = w / 'lighting-review/review.json'
            def check(data):
                path.write_text(json.dumps(data))
                return load_lighting_review(w, evidence, profile)
            self.assertEqual(check(report)[1][str(w / 'modified/solid.png')], str(solid))
            for key, value in [('status', 'pending'), ('model_sha256', 'old'),
                               ('modified_views_sha256', 'old'), ('lighting_config_sha256', 'old')]:
                with self.subTest(key=key), self.assertRaises(ValueError):
                    check({**report, key: value})
            with self.assertRaises(ValueError):
                check({**report, 'packets': [{**report['packets'][0], 'inspected_views': [0]}]})
            evidence['state_packets']['revealed'] = {'directory': str(w / 'revealed')}
            with self.assertRaisesRegex(ValueError, 'state missing'):
                check(report)
