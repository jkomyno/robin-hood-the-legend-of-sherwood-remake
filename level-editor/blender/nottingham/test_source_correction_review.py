import json
from pathlib import Path
import tempfile
import unittest
from build_source_correction_review import enrich, sha


class SourceCorrectionEvidence(unittest.TestCase):
    def fixture(self, root):
        (root/'modified').mkdir();(root/'inspection').mkdir()
        (root/'model.blend').write_bytes(b'approved candidate')
        (root/'modified/views.json').write_text(json.dumps({'object_names':['owned'], 'render_object_names':None}))
        (root/'candidate.json').write_text(json.dumps({'stored_material_evidence':'inspection/audit.json'}))
        files=['materials.png',*(f'view-{i}.png' for i in range(8))]
        for name in files:(root/'inspection'/name).write_bytes(name.encode())
        audit={'asset_id':'example','status':'STRUCTURAL-PASS','problems':[],
               'model_sha256':sha(root/'model.blend'),'frame_manifest_sha256':sha(root/'modified/views.json'),
               'render_object_names':['owned'],'artifact_sha256':{n:sha(root/'inspection'/n) for n in files}}
        (root/'inspection/audit.json').write_text(json.dumps(audit))
        return {'id':'example','workspace':str(root),'notes':[]}

    def test_exact_evidence_added_without_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);item=enrich(self.fixture(root))
            self.assertEqual(item['stored_material_textured'],str(root/'inspection/materials.png'))
            self.assertNotIn('user_approval',item)
            self.assertIn('new decision',item['notes'][0])

    def test_changed_image_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);item=self.fixture(root)
            (root/'inspection/view-7.png').write_bytes(b'changed')
            with self.assertRaises(ValueError):enrich(item)

    def test_foreign_scope_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);item=self.fixture(root)
            p=root/'inspection/audit.json';audit=json.loads(p.read_text());audit['render_object_names']=['foreign'];p.write_text(json.dumps(audit))
            with self.assertRaises(ValueError):enrich(item)


if __name__=='__main__':unittest.main()
