import unittest
import numpy as np
from complete_hall_revealed_fallback import fallback_selection

class SecondaryFallbackTests(unittest.TestCase):
    def test_existing_but_unsupported_primary_uses_secondary(self):
        self.assertEqual(fallback_selection([0],[False],[True]).tolist(),[True])
    def test_supported_primary_is_kept(self):
        self.assertEqual(fallback_selection([0,2],[True,True],[True,True]).tolist(),[False,False])
    def test_source_and_existing_completion_are_never_replaced(self):
        self.assertEqual(fallback_selection([1,2],[False,False],[True,True]).tolist(),[False,False])
    def test_secondary_must_be_fully_supported(self):
        self.assertEqual(fallback_selection([0],[False],[False]).tolist(),[False])
if __name__=='__main__':unittest.main()
