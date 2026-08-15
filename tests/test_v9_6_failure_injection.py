"""
S-Class V9.6 Hardening Suite Vector 10: Fault & Failure Injection Framework
"""

import unittest
import os
import json
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
        """System Outcome Chain 1: Corrupted pipeline JSON forces ArtifactGovernor BLOCK, preserves previous immutable artifact v1.json, and maintains EXACT pre/post FSM state snapshot equality."""
        from dataclasses import asdict
        from runtime import initialize_state, get_state
        from spec_compiler import SpecificationCompiler
        from artifact_governor import ArtifactGovernor

        initialize_state(self.test_dir, goal="Test Goal")
        state_dir = os.path.join(self.test_dir, ".agents")

        # Snapshot EXACT initial FSM state before any operation
        before_state = asdict(get_state(self.test_dir))

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

        # Snapshot EXACT FSM state after governance audit
        after_state = asdict(get_state(self.test_dir))

        # Full outcome chain assertions:
        self.assertTrue(gov_res.is_blocked, "ArtifactGovernor MUST evaluate is_blocked=True on corrupted pipeline")
        self.assertTrue(os.path.exists(v1_path), "Previous immutable backup v1.json MUST remain preserved intact")
        self.assertEqual(before_state, after_state, "FSM state snapshot MUST remain 100% strictly identical (zero state mutation)")

    def test_system_outcome_tampered_approval_signature_fails_closed(self):
        """System Outcome Chain 2: Persisted tampered HMAC approval record fails verification on disk, forces governance BLOCK, and leaves FSM state un-mutated."""
        from dataclasses import asdict
        from runtime import initialize_state, get_state
        from artifact_governor import ArtifactGovernor, ApprovalRecord, ApprovalAuthority

        initialize_state(self.test_dir, goal="Test Goal")
        before_state = asdict(get_state(self.test_dir))

        state_dir = os.path.join(self.test_dir, ".agents")
        os.makedirs(state_dir, exist_ok=True)
        approvals_file = os.path.join(state_dir, "approvals.json")

        tampered_record = ApprovalRecord(
            decision_id="ADR-SEC-001",
            artifact_id="HLD-001",
            artifact_version=1,
            content_hash="1111111111111111111111111111111111111111111111111111111111111111",
            decision="APPROVED",
            authority=ApprovalAuthority.HUMAN_EXPLICIT,
            reason="Tested approval",
            timestamp="2026-08-15T00:00:00Z",
            signature="TAMPERED_INVALID_HMAC_SIGNATURE"
        )

        # 1. Write pipeline containing PROPOSED HIGH_RISK ADR needing approval in PRODUCTION mode
        pipeline_file = os.path.join(state_dir, "v7_refinement_pipeline.json")
        pipe_data = {
            "version": 1,
            "blocked": True,
            "execution_mode": "PRODUCTION",
            "hld_governance": {
                "is_blocked": True,
                "blocking_reasons": ["ADR-SEC-001 is PROPOSED without valid canonical ApprovalRecord"]
            },
            "hld_design": {
                "adrs": [
                    {
                        "id": "ADR-SEC-001",
                        "title": "Zero Trust Token Encryption",
                        "status": "PROPOSED",
                        "epistemic_status": "proposed",
                        "risk_class": "HIGH_RISK",
                        "decision": "Use AES-256-GCM"
                    }
                ]
            }
        }
        with open(pipeline_file, "w", encoding="utf-8") as f:
            json.dump(pipe_data, f, indent=2)

        # 2. Persist tampered approval record directly into disk storage
        with open(approvals_file, "w", encoding="utf-8") as f:
            json.dump({"approval_records": [tampered_record.to_dict()]}, f, indent=2)

        # 3. Verify Governor rejects the persisted record during disk audit
        loaded_verified = ArtifactGovernor._load_verified_approval_records(self.test_dir)
        self.assertNotIn("ADR-SEC-001", loaded_verified, "Tampered approval record on disk MUST be rejected by Governor audit")

        # 4. FSM transition to CODING must be BLOCKED
        gov_res = ArtifactGovernor.enforce_fsm_transition(
            current_phase="DESIGN",
            proposed_event="spec_approved",
            target_phase="CODING",
            workspace_dir=self.test_dir
        )
        after_state = asdict(get_state(self.test_dir))

        self.assertTrue(gov_res.is_blocked, "Unapproved/tampered artifact on disk MUST block transition to CODING")
        self.assertEqual(before_state, after_state, "FSM state snapshot MUST remain strictly identical on governance block")


if __name__ == "__main__":
    unittest.main()
