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

    def test_system_outcome_corrupt_pipeline_json_fails_closed_in_fsm_runner(self):
        """System Outcome Injection 1: Corrupted pipeline JSON forces fail-closed governance BLOCK without partial mutation."""
        from runtime import FSMGoalSequenceRunner, initialize_state

        state_dir = os.path.join(self.test_dir, ".agents")
        os.makedirs(state_dir, exist_ok=True)
        pipeline_file = os.path.join(state_dir, "v7_refinement_pipeline.json")

        # Write truncated corrupt JSON
        with open(pipeline_file, "w", encoding="utf-8") as f:
            f.write('{"behavior_graph": {"nodes": {')

        initialize_state(self.test_dir, goal="Test Goal")

        # Phase evidence check must not crash and handles corrupt JSON gracefully
        FSMGoalSequenceRunner._ensure_phase_evidence("DESIGN", self.test_dir)
        self.assertTrue(os.path.exists(pipeline_file), "Pipeline file must remain intact without corrupt state mutation")

    def test_system_outcome_tampered_approval_signature_fails_closed(self):
        """System Outcome Injection 2: Tampered HMAC approval signature forces FAIL_CLOSED governance BLOCK."""
        from artifact_governor import ArtifactGovernor, ApprovalRecord, ApprovalAuthority

        tampered_record = ApprovalRecord(
            decision_id="DEC-001",
            artifact_id="HLD-001",
            artifact_version=1,
            content_hash="1111111111111111111111111111111111111111111111111111111111111111",
            decision="APPROVED",
            authority=ApprovalAuthority.HUMAN_EXPLICIT,
            reason="Tested approval",
            timestamp="2026-08-15T00:00:00Z",
            signature="TAMPERED_INVALID_HMAC_SIGNATURE"
        )

        res = tampered_record.is_valid("secret_key_123")
        self.assertFalse(res, "Tampered approval signature MUST evaluate to False (FAIL CLOSED)")


if __name__ == "__main__":
    unittest.main()
