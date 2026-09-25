"""Explicit state role and reviewed packet binding regression tests."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from texture_state_roles import partition_texture_states, validate_texture_state_role_evidence


class StateRoles(unittest.TestCase):
    def fixture(self, root):
        children = []
        records = []
        for role in ('revealed', 'initial', 'applied'):
            view = root / (role + '.json')
            view.write_text(json.dumps({'reviewed_packet': str(root / role), 'source_sha256': role}))
            children.append({'id': role, 'asset_id': 'prison', 'review_manifest': str(view), 'object_names': [role]})
            if role != 'revealed':
                records.append({'path': str(root / role), 'source_sha256': role, 'object_names': [role]})
        states = root / 'states.json'
        states.write_text(json.dumps({'asset_id': 'prison', 'states': records}))
        return {'asset_id': 'prison', 'texture_states': children,
                'texture_state_roles': {'revealed': 'map-reveal', 'initial': 'standalone-initial', 'applied': 'standalone-applied'},
                'texture_state_role_evidence': {'states_json': str(states), 'states_sha256': hashlib.sha256(states.read_bytes()).hexdigest()}}

    def test_existing_single_reveal(self):
        child = {'id': 'revealed'}
        self.assertEqual(partition_texture_states({'texture_states': [child]}), ([child], {}))

    def test_three_states_and_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            item = self.fixture(Path(directory))
            appearances, endpoints = partition_texture_states(item)
            self.assertEqual([c['id'] for c in appearances], ['revealed'])
            self.assertEqual(set(endpoints), {'initial', 'applied'})
            validate_texture_state_role_evidence(item)
            for mutate in ('roles', 'duplicate', 'parent', 'hash', 'inventory', 'reuse'):
                bad = copy.deepcopy(item)
                if mutate == 'roles': del bad['texture_state_roles']
                elif mutate == 'duplicate': bad['texture_states'][2]['id'] = 'initial'
                elif mutate == 'parent': bad['texture_states'][1]['asset_id'] = 'other'
                elif mutate == 'hash': bad['texture_state_role_evidence']['states_sha256'] = 'wrong'
                elif mutate == 'inventory': bad['texture_states'][1]['object_names'] = ['other']
                elif mutate == 'reuse': bad['texture_states'][2]['review_manifest'] = bad['texture_states'][1]['review_manifest']
                with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                    validate_texture_state_role_evidence(bad)


if __name__ == '__main__': unittest.main()
