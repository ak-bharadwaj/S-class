"""
S-Class EOS V9.6 - Comprehensive Full-System Red-Team Audit & Reliability Campaign

Executes adversarial stress testing across all 10 core architectural pillars:
1. Grounding & Anti-Hallucination Isolation
2. Epistemic Fail-Closed Evidence & Provenance Boundaries
3. Requirement Graph Integrity & Collision Rejection
4. End-to-End Architectural Lineage Traceability
5. Evidence-Conditioned Security (403) & Audit Persistence
6. Architecture Debate Epistemic Sufficiency
7. Cryptographic Governance & Tamper Resistance
8. 19-State FSM Control Plane & Illegal Transition Rejection
9. Persistent Inode Locking & Strict Mutual Exclusion
10. Production Mode Simulation Rejection & Version Lineage Immutability
"""

import unittest
import os
import shutil
import tempfile
import time
import json
import math
import concurrent.futures
import threading

from domain_primitives import DomainPrimitiveType, ProvenanceKind, SemanticDomainGraph, DomainNode, DomainEdge, RelationType
from behavior_graph import BehaviorGraph, BehaviorGraphEngine, BehaviorNode, BehaviorNodeType, BehaviorRelationType, EpistemicStatus
from requirement_ir import RequirementGraph, RequirementNode, RequirementKind, NFRCategory, EvidenceItem, normalize_evidence, DuplicateIDConflictError, CircularDependencyError
from hld_compiler import HLDCompiler, HLDDesign, HLDModule, ADRRecord, ValidationStatus, ApprovalStatus
from lld_compiler import LLDCompiler, LLDComponent, LLDComponentType
from task_compiler import TaskCompiler, TaskRecord, TaskCategory
from architecture_debate import (
    ArchitectureDebateEngine,
    EngineeringClaim,
    ArchitecturalAlternative,
    EvidenceQualityRecord,
    EvidenceState,
    DimensionGateResult,
    DecisionRiskProfile,
    DecisionSufficiencyGate,
    DecisionOutcome
)
from artifact_governor import ArtifactGovernor, ApprovalRecord, ApprovalAuthority, FSMTransitionTarget
from runtime import FileLock, initialize_state, get_state, dispatch_event, write_json_atomic
from verifier import EvidenceVerifier


class TestV96FullSystemRedTeam(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sclass_v96_redteam_")
        self.agents_dir = os.path.join(self.test_dir, ".agents")
        os.makedirs(self.agents_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Pillar 1: Grounding & Anti-Hallucination Isolation
    # -------------------------------------------------------------------------
    def test_pillar_1_adversarial_grounding_isolation(self):
        """Pillar 1: Ungrounded entities, ambiguous nouns, and deceptive verbs MUST NOT acquire EXPLICIT status."""
        d_graph = SemanticDomainGraph()
        d_graph.add_node(DomainNode(id="pilot", name="Pilot", primitive_type=DomainPrimitiveType.ACTOR, provenance=ProvenanceKind.EXPLICIT))
        d_graph.add_node(DomainNode(id="aircraft", name="Aircraft", primitive_type=DomainPrimitiveType.ENTITY, provenance=ProvenanceKind.EXPLICIT))

        # Empty prompt forces ungrounded fallback query generation
        b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, "")

        # Proposed query nodes must have PROPOSED status and reduced confidence
        proposed_queries = [n for n in b_graph.nodes.values() if n.epistemic_status == EpistemicStatus.PROPOSED]
        self.assertGreaterEqual(len(proposed_queries), 1)
        for node in proposed_queries:
            self.assertEqual(node.epistemic_status, EpistemicStatus.PROPOSED)
            self.assertEqual(node.provenance, ProvenanceKind.SPECULATIVE)
            self.assertLessEqual(node.confidence, 0.5)

    # -------------------------------------------------------------------------
    # Pillar 2: Epistemic Fail-Closed Evidence & Provenance Boundaries
    # -------------------------------------------------------------------------
    def test_pillar_2_fail_closed_evidence_boundaries(self):
        """Pillar 2: Corrupted evidence quality, invalid provenance, or unsupported objects MUST fail closed (quality=0, provenance=INVALID)."""
        # 1. NaN quality
        item_nan = EvidenceItem(id="EV-NAN", quality=float("nan"))
        self.assertEqual(item_nan.quality, 0.0)
        self.assertEqual(item_nan.provenance, ProvenanceKind.INVALID)

        # 2. Infinite quality
        item_inf = EvidenceItem(id="EV-INF", quality=float("inf"))
        self.assertEqual(item_inf.quality, 0.0)
        self.assertEqual(item_inf.provenance, ProvenanceKind.INVALID)

        # 3. Out-of-bounds quality
        item_oob = EvidenceItem(id="EV-OOB", quality=150.0)
        self.assertEqual(item_oob.quality, 0.0)
        self.assertEqual(item_oob.provenance, ProvenanceKind.INVALID)

        # 4. Corrupted provenance dictionary
        item_prov = EvidenceItem.from_dict({"id": "EV-CORRUPT", "provenance": "completely_fake_provenance"})
        self.assertEqual(item_prov.provenance, ProvenanceKind.INVALID)
        self.assertEqual(item_prov.quality, 0.0)

        # 5. Unsupported object type raises TypeError
        with self.assertRaises(TypeError):
            normalize_evidence(set([1, 2, 3]))

    # -------------------------------------------------------------------------
    # Pillar 3: Requirement Graph Integrity & Collision Rejection
    # -------------------------------------------------------------------------
    def test_pillar_3_requirement_integrity_and_collision_rejection(self):
        """Pillar 3: Rejects duplicate ID collisions with conflicting semantic identity, and prevents circular DAG cycles."""
        r_graph = RequirementGraph()
        r1 = RequirementNode(id="REQ-001", kind=RequirementKind.FUNCTIONAL, statement="Login", actor="user", capability="login", target="session")
        r_graph.add_requirement(r1)

        # Conflicting semantic identity with identical ID -> DuplicateIDConflictError
        r1_conflict = RequirementNode(id="REQ-001", kind=RequirementKind.FUNCTIONAL, statement="Login", actor="admin", capability="login", target="session")
        with self.assertRaises(DuplicateIDConflictError):
            r_graph.add_requirement(r1_conflict)

        # Circular dependency cycle -> CircularDependencyError
        r2 = RequirementNode(id="REQ-002", kind=RequirementKind.FUNCTIONAL, statement="Dashboard", actor="user", capability="view", target="dashboard")
        r_graph.add_requirement(r2)
        r_graph.add_dependency("REQ-002", "REQ-001")

        with self.assertRaises(CircularDependencyError):
            r_graph.add_dependency("REQ-001", "REQ-002")

    # -------------------------------------------------------------------------
    # Pillar 4: End-to-End Architectural Lineage Traceability
    # -------------------------------------------------------------------------
    def test_pillar_4_end_to_end_architectural_lineage(self):
        """Pillar 4: Verifies unbroken upstream lineage from TaskRecord -> LLD -> HLD -> Requirements -> Behavior."""
        b_graph = BehaviorGraph()
        b_graph.add_node(BehaviorNode(
            id="cmd_dispatch", name="DispatchVehicle", behavior_type=BehaviorNodeType.COMMAND,
            actor_id="dispatcher", target_entity_id="vehicle", epistemic_status=EpistemicStatus.EXPLICIT,
            provenance=ProvenanceKind.EXPLICIT, confidence=1.0, evidence_ref="Explicit dispatch command"
        ))

        r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)
        hld_modules = HLDCompiler.compile_hld(r_graph, b_graph)
        lld_components = LLDCompiler.compile_lld(hld_modules, r_graph, b_graph)
        tasks = TaskCompiler.compile_tasks(lld_components, r_graph, b_graph)

        self.assertGreaterEqual(len(tasks), 1)
        for task in tasks:
            self.assertTrue(task.parent_lld.startswith("LLD-") or task.parent_lld != "")
            self.assertTrue(task.parent_hld.startswith("HLD-") or task.parent_hld != "")
            self.assertGreaterEqual(len(task.parent_reqs), 1)
            self.assertGreaterEqual(len(task.parent_behaviors), 1)

    # -------------------------------------------------------------------------
    # Pillar 5: Evidence-Conditioned Security & Audit Criteria
    # -------------------------------------------------------------------------
    def test_pillar_5_evidence_conditioned_security_and_audit(self):
        """Pillar 5: HTTP 403 Forbidden and audit trail assertions MUST be strictly conditioned on grounded evidence."""
        # Case A: Without authorization evidence -> No 403 assertion
        b_graph_no_auth = BehaviorGraph()
        b_graph_no_auth.add_node(BehaviorNode(
            id="cmd_read", name="ReadNews", behavior_type=BehaviorNodeType.COMMAND,
            actor_id="guest", target_entity_id="article", epistemic_status=EpistemicStatus.EXPLICIT,
            provenance=ProvenanceKind.EXPLICIT, confidence=1.0, evidence_ref="Guest reads news"
        ))
        r_graph_no_auth = RequirementGraph.compile_from_behavior_graph(b_graph_no_auth)
        hld_no_auth = HLDCompiler.compile_hld(r_graph_no_auth, b_graph_no_auth)
        lld_no_auth = LLDCompiler.compile_lld(hld_no_auth, r_graph_no_auth, b_graph_no_auth)
        tasks_no_auth = TaskCompiler.compile_tasks(lld_no_auth, r_graph_no_auth, b_graph_no_auth)

        for task in tasks_no_auth:
            for crit in task.verification_criteria:
                self.assertNotIn("403 Forbidden", crit)

        # Case B: With explicit authorization evidence -> 403 assertion generated
        b_graph_auth = BehaviorGraph()
        b_graph_auth.add_node(BehaviorNode(
            id="cmd_override", name="OverrideSafety", behavior_type=BehaviorNodeType.COMMAND,
            actor_id="admin", target_entity_id="engine", epistemic_status=EpistemicStatus.EXPLICIT,
            provenance=ProvenanceKind.EXPLICIT, confidence=1.0, evidence_ref="role:admin override"
        ))
        b_graph_auth.add_edge("admin", BehaviorRelationType.AUTHORIZED_FOR, "cmd_override")
        r_graph_auth = RequirementGraph.compile_from_behavior_graph(b_graph_auth)
        hld_auth = HLDCompiler.compile_hld(r_graph_auth, b_graph_auth)
        lld_auth = LLDCompiler.compile_lld(hld_auth, r_graph_auth, b_graph_auth)
        tasks_auth = TaskCompiler.compile_tasks(lld_auth, r_graph_auth, b_graph_auth)

        found_403 = any(any("403 Forbidden" in crit for crit in t.verification_criteria) for t in tasks_auth)
        self.assertTrue(found_403, "TaskCompiler MUST condition 403 Forbidden on explicit authorization evidence")

    # -------------------------------------------------------------------------
    # Pillar 6: Architecture Debate Epistemic Sufficiency
    # -------------------------------------------------------------------------
    def test_pillar_6_debate_epistemic_sufficiency_gates(self):
        """Pillar 6: Debate Engine MUST reject claims with NO_EVIDENCE and ungrounded alternatives."""
        ev_record = EvidenceQualityRecord("EV-NONE", EvidenceState.NO_EVIDENCE, "NO_EVIDENCE", "", 0.0, 0.0, 0.0, 0.0)
        claim = EngineeringClaim("CLAIM-1", "ADR-1", "Use Redis", "Reason", [], [], [], [], [], [], [ev_record], "scale_throughput_invariant", 0.0)
        blast = {"blast_radius_score": 0.40}
        risk_prof = DecisionRiskProfile("ADR-1", "DATA_PERSISTENCE", ["Scale & Throughput"])
        dim_gates = [DimensionGateResult("Scale & Throughput", "FAIL", [], [], ["NO_EVIDENCE"], [])]

        outcome, conf, metrics = DecisionSufficiencyGate.evaluate_sufficiency(claim, [], [], blast, dim_gates, risk_prof)
        self.assertIn(outcome, [DecisionOutcome.INSUFFICIENT_DEBATE, DecisionOutcome.REJECT], "Claim with NO_EVIDENCE MUST NOT produce PASS!")

    # -------------------------------------------------------------------------
    # Pillar 7: Cryptographic Governance & Tamper Resistance
    # -------------------------------------------------------------------------
    def test_pillar_7_artifact_governance_tamper_resistance(self):
        """Pillar 7: Canonical ADR hashing invalidates approvals when evidence or decision fields are tampered."""
        adr = ADRRecord(
            id="ADR-001",
            title="Redis Session Store",
            decision="Adopt Redis",
            alternatives=[],
            evidence=["Confirmed"],
            affected_modules=["mod_1"],
            rejected_options=[],
            reason="Low risk logging standard choice",
            status="ACCEPTED",
            epistemic_status=EpistemicStatus.CONFIRMED,
            validation_status=ValidationStatus.VALID,
            approval_status=ApprovalStatus.APPROVED
        )
        h1 = ArtifactGovernor.compute_canonical_adr_hash(adr)

        # Modify an evidence field
        adr_tampered = ADRRecord(
            id="ADR-001",
            title="Redis Session Store",
            decision="Adopt Redis",
            alternatives=[],
            evidence=["Tampered Evidence"],
            affected_modules=["mod_1"],
            rejected_options=[],
            reason="Low risk logging standard choice",
            status="ACCEPTED",
            epistemic_status=EpistemicStatus.CONFIRMED,
            validation_status=ValidationStatus.VALID,
            approval_status=ApprovalStatus.APPROVED
        )
        h2 = ArtifactGovernor.compute_canonical_adr_hash(adr_tampered)
        self.assertNotEqual(h1, h2, "Mutating evidence field MUST invalidate canonical ADR hash!")

    # -------------------------------------------------------------------------
    # Pillar 8: 19-State FSM Control Plane & Illegal Transition Rejection
    # -------------------------------------------------------------------------
    def test_pillar_8_fsm_control_plane_illegal_transitions(self):
        """Pillar 8: FSM refuses illegal jump transitions (e.g. TRIAGE -> CODING)."""
        initialize_state(self.test_dir)
        state_obj = get_state(self.test_dir)
        self.assertEqual(state_obj.currentPhase, "TRIAGE")

        # Direct illegal transition from TRIAGE to CODING must fail closed
        with self.assertRaises(ValueError):
            dispatch_event("code_written", workspace_dir=self.test_dir)

        self.assertEqual(get_state(self.test_dir).currentPhase, "TRIAGE", "FSM state MUST remain TRIAGE upon illegal transition refusal")

    # -------------------------------------------------------------------------
    # Pillar 9: Persistent Inode Locking & Strict Mutual Exclusion
    # -------------------------------------------------------------------------
    def test_pillar_9_persistent_locking_and_strict_mutual_exclusion(self):
        """Pillar 9: Persistent lock file is never unlinked, and enforces strict max_active_count == 1 across 5 concurrent workers."""
        lock_path = os.path.join(self.agents_dir, "redteam_concurrency.lock")

        active_count = 0
        max_active_count = 0
        active_lock = threading.Lock()
        intervals = []

        def worker_task(worker_id):
            nonlocal active_count, max_active_count
            with FileLock(lock_path, timeout=5.0):
                t_enter = time.time()
                with active_lock:
                    active_count += 1
                    if active_count > max_active_count:
                        max_active_count = active_count

                time.sleep(0.01)

                t_exit = time.time()
                with active_lock:
                    active_count -= 1
                    intervals.append((worker_id, t_enter, t_exit))

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_task, i) for i in range(5)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        self.assertEqual(len(intervals), 5)
        self.assertEqual(max_active_count, 1, "STRICT MUTUAL EXCLUSION: max active concurrent workers MUST NEVER exceed 1!")
        self.assertTrue(os.path.exists(lock_path), "Persistent lock file MUST remain on disk throughout execution")

    # -------------------------------------------------------------------------
    # Pillar 10: Production Mode Simulation Rejection & Version Lineage Immutability
    # -------------------------------------------------------------------------
    def test_pillar_10_production_mode_simulation_rejection(self):
        """Pillar 10: Production mode rejects synthetic simulation receipts and preserves immutable versioned lineage."""
        # Synthetic mock receipt in production mode must be rejected
        spec_file = os.path.join(self.agents_dir, "synthesized_spec.json")
        write_json_atomic(spec_file, {
            "intent_summary": "Test intent",
            "requirements": {"reqs": [{"id": "REQ-1"}]},
            "affected_systems": ["backend"],
            "acceptance_criteria": ["criteria 1"],
            "gate_result": "PASS"
        })

        design_file = os.path.join(self.agents_dir, "design_blueprint.json")
        synthetic_design = {
            "phase": "DESIGN",
            "blueprint_status": "APPROVED",
            "provenance_metadata": {
                "mode": "SIMULATION",
                "synthetic": True,
                "authority": "FSM_TEST_RUNNER"
            },
            "backend_spec": {"services": ["AuthService"]},
            "db_schema": {"tables": ["users"]},
            "frontend_layout": {"components": ["Header"]}
        }
        write_json_atomic(design_file, synthetic_design)

        os.environ["SCLASS_EXECUTION_MODE"] = "PRODUCTION"
        try:
            res_prod = EvidenceVerifier.verify_phase("DESIGN", workspace_dir=self.test_dir, allow_soft=False)
            self.assertFalse(res_prod.passed, "EvidenceVerifier in production mode MUST reject synthetic simulation receipts")
        finally:
            os.environ["SCLASS_EXECUTION_MODE"] = "TEST"


if __name__ == "__main__":
    unittest.main()
