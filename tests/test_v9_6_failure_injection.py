"""
S-Class V9.6 Hardening Suite Vector 10: Fault & Failure Injection Framework
"""

import unittest
import os
import tempfile
import shutil
from runtime import FileLock
from spec_compiler import SpecificationCompiler


class TestV96FailureInjection(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_failure_injection_corrupt_lock_file_recovery(self):
        """Failure Injection 1: Corrupt/non-digit lock file is safely recovered without blocking subsequent acquire."""
        state_dir = os.path.join(self.test_dir, ".agents")
        os.makedirs(state_dir, exist_ok=True)
        lock_path = os.path.join(state_dir, ".pipeline_version.lock")

        # Inject corrupt non-digit content into lock file
        with open(lock_path, "w", encoding="utf-8") as f:
            f.write("CORRUPT_LOCK_DATA_INVALID_PID")

        # FileLock must recover the corrupt lock file after stale inspection delay
        with FileLock(lock_path, timeout=2.0, stale_ttl=0.1):
            self.assertTrue(os.path.exists(lock_path))

    def test_failure_injection_missing_pipeline_key(self):
        """Failure Injection 2: Saving malformed pipeline dict missing key components fails closed cleanly."""
        malformed_pipeline = {
            "behavior_graph": {},
            # Missing requirement_graph, hld_design
        }
        with self.assertRaises(KeyError):
            SpecificationCompiler.save_versioned_pipeline_artifact(malformed_pipeline, self.test_dir)


if __name__ == "__main__":
    unittest.main()
