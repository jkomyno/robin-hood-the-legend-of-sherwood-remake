"""Working projection edits retain immutable artwork and asset ownership."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from refinement_workspace import (_files, _validated_projection, initialize_working_projection)


class WorkingProjectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.reference = self.root/'reference'
        self.reference.mkdir()
        for name in ('source.png', 'interior.png', 'alpha.png'):
            (self.reference/name).write_bytes(name.encode())
        review = dict(version=1, reviewed=True, patch_id='patch-000', reviewer='reviewer',
                      evidence='Reviewed room.', receiver_nodes=['building-001'],
                      retained_occluder_nodes=['building-002'], partial_cover_nodes=[],
                      exclude_occluder_components=[], receiver_components={},
                      source_sha256=hashlib.sha256(b'interior.png').hexdigest(),
                      alpha_sha256=hashlib.sha256(b'alpha.png').hexdigest())
        manifest = dict(version=1, map='Fixture', sources=dict(exterior='source.png', interior='interior.png'),
                        patches=[dict(id='patch-000', graphic=dict(alpha='alpha.png'))],
                        projection_reviews={'patch-000': review})
        (self.reference/'layers.json').write_text(json.dumps(manifest))
        self.config = dict(projection_manifest=str(self.reference/'layers.json'),
                           source_path=str(self.reference/'source.png'), part_ids=['building-001'],
                           reference_files=_files(self.reference))
        (self.root/'workspace.json').write_text(json.dumps(self.config))
        self.frozen = _files(self.reference)

    def migrate(self):
        destination = Path(initialize_working_projection(self.root))
        config = json.loads((self.root/'workspace.json').read_text())
        return destination, config

    def test_migration_and_owned_component_edit_keep_reference_identical(self):
        destination, config = self.migrate()
        manifest = json.loads(destination.read_text())
        self.assertEqual(manifest['sources']['interior'], str(self.reference/'interior.png'))
        manifest['projection_reviews']['patch-000']['receiver_components'] = {
            'interior-patch-000': [dict(source_node='building-001', projection_components=['floor'], patch_id='patch-000')]}
        destination.write_text(json.dumps(manifest))
        _validated_projection(config)
        self.assertEqual(_files(self.reference), self.frozen)
        self.assertEqual(initialize_working_projection(self.root), str(destination))

    def test_changed_state_inventory_or_foreign_assignment_is_rejected(self):
        destination, config = self.migrate()
        original = json.loads(destination.read_text())
        changed = json.loads(json.dumps(original))
        changed['patches'][0]['sight_after'] = ['building-001']
        destination.write_text(json.dumps(changed))
        with self.assertRaises(ValueError):
            _validated_projection(config)
        original['projection_reviews']['patch-000']['retained_occluder_nodes'] = []
        destination.write_text(json.dumps(original))
        with self.assertRaises(ValueError):
            _validated_projection(config)


if __name__ == '__main__':
    unittest.main()
