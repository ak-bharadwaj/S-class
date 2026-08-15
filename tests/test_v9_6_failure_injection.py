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
        """System Outcome Chain 1: Corrupted pipeline JSON forces ArtifactGovernor BLOCK, preserves previous immutable artifact v1.json, and prevents downstream FSM transition."""
        from runtime import initialize_state, get_state
        from spec_compiler import SpecificationCompiler
        from artifact_governor import ArtifactGovernor

        initialize_state(self.test_dir, goal="Test Goal")
        state_dir = os.path.join(self.test_dir, ".agents")

        # 1. Create and persist valid v1 pipeline artifact
        dummy_pipe = {
            "version": 1,
            "behavior_graph": {"nodes": {}},
            "requirement_graph": {"nodes": {}},
            "hld_design": {"adrs": []},
            "debate_result": {"accepted_adrs": []},
            "lld_components": [],
            "tasks": [],
            "blocked": False
        }
        v1_path = SpecificationCompiler.save_versioned_pipeline_artifact(dummy_pipe, self.test_dir)
        self.assertTrue(os.path.exists(v1_path), "v1.json must be saved cleanly")

        # 2. Inject corruption into current working pipeline file
        pipeline_file = os.path.join(state_dir, "v7_refinement_pipeline.json")
        with open(pipeline_file, "w", encoding="utf-8") as f:
            f.write('{"behavior_graph": {"nodes": { TRUNCATED_CORRUPT_JSON')

        # 3. Governor audit MUST detect corruption and BLOCK transition to CODING
        gov_res = ArtifactGovernor.enforce_fsm_transition(
            current_phase="DESIGN",
            proposed_event="spec_approved",
            target_phase="CODING",
            workspace_dir=self.test_dir
        )

        # Full outcome chain assertions:
        self.assertTrue(gov_res.is_blocked, "ArtifactGovernor MUST evaluate is_blocked=True on corrupted pipeline")
        self.assertTrue(os.path.exists(v1_path), "Previous immutable backup v1.json MUST remain preserved intact")
        state = get_state(self.test_dir)
        self.assertEqual(state.currentPhase, "TRIAGE", "FSM current state MUST remain in safe current phase without state mutation")

    def test_system_outcome_tampered_approval_signature_fails_closed(self):
        """System Outcome Chain 2: Tampered HMAC approval signature forces verification failure, governance BLOCK, and blocks downstream CODING transition."""
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

        # 1. Direct record signature check evaluates to False
        self.assertFalse(tampered_record.is_valid("secret_key_123"), "Tampered signature MUST fail validation")

        # 2. FSM transition to CODING must be BLOCKED
        gov_res = ArtifactGovernor.enforce_fsm_transition(
            current_phase="DESIGN",
            proposed_event="spec_approved",
            target_phase="CODING",
            workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked, "Unapproved/tampered artifact MUST block transition to CODING")


if __name__ == "__main__":
    unittest.main()
