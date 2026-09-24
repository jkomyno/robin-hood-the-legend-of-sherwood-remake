import json,tempfile,unittest
from pathlib import Path
from PIL import Image
from texture_experiment_paths import reconciliation_reference
class TransportReference(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.p=Path(self.temp.name)
  raw=Image.new('RGBA',(4,4),(11,22,33,255));raw.putpixel((1,1),(45,67,89,255));raw.save(self.p/'generated-raw.png')
  raw.crop((0,0,4,3)).save(self.p/'generated-content.png');raw.crop((0,0,4,3)).save(self.p/'generated-preserved.png')
  (self.p/'generation.json').write_text(json.dumps({'transportPadding':{'version':1,'kind':'bottom-padding','width':4,'height':4,'content_box':{'left':0,'top':0,'width':4,'height':3}}}))
 def tearDown(self):self.temp.cleanup()
 def test_exact_unscaled_content(self):self.assertEqual(reconciliation_reference(self.p),self.p/'generated-content.png')
 def test_modified_content_rejected(self):
  Image.new('RGBA',(4,3),(0,0,0,255)).save(self.p/'generated-content.png')
  with self.assertRaises(ValueError):reconciliation_reference(self.p)
 def test_unproven_dimensions_rejected(self):
  (self.p/'generation.json').write_text('{}')
  with self.assertRaises(ValueError):reconciliation_reference(self.p)
 def test_matching_raw_no_crop(self):
  Image.open(self.p/'generated-raw.png').save(self.p/'generated-preserved.png')
  self.assertEqual(reconciliation_reference(self.p),self.p/'generated-raw.png')
if __name__=='__main__':unittest.main()
