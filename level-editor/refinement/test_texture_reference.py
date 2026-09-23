import hashlib
from pathlib import Path
import tempfile
import unittest
from build_texture_gallery import validate_reconciliation_reference

class ReferenceTests(unittest.TestCase):
    def test_legacy_without_reference(self):
        validate_reconciliation_reference({})

    def test_reference_must_remain_hash_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'raw.png'; p.write_bytes(b'original')
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            record={'reconciliation_reference':str(p),'reconciliation_reference_sha256':digest,'evidence_sha256':{str(p):digest}}
            validate_reconciliation_reference(record)
            p.write_bytes(b'changed')
            with self.assertRaises(ValueError): validate_reconciliation_reference(record)
            p.unlink()
            with self.assertRaises(ValueError): validate_reconciliation_reference(record)

    def test_missing_guard_or_hash_rejected(self):
        with self.assertRaises(ValueError):
            validate_reconciliation_reference({'reconciliation_reference':'raw.png'})
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'raw.png'; p.write_bytes(b'original')
            with self.assertRaises(ValueError):
                validate_reconciliation_reference({'reconciliation_reference':str(p),'reconciliation_reference_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})

if __name__=='__main__': unittest.main()

class PlanarBakeTests(unittest.TestCase):
    def test_planar_guards_require_uv_source_and_frozen_preparation(self):
        import json
        from build_texture_gallery import validate_planar_bake
        from review_evidence import sha
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);(p/'frames').mkdir();(p/'frames/views.json').write_text('{}')
            (p/'views.json').write_text(json.dumps({'reviewed_packet':str(p/'frames')}))
            (p/'preparation.json').write_text(json.dumps({'files':{'views.json':sha(p/'views.json')}}))
            record={'projection_kind':'planar-atlas','uv_verified':True,'protected_changes':0,
                    'preparation_sha256':sha(p/'preparation.json'),'frame_manifest_sha256':sha(p/'frames/views.json')}
            validate_planar_bake(p,record)
            with self.assertRaises(ValueError):validate_planar_bake(p,{**record,'uv_verified':False})
            with self.assertRaises(ValueError):validate_planar_bake(p,{**record,'protected_changes':1})
            (p/'views.json').write_text('{}')
            with self.assertRaises(ValueError):validate_planar_bake(p,record)
