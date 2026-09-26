import json
from pathlib import Path
import re
import tempfile
import unittest
from copy_game_data import BONUS_SPRITES, EDITOR, copy_game_data


class CopyGameDataTests(unittest.TestCase):
    def test_bonus_mapping_matches_preview(self):
        source = (EDITOR / 'app/src/sprite-profiles.ts').read_text()
        table = source.split('export const BONUS_SPRITES:')[1].split('];')[0]
        self.assertEqual(BONUS_SPRITES, re.findall(r'\["([^"]+)", "([^"]+)"\]', table))

    def test_only_mission_poses_with_fallback_and_stale_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / 'source', root / 'library/game-data'
            def write(relative, data):
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data))
            def bank(relative, names, actions):
                profiles = []
                for name in names:
                    rows = []
                    for action in actions:
                        for direction in range(16):
                            path = f'action_{action}/dir_{direction:02}'
                            rows.append({'action_id': action, 'direction': direction, 'path': path,
                                         'frames': [{'file': '00.png'}, {'file': '01.png'}]})
                            for frame in ('00', '01'):
                                write(f'{relative}/{name}/{path}/{frame}.png', frame)
                    profiles.append({'name': name, 'rows': rows})
                write(f'{relative}/manifest.json', {'profiles': profiles, 'pixel_format': 'rgba'})

            write('Data/Levels/York.rhp.json', {})
            mission = {'header': {'ambiance': 4},
                       'soldiers': [{'profile_number': 0, 'action': 99}],
                       'pcs_to_rescue': [{'profile_index': 0, 'action': 0}],
                       'civilians': [{'profile_number': 0, 'action': 5}],
                       'targets': [{'filename': 'Gate', 'profile_name': 'Open', 'action': 8}],
                       'mobile_elements': [{'sprites': [
                           {'active': False, 'sprite': {'frame_profile_name': 'Unused'}},
                           {'sprite': {'frame_profile_name': 'Gate', 'profile_name': 'Open'}}]}],
                       'bonuses': [{'bonus_type': 0, 'quantity': 2}],
                       'scrolls': [{'action': 190}]}
            write('Data/Levels/Mission.rhm.json', mission)
            write('Data/Levels/Mission.scb.json', {})
            write('Data/Configuration/profile.cpf.json', {
                'soldier_order': ['guard'], 'character_order': ['guard'], 'civilian_order': ['guard'],
                **{category: {'guard': {'filename': 'bank', 'profile_name': 'Guard One'}}
                   for category in ('soldiers', 'characters', 'civilians')}})
            bank('Data/Characters/Bank.rhs.d', ['Guard One', 'Unused'], [0, 3, 5, 42])
            bank('Data/Characters/Unused.rhs.d', ['Unused'], [0])
            bank('Data/Animations/Day/Gate.rhs.d', ['Open', 'Unused'], [0, 8, 9])
            bank('Data/Animations/Fog/Gate.rhs.d', ['Open', 'Unused'], [0, 8])
            bank('Data/Characters/BONUS_Arrows.rhs.d', ['BONUS Fleches', 'Unused'], [190, 191])
            bank('Data/Characters/BONUS_Parchment.rhs.d', ['BONUS Parchemin', 'Unused'], [190, 191])
            output.mkdir(parents=True)
            (output / 'old').mkdir()
            (output / 'old/unused.png').write_text('old generated frame')
            (output / 'notes.txt').write_text('keep user file')
            (output / 'index.json').write_text(json.dumps({'version': 1, 'files': ['old/unused.png']}))
            count = copy_game_data(source, output)
            self.assertEqual(count, 3 + 4 + 16 * (3 + 2 + 1 + 1))
            index = json.loads((output / 'index.json').read_text())
            self.assertEqual(len(index['files']), count)
            self.assertFalse(any('01.png' in p or 'Unused' in p or '/Fog/' in p or 'action_42' in p
                                 or '.scb.' in p for p in index['files']))
            self.assertFalse((output / 'old').exists())
            self.assertTrue((output / 'notes.txt').exists())
            manifest = json.loads((output / 'Data/Characters/Bank.rhs.d/manifest.json').read_text())
            self.assertEqual(len(manifest['profiles']), 1)
            rows = manifest['profiles'][0]['rows']
            self.assertEqual({row['action_id'] for row in rows}, {0, 3, 5})
            self.assertTrue(all(len(row['frames']) == 1 for row in rows))
            # Pruned manifests must resolve directly even though just one profile remains.
            for relative in index['files']:
                if relative.endswith('/manifest.json'):
                    directory = output / relative
                    manifest = json.loads(directory.read_text())
                    for profile in manifest['profiles']:
                        for row in profile['rows']:
                            self.assertTrue((directory.parent / row['path'] / row['frames'][0]['file']).is_file())
            self.assertEqual(copy_game_data(source, output), count)
            # A changed mission removes poses that used to be selected.
            mission['civilians'] = []
            write('Data/Levels/Mission.rhm.json', mission)
            self.assertEqual(copy_game_data(source, output), count - 16)
            self.assertFalse((output / 'Data/Characters/Bank.rhs.d/Guard One/action_5').exists())


if __name__ == '__main__':
    unittest.main()
