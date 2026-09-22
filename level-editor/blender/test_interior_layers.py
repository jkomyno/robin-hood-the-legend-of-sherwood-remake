"""Reviewed map ownership rejects missing evidence and preserves legacy partitions."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from interior_layers import (projection_receivers, projection_occluders,
                             projection_occluder_audit, validate_projection_reviews)


class AuthoredProjectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in ('interior.png', 'alpha.png'):
            (self.root / name).write_bytes(name.encode())
        self.review = dict(version=1, reviewed=True, patch_id='patch-000',
                           reviewer='fixture reviewer', evidence='Inspected state pair and shell.',
                           receiver_nodes=['building-001'], retained_occluder_nodes=['building-002'],
                           partial_cover_nodes=['building-003'], exclude_occluder_components=[],
                           receiver_components={},
                           source_sha256=hashlib.sha256(b'interior.png').hexdigest(),
                           alpha_sha256=hashlib.sha256(b'alpha.png').hexdigest())
        self.manifest = dict(map='Fixture', sources={'interior': 'interior.png'},
                             patches=[{'id': 'patch-000', 'graphic': {'alpha': 'alpha.png'}}],
                             projection_reviews={'patch-000': self.review})

    def test_receiver_and_shell_partition_does_not_infer_sight_or_cover_nodes(self):
        self.manifest['patches'][0]['sight_before'] = ['building-099']
        self.assertEqual(projection_receivers(self.manifest), {'patch-000': ['building-001']})
        self.assertEqual(projection_occluders(self.manifest, ['building-001', 'building-002',
                                                              'building-003', 'building-099']),
                         {'patch-000': ['building-001', 'building-002']})
        self.assertEqual(projection_occluder_audit(self.manifest)['patch-000']['partial_cover_nodes'],
                         ['building-003'])
        validate_projection_reviews(self.manifest, self.root)

    def test_unreviewed_missing_and_duplicate_ownership_fail_closed(self):
        for key, value in [('reviewed', False), ('reviewer', ''), ('receiver_nodes', []),
                           ('receiver_nodes', ['building-001', 'building-001']),
                           ('retained_occluder_nodes', None), ('source_sha256', 'stale'),
                           ('patch_id', 'patch-001')]:
            with self.subTest(key=key, value=value):
                manifest = copy.deepcopy(self.manifest)
                manifest['projection_reviews']['patch-000'][key] = value
                with self.assertRaises(ValueError):
                    projection_receivers(manifest)
        for reviews in ({}, {'patch-001': self.review}):
            with self.assertRaises(ValueError):
                projection_receivers({**self.manifest, 'projection_reviews': reviews})
        with self.assertRaises(ValueError):
            projection_occluders(self.manifest, ['building-001'])

    def test_changed_reveal_and_alpha_are_rejected(self):
        for name in ('interior.png', 'alpha.png'):
            original = (self.root / name).read_bytes()
            (self.root / name).write_bytes(b'changed')
            with self.assertRaises(ValueError):
                validate_projection_reviews(self.manifest, self.root)
            (self.root / name).write_bytes(original)

    def test_non_interior_trigger_needs_classification_but_no_graphic(self):
        self.manifest['patches'].append({'id': 'patch-001', 'pixel_vert': True})
        with self.assertRaises(ValueError):
            projection_receivers(self.manifest)
        trigger = dict(version=1, reviewed=True, patch_id='patch-001', role='non-interior',
                       reviewer='fixture reviewer', evidence='Trigger has no interior image.',
                       receiver_nodes=[], retained_occluder_nodes=[], partial_cover_nodes=[],
                       exclude_occluder_components=[], receiver_components={})
        self.manifest['projection_reviews']['patch-001'] = trigger
        self.assertEqual(projection_receivers(self.manifest), {'patch-000': ['building-001']})
        validate_projection_reviews(self.manifest, self.root)
        trigger['receiver_nodes'] = ['building-004']
        with self.assertRaises(ValueError):
            projection_receivers(self.manifest)

    def test_component_must_belong_to_reviewed_patch_and_receiver(self):
        self.review['receiver_components'] = {'interior-patch-000': [
            dict(source_node='building-002', projection_components=['floor'], patch_id='patch-000')]}
        with self.assertRaises(ValueError):
            projection_receivers(self.manifest)
        self.review['receiver_components']['interior-patch-000'][0]['source_node'] = 'building-001'
        projection_receivers(self.manifest)
        self.review['receiver_components']['interior-patch-000'][0]['patch_id'] = 'patch-001'
        with self.assertRaises(ValueError):
            projection_receivers(self.manifest)

    def test_derby_legacy_partition_unchanged(self):
        self.assertEqual(projection_receivers({'map': 'Derby'})['patch-003'],
                         ['building-252', 'building-253'])
        self.assertEqual(projection_occluders({'map': 'Derby'}, ['building-252'])['patch-003'],
                         ['building-252'])


if __name__ == '__main__':
    unittest.main()
