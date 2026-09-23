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
