import json
from pathlib import Path
import tempfile
import unittest

from evidence_io import digest, read_json, record_recipe, sha, write_json


class EvidenceIoTests(unittest.TestCase):
    def test_json_round_trip_and_canonical_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_json(Path(directory) / 'record.json', {'b': 1, 'a': [2]})
            self.assertEqual(read_json(path), {'a': [2], 'b': 1})
            self.assertEqual(digest({'b': 1, 'a': [2]}), digest({'a': [2], 'b': 1}))
            self.assertEqual(sha(path), sha(path))
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_recipe_copy_is_relative_and_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / 'workspace'
            workspace.mkdir()
            recipe = root / 'refine_example.py'
            recipe.write_text('print(1)\n')
            record = record_recipe(workspace, recipe)
            self.assertEqual(record['recipe'], 'recipe/refine_example.py')
            self.assertEqual(record['recipe_sha256'], sha(recipe))
            self.assertEqual(record_recipe(workspace, recipe), record)
            recipe.write_text('print(2)\n')
            with self.assertRaisesRegex(ValueError, 'different'):
                record_recipe(workspace, recipe)
            json.dumps(record)


if __name__ == '__main__':
    unittest.main()
