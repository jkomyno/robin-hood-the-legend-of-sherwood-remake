from pathlib import Path
import tempfile
import unittest
from PIL import Image
from texture_transport import validate_crop

class TransportTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);p=Path(self.tmp.name);self.raw=p/'raw.png';self.content=p/'content.png';self.preserved=p/'preserved.png';im=Image.new('RGBA',(4,6),(10,20,30,255));im.putpixel((1,1),(80,90,100,255));im.save(self.raw);im.crop((0,0,4,4)).save(self.content);Image.new('RGBA',(4,4)).save(self.preserved);self.padding=dict(version=1,kind='bottom-padding',width=4,height=6,content_box=dict(left=0,top=0,width=4,height=4))
 def test_exact_unscaled_crop(self):validate_crop(self.raw,self.content,self.preserved,self.padding)
 def test_reject_changed_crop(self):
  im=Image.open(self.content);im.putpixel((1,1),(90,90,100,255));im.save(self.content)
  with self.assertRaises(ValueError):validate_crop(self.raw,self.content,self.preserved,self.padding)
 def test_reject_rescaling_or_unapproved_offset(self):
  for bad in [dict(self.padding,width=5),dict(self.padding,content_box=dict(left=0,top=1,width=4,height=4)),None]:
   with self.assertRaises(ValueError):validate_crop(self.raw,self.content,self.preserved,bad)
if __name__=='__main__':unittest.main()
