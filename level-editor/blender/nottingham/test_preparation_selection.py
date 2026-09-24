import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_ready_textures import selected_paths

class SelectionTest(unittest.TestCase):
    def test_explicit_revision_survives_default_change(self):
        rows=[{'asset_id':'house','experiment':'fresh-source33','normalized_manifest':'source33/manifest.json','status':'ready'}]
        self.assertEqual(selected_paths('house',rows,Path('old/manifest.json'),Path('old')), (Path('source33/manifest.json'),Path('fresh-source33'),True))
        rows[0]['status']='failed'
        self.assertEqual(selected_paths('house',rows,Path('old'),Path('old'))[1],Path('fresh-source33'))
    def test_missing_or_ambiguous_authorization_fails(self):
        row={'asset_id':'house','experiment':'fresh'}
        with self.assertRaises(ValueError):selected_paths('house',[row],Path('old'),Path('old'))
        with self.assertRaises(ValueError):selected_paths('house',[row,row],Path('old'),Path('old'))
    def test_unselected_uses_default(self):
        self.assertEqual(selected_paths('house',[],Path('m'),Path('e')),(Path('m'),Path('e'),False))

if __name__=='__main__':unittest.main()
