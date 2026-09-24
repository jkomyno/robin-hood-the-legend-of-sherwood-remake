"""Only complete, current saved-material audits can skip batch rendering."""
import json
from pathlib import Path
import tempfile
import unittest
from generation_material_audits import matches, sha

class MaterialAuditBindings(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)
        frame=self.p/'views.json';frame.write_text(json.dumps({'object_names':['owned']}))
        self.row={'asset_id':'asset','saved_state_model_sha256':'model','frame_manifest':str(frame),'frame_manifest_sha256':sha(frame)}
        artifacts={}
        for name in ['materials.png',*[f'view-{i}.png'for i in range(8)]]:
            path=self.p/name;path.write_bytes(name.encode());artifacts[name]=sha(path)
        self.audit={'status':'STRUCTURAL-PASS','problems':[],'asset_id':'asset','model_sha256':'model',
                    'frame_manifest_sha256':sha(frame),'render_object_names':['owned'],'artifact_sha256':artifacts}
        self.path=self.p/'audit.json';self.save()
    def save(self):self.path.write_text(json.dumps(self.audit))
    def test_complete_exact_audit_matches(self):self.assertTrue(matches(self.path,self.row))
    def test_wrong_model_or_scope_never_reused(self):
        for field,value in [('model_sha256','stale'),('render_object_names',['neighbor']),('status','FAIL')]:
            with self.subTest(field=field):
                original=self.audit[field];self.audit[field]=value;self.save();self.assertFalse(matches(self.path,self.row));self.audit[field]=original
    def test_changed_image_rejected(self):
        (self.p/'view-3.png').write_bytes(b'changed');self.assertFalse(matches(self.path,self.row))
    def test_missing_view_rejected(self):
        del self.audit['artifact_sha256']['view-7.png'];self.save();self.assertFalse(matches(self.path,self.row))

if __name__=='__main__':unittest.main()
