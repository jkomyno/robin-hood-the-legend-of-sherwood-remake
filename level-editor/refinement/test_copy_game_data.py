import json
from pathlib import Path
import re
import tempfile
import unittest
from io import BytesIO
from PIL import Image
from game_data_atlas import pack_atlas
from copy_game_data import BONUS_SPRITES, EDITOR, copy_game_data


class CopyGameDataTests(unittest.TestCase):
    def test_atlas_deduplicates_identical_pixels_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            a, b = Path(temporary) / 'a.png', Path(temporary) / 'b.png'
            Image.new('RGBA', (5, 7), (20, 40, 60, 128)).save(a)
            b.write_bytes(a.read_bytes())
            payload, rectangles = pack_atlas([a, b])
            self.assertEqual(rectangles[a], rectangles[b])
            self.assertEqual(pack_atlas([a, b])[0], payload)
            with Image.open(BytesIO(payload)) as atlas:
                self.assertEqual(atlas.format, 'WEBP')
                self.assertEqual(atlas.size, (7, 9))

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
                                target = source / f'{relative}/{name}/{path}/{frame}.png'
                                target.parent.mkdir(parents=True, exist_ok=True)
                                image = Image.new('RGBA', (direction + 1, 3), (action, direction, int(frame), 127))
                                image.putpixel((0, 0), (55, 66, 77, 0))
                                image.save(target)
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
                **{category: {'guard': {'filename': 'Bank', 'profile_name': 'Guard One'}}
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
            self.assertEqual(count, 3 + 4 * 2)
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
            # Atlas crops must reproduce every retained source pixel, including hidden RGB.
            for relative in index['files']:
                if relative.endswith('/manifest.json'):
                    directory = output / relative
                    manifest = json.loads(directory.read_text())
                    for profile in manifest['profiles']:
                        for row in profile['rows']:
                            frame = row['frames'][0]
                            with Image.open(directory.parent / manifest['atlas']) as atlas:
                                x, y, width, height = frame['rect']
                                crop = atlas.crop((x, y, x + width, y + height))
                            original = source / directory.parent.relative_to(output) / profile['name'] / f'action_{row["action_id"]}/dir_{row["direction"]:02}/00.png'
                            with Image.open(original) as image:
                                self.assertEqual(crop.tobytes(), image.convert('RGBA').tobytes())
                                self.assertEqual(crop.size, image.size)
            self.assertEqual(copy_game_data(source, output), count)
            # A changed mission removes poses that used to be selected.
            mission['civilians'] = []
            write('Data/Levels/Mission.rhm.json', mission)
            self.assertEqual(copy_game_data(source, output), count)
            refreshed = json.loads((output / 'Data/Characters/Bank.rhs.d/manifest.json').read_text())
            self.assertEqual({r['action_id'] for r in refreshed['profiles'][0]['rows']}, {0, 3})
            self.assertFalse(list(output.rglob('*.png')))
            self.assertEqual(len(list(output.rglob('atlas.webp'))), 4)

    def test_authorable_characters_absent_from_missions_have_complete_canonical_idle_banks(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / 'source', Path(temporary) / 'output'
            def write(relative, data):
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data))
            profiles = {
                'character_order': ['hero'], 'soldier_order': ['guard'],
                'characters': {'hero': {'filename': 'Hero', 'profile_name': 'Hero pose'}},
                'soldiers': {'guard': {'filename': 'sherif', 'profile_name': 'Guard pose'}},
            }
            write('Data/Configuration/profile.cpf.json', profiles)
            write('Data/Levels/Test.rhp.json', {})
            write('Data/Levels/Test.rhm.json', {'header': {'ambiance': 1}})
            for filename, name, action in [('Hero', 'Hero pose', 3), ('Sherif', 'Guard pose', 0)]:
                bank = source / f'Data/Characters/{filename}.rhs.d'
                bank.mkdir(parents=True)
                Image.new('RGBA', (4, 5), (7, 8, 9, 255)).save(bank / 'idle.png')
                write(f'Data/Characters/{filename}.rhs.d/manifest.json', {'profiles': [{
                    'name': name, 'rows': [
                        {'action_id': action, 'direction': direction, 'path': '.',
                         'frames': [{'file': 'idle.png', 'offset_x': -2, 'offset_y': -4}]}
                        for direction in range(16)]}]})
            self.assertEqual(copy_game_data(source, output), 7)
            self.assertEqual(json.loads((output / 'Data/Configuration/profile.cpf.json').read_text()), profiles)
            for filename, name, action in [('Hero', 'Hero pose', 3), ('sherif', 'Guard pose', 0)]:
                bank = output / f'Data/Characters/{filename}.rhs.d'
                manifest = json.loads((bank / 'manifest.json').read_text())
                self.assertEqual(manifest['profiles'][0]['name'], name)
                rows = manifest['profiles'][0]['rows']
                self.assertEqual({row['direction'] for row in rows}, set(range(16)))
                self.assertEqual({row['action_id'] for row in rows}, {action})
                self.assertTrue(all(row['frames'][0]['offset_x'] == -2 for row in rows))
                self.assertTrue((bank / manifest['atlas']).is_file())
            # An incomplete chooser sprite is an authoring failure, never silently a marker.
            manifest_path = source / 'Data/Characters/Hero.rhs.d/manifest.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['profiles'][0]['rows'].pop()
            manifest_path.write_text(json.dumps(manifest))
            before = (output / 'index.json').read_bytes()
            with self.assertRaisesRegex(ValueError, 'incomplete idle directions'):
                copy_game_data(source, output)
            self.assertEqual((output / 'index.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
