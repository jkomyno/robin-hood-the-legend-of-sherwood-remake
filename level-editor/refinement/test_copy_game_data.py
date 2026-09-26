import json
from pathlib import Path
import tempfile
import unittest
from copy_game_data import copy_game_data


class CopyGameDataTests(unittest.TestCase):
    def test_preview_files_and_multi_profile_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / 'source', root / 'library/game-data'
            def write(relative, data):
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data))
            write('Data/Levels/York.rhp.json', {})
            write('Data/Levels/Mission.rhm.json', {})
            write('Data/Levels/Mission.scb.json', {})
            write('Data/Configuration/profile.cpf.json', {})
            for category in ('Characters', 'Animations/Day'):
                bank = f'Data/{category}/Bank.rhs.d'
                profiles = []
                for name in ('Guard One', 'Guard_Two'):
                    profiles.append({'name': name, 'rows': [{'path': 'Idle/dir_00',
                        'frames': [{'file': '00.png'}, {'file': '01.png'}]}]})
                    write(f'{bank}/{name}/Idle/dir_00/00.png', 'first')
                    write(f'{bank}/{name}/Idle/dir_00/01.png', 'second')
                write(f'{bank}/manifest.json', {'profiles': profiles})
            self.assertEqual(copy_game_data(source, output), 9)
            index = json.loads((output / 'index.json').read_text())
            self.assertEqual(index['version'], 1)
            self.assertEqual(len(index['files']), 9)
            self.assertFalse(any('01.png' in p or '.scb.' in p for p in index['files']))
            for relative in index['files']:
                self.assertEqual((source / relative).read_bytes(), (output / relative).read_bytes())
            self.assertEqual(copy_game_data(source, output), 9)


if __name__ == '__main__':
    unittest.main()
