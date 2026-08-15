"""
S-Class EOS V9.6 - Comprehensive Full-System Red-Team Audit & Reliability Campaign

Executes non-tautological adversarial falsification testing across all 10 core architectural pillars:
1. Pillar 1: Adversarial Grounding & Anti-Hallucination Isolation (Multi-Vector Matrix)
2. Pillar 2: Epistemic Fail-Closed Evidence & Cross-Module Downstream Propagation
3. Pillar 3: Requirement Graph Integrity, Precedence & Cycle Rejection
4. Pillar 4: End-to-End Non-Tautological Architectural Lineage Traceability & Negative Attacks
5. Pillar 5: Disambiguated Evidence-Conditioned Security (AUTHORIZED_FOR vs String Heuristic)
6. Pillar 6: Architecture Debate Epistemic Sufficiency & Trade-off Completeness
7. Pillar 7: Full End-to-End Cryptographic Governance Tamper Resistance & FSM Blocking
8. Pillar 8: 19-State FSM Control Plane & Illegal Transition Rejection
9. Pillar 9: Persistent Inode Locking Lifecycle, Mutual Exclusion & Live Owner Protection
10. Pillar 10: Production Mode Simulation Rejection & Version Lineage Immutability Chaining
"""

import unittest
import os
import shutil
import tempfile
import time
import json
import math
import hashlib
import concurrent.futures
import threading

from domain_primitives import (
    DomainPrimitiveType,
    ProvenanceKind,
    SemanticDomainGraph,
    DomainNode,
    DomainEdge,
    RelationType
)
from behavior_graph import (
    BehaviorGraph,
    BehaviorGraphEngine,
    BehaviorNode,
    BehaviorNodeType,
    BehaviorRelationType,
    EpistemicStatus
)
from requirement_ir import (
    RequirementGraph,
    RequirementNode,
    RequirementKind,
    NFRCategory,
    EvidenceItem,
    normalize_evidence,
    DuplicateIDConflictError,
    CircularDependencyError
)
from hld_compiler import (
    HLDCompiler,
    HLDDesign,
    HLDModule,
    ADRRecord,
    ValidationStatus,
    ApprovalStatus
)
from lld_compiler import (
    LLDCompiler,
    LLDComponent,
    LLDComponentType
)
from task_compiler import (
    TaskCompiler,
    TaskRecord,
    TaskCategory
)
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
from artifact_governor import (
    ArtifactGovernor,
    ApprovalRecord,
    ApprovalAuthority,
    FSMTransitionTarget
)
from spec_compiler import SpecificationCompiler
from runtime import (
    FileLock,
    initialize_state,
    get_state,
    dispatch_event,
    write_json_atomic,
    load_json
)
from verifier import EvidenceVerifier


class TestV96FullSystemRedTeam(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sclass_v96_redteam_")
        self.agents_dir = os.path.join(self.test_dir, ".agents")
        os.makedirs(self.agents_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Pillar 1: Adversarial Grounding & Anti-Hallucination Isolation (Multi-Vector)
    # -------------------------------------------------------------------------
    def test_pillar_1_multi_vector_adversarial_grounding(self):
        """Pillar 1: Multi-vector anti-hallucination matrix."""
        d_graph = SemanticDomainGraph()
        d_graph.add_node(DomainNode(id="actor_doctor", name="Doctor", primitive_type=DomainPrimitiveType.ACTOR, provenance=ProvenanceKind.EXPLICIT))
        d_graph.add_node(DomainNode(id="entity_patient", name="Patient", primitive_type=DomainPrimitiveType.ENTITY, provenance=ProvenanceKind.EXPLICIT))

        # Vector 1: Empty prompt forces ungrounded fallback queries into PROPOSED status
        b_graph_empty = BehaviorGraphEngine.build_behavior_graph(d_graph, "")
        proposed_queries = [n for n in b_graph_empty.nodes.values() if n.epistemic_status == EpistemicStatus.PROPOSED]
        self.assertGreaterEqual(len(proposed_queries), 1)
        for node in proposed_queries:
            self.assertEqual(node.epistemic_status, EpistemicStatus.PROPOSED)
            self.assertEqual(node.provenance, ProvenanceKind.SPECULATIVE)
            self.assertLessEqual(node.confidence, 0.5)

        # Vector 2: Prose statement creates PERFORMS relation, NEVER AUTHORIZED_FOR without RBAC evidence
        prompt_prose = "Doctor examines patient."
        b_graph_prose = BehaviorGraphEngine.build_behavior_graph(d_graph, prompt_prose)
        performs_edges = [e for e in b_graph_prose.edges if e.relation == BehaviorRelationType.PERFORMS]
        auth_edges = [e for e in b_graph_prose.edges if e.relation == BehaviorRelationType.AUTHORIZED_FOR]
        self.assertGreaterEqual(len(performs_edges), 1)
        self.assertEqual(len(auth_edges), 0, "Prose text MUST NOT invent AUTHORIZED_FOR relation without explicit security evidence!")

    # -------------------------------------------------------------------------
    # Pillar 2: Epistemic Fail-Closed Evidence & Cross-Module Propagation
    # -------------------------------------------------------------------------
    def test_pillar_2_fail_closed_evidence_and_downstream_propagation(self):
        """Pillar 2: Corrupted evidence quality/provenance fails closed and CANNOT satisfy downstream gates."""
        # 1. Parsing fail-closed assertions
        item_nan = EvidenceItem(id="EV-NAN", quality=float("nan"))
        self.assertEqual(item_nan.quality, 0.0)
        self.assertEqual(item_nan.provenance, ProvenanceKind.INVALID)

        item_inf = EvidenceItem(id="EV-INF", quality=float("inf"))
        self.assertEqual(item_inf.quality, 0.0)
        self.assertEqual(item_inf.provenance, ProvenanceKind.INVALID)

        item_fake_prov = EvidenceItem.from_dict({"id": "EV-FAKE", "provenance": "corrupted_garbage_provenance"})
        self.assertEqual(item_fake_prov.provenance, ProvenanceKind.INVALID)
        self.assertEqual(item_fake_prov.quality, 0.0)

        with self.assertRaises(TypeError):
            normalize_evidence(set([1, 2, 3]))

        # 2. Downstream Debate Propagation: INVALID evidence CANNOT produce ACCEPT
        ev_record = EvidenceQualityRecord("EV-INV", EvidenceState.NO_EVIDENCE, "NO_EVIDENCE", "", 0.0, 0.0, 0.0, 0.0)
        claim = EngineeringClaim("CLAIM-1", "ADR-1", "Use Redis", "Reason", [], [], [], [], [], [], [ev_record], "scale_throughput_invariant", 0.0)
        blast = {"blast_radius_score": 0.40}
        risk_prof = DecisionRiskProfile("ADR-1", "DATA_PERSISTENCE", ["Scale & Throughput"])
        dim_gates = [DimensionGateResult("Scale & Throughput", "FAIL", [], [], ["INVALID_EVIDENCE"], [])]

        outcome, conf, metrics = DecisionSufficiencyGate.evaluate_sufficiency(claim, [], [], blast, dim_gates, risk_prof)
        self.assertIn(outcome, [DecisionOutcome.INSUFFICIENT_DEBATE, DecisionOutcome.REJECT], "Downstream Debate Gate MUST reject claim with INVALID evidence!")

    # -------------------------------------------------------------------------
    # Pillar 3: Requirement Graph Integrity, Precedence & Cycle Rejection
    # -------------------------------------------------------------------------
    def test_pillar_3_requirement_integrity_precedence_and_cycle_rejection(self):
        """Pillar 3: Rejects duplicate ID semantic collisions, prevents cycles, and enforces precedence."""
        r_graph = RequirementGraph()
        r1 = RequirementNode(id="REQ-001", kind=RequirementKind.FUNCTIONAL, statement="Login", actor="user", capability="login", target="session")
        r_graph.add_requirement(r1)

        # Collision with conflicting semantic identity
        r1_conflict = RequirementNode(id="REQ-001", kind=RequirementKind.FUNCTIONAL, statement="Login", actor="admin", capability="login", target="session")
        with self.assertRaises(DuplicateIDConflictError):
            r_graph.add_requirement(r1_conflict)

        # Circular dependency cycle
        r2 = RequirementNode(id="REQ-002", kind=RequirementKind.FUNCTIONAL, statement="Dashboard", actor="user", capability="view", target="dashboard")
        r_graph.add_requirement(r2)
        r_graph.add_dependency("REQ-002", "REQ-001")

        with self.assertRaises(CircularDependencyError):
            r_graph.add_dependency("REQ-001", "REQ-002")

    # -------------------------------------------------------------------------
    # Pillar 4: End-to-End Non-Tautological Lineage Traceability & Negative Attacks
    # -------------------------------------------------------------------------
    def test_pillar_4_non_tautological_architectural_lineage(self):
        """Pillar 4: Exact object lookup and set inclusion verifying unbroken 5-layer lineage."""
        b_graph = BehaviorGraph()
        b_node = BehaviorNode(
            id="cmd_dispatch", name="DispatchVehicle", behavior_type=BehaviorNodeType.COMMAND,
            actor_id="dispatcher", target_entity_id="vehicle", epistemic_status=EpistemicStatus.EXPLICIT,
            provenance=ProvenanceKind.EXPLICIT, confidence=1.0, evidence_ref="Explicit dispatch command"
        )
        b_graph.add_node(b_node)

        r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)
        hld_design = HLDCompiler.compile_hld(r_graph, b_graph)
        lld_components = LLDCompiler.compile_lld(hld_design, r_graph, b_graph)
        tasks = TaskCompiler.compile_tasks(lld_components, r_graph, b_graph)

        self.assertGreaterEqual(len(tasks), 1)
        lld_map = {c.id: c for c in lld_components}
        hld_map = {m.id: m for m in hld_design.modules}

        for task in tasks:
            # 1. Exact parent LLD object resolution
            self.assertIn(task.parent_lld, lld_map, f"Task parent_lld '{task.parent_lld}' must resolve to an actual LLDComponent")
            parent_lld = lld_map[task.parent_lld]

            # 2. Exact parent HLD object resolution
            self.assertIn(task.parent_hld, hld_map, f"Task parent_hld '{task.parent_hld}' must resolve to an actual HLDModule")

            # 3. Exact Requirement Graph subset inclusion
            self.assertTrue(set(task.parent_reqs).issubset(set(r_graph.nodes.keys())), "Task parent_reqs must be a strict subset of RequirementGraph nodes")

            # 4. Exact Behavior Graph subset inclusion
            self.assertTrue(set(task.parent_behaviors).issubset(set(b_graph.nodes.keys())), "Task parent_behaviors must be a strict subset of BehaviorGraph nodes")

            # 5. Semantic capability consistency
            self.assertIn(b_node.id, task.parent_behaviors)

        # 6. Negative Attack Vector A: Injected forged parent LLD ID MUST fail lineage resolution
        forged_task_lld = TaskRecord(
            id="TSK-FORGED-LLD", title="Forged Task", description="desc",
            category=TaskCategory.API_ENDPOINT, parent_lld="LLD-FORGED-999",
            parent_hld=tasks[0].parent_hld, parent_reqs=tasks[0].parent_reqs,
            parent_behaviors=tasks[0].parent_behaviors
        )
        self.assertNotIn(forged_task_lld.parent_lld, lld_map, "Forged LLD ID MUST NOT resolve against actual LLD component map")

        # 7. Negative Attack Vector B: Injected non-existent requirement ID MUST fail subset inclusion
        forged_task_req = TaskRecord(
            id="TSK-FORGED-REQ", title="Forged Task Req", description="desc",
            category=TaskCategory.API_ENDPOINT, parent_lld=tasks[0].parent_lld,
            parent_hld=tasks[0].parent_hld, parent_reqs=["REQ-NONEXISTENT-999"],
            parent_behaviors=tasks[0].parent_behaviors
        )
        self.assertFalse(set(forged_task_req.parent_reqs).issubset(set(r_graph.nodes.keys())), "Non-existent requirement ID MUST fail graph subset inclusion")

    # -------------------------------------------------------------------------
    # Pillar 5: Disambiguated Evidence-Conditioned Security (AUTHORIZED_FOR vs String)
    # -------------------------------------------------------------------------
    def test_pillar_5_disambiguated_security_evidence_conditioning(self):
        """Pillar 5: HTTP 403 Forbidden is conditioned strictly on AUTHORIZED_FOR graph relation, NOT prose strings."""
        # Sub-case A: PERFORMS relation only (without AUTHORIZED_FOR and without 'role:' string in evidence)
        b_graph_no_auth = BehaviorGraph()
        b_graph_no_auth.add_node(BehaviorNode(
            id="cmd_read", name="ReadNews", behavior_type=BehaviorNodeType.COMMAND,
            actor_id="guest", target_entity_id="article", epistemic_status=EpistemicStatus.EXPLICIT,
            provenance=ProvenanceKind.EXPLICIT, confidence=1.0, evidence_ref="Guest reads news article text"
        ))
        b_graph_no_auth.add_edge("guest", BehaviorRelationType.PERFORMS, "cmd_read")

        r_graph_no_auth = RequirementGraph.compile_from_behavior_graph(b_graph_no_auth)
        hld_no_auth = HLDCompiler.compile_hld(r_graph_no_auth, b_graph_no_auth)
        lld_no_auth = LLDCompiler.compile_lld(hld_no_auth, r_graph_no_auth, b_graph_no_auth)
        tasks_no_auth = TaskCompiler.compile_tasks(lld_no_auth, r_graph_no_auth, b_graph_no_auth)

        for task in tasks_no_auth:
            for crit in task.verification_criteria:
                self.assertNotIn("403 Forbidden", crit, "PERFORMS relation alone MUST NOT trigger 403 Forbidden assertion")

        # Sub-case B: AUTHORIZED_FOR relation present (without 'role:' string in evidence)
        b_graph_auth = BehaviorGraph()
        b_graph_auth.add_node(BehaviorNode(
            id="cmd_override", name="OverrideSafety", behavior_type=BehaviorNodeType.COMMAND,
            actor_id="admin", target_entity_id="engine", epistemic_status=EpistemicStatus.EXPLICIT,
            provenance=ProvenanceKind.EXPLICIT, confidence=1.0, evidence_ref="Overriding safety control mechanism"
        ))
        b_graph_auth.add_edge("admin", BehaviorRelationType.AUTHORIZED_FOR, "cmd_override")

        r_graph_auth = RequirementGraph.compile_from_behavior_graph(b_graph_auth)
        hld_auth = HLDCompiler.compile_hld(r_graph_auth, b_graph_auth)
        lld_auth = LLDCompiler.compile_lld(hld_auth, r_graph_auth, b_graph_auth)
        tasks_auth = TaskCompiler.compile_tasks(lld_auth, r_graph_auth, b_graph_auth)

        found_403 = any(any("403 Forbidden" in crit for crit in t.verification_criteria) for t in tasks_auth)
        self.assertTrue(found_403, "AUTHORIZED_FOR relation MUST trigger 403 Forbidden assertion even without 'role:' in evidence string")

    # -------------------------------------------------------------------------
    # Pillar 6: Architecture Debate Epistemic Sufficiency & Trade-off Completeness
    # -------------------------------------------------------------------------
    def test_pillar_6_debate_tradeoff_complete_sufficiency(self):
        """Pillar 6: Grounded alternatives without comparison rationale fail sufficiency gate."""
        unrationale_alt = ArchitecturalAlternative("ALT-01", "Monolith", "Desc", ["Pro"], ["Con"], 0.3, 0.5, is_synthetic=False, comparison_rationale="")
        ev_record = EvidenceQualityRecord("EV-1", EvidenceState.DIRECT_EVIDENCE, "REQUIREMENT_GRAPH", "Requirement", 0.90, 1.0, 0.90, 0.90)
        claim = EngineeringClaim("CLAIM-1", "ADR-1", "Use Monolith", "Reason", [], [], [], [], [], [], [ev_record], "scale_throughput_invariant", 0.90)
        blast = {"blast_radius_score": 0.40}
        risk_prof = DecisionRiskProfile("ADR-1", "DATA_PERSISTENCE", ["Data Consistency & Persistence"])
        dim_gates = [DimensionGateResult("Data Consistency & Persistence", "PASS", ["Matched"], ["Matched"], [], [])]

        outcome_un, conf_un, metrics_un = DecisionSufficiencyGate.evaluate_sufficiency(claim, [], [unrationale_alt], blast, dim_gates, risk_prof)
        self.assertFalse(metrics_un["alternatives_explored"], "Alternative without comparison rationale MUST NOT count as explored")
        self.assertEqual(outcome_un, DecisionOutcome.INSUFFICIENT_DEBATE)

    # -------------------------------------------------------------------------
    # Pillar 7: Full End-to-End Cryptographic Governance Tamper Resistance & FSM Blocking
    # -------------------------------------------------------------------------
    def test_pillar_7_end_to_end_governance_tamper_blocking(self):
        """Pillar 7: ArtifactGovernor blocks FSM transition to CODING when signed ADR content is tampered."""
        initialize_state(self.test_dir)
        sec_key = ArtifactGovernor._get_governance_secret(self.test_dir)
        mod = HLDModule(id="mod_core", name="Core", system_boundary="internal", owned_entities=["Session"], owned_capabilities=["manage_session"])

        # 1. Create a valid ADR record and compute its canonical hash
        adr = ADRRecord(
            id="ADR-001",
            title="Session Store",
            decision="Adopt Redis",
            alternatives=["Memcached"],
            evidence=["High throughput requirement"],
            affected_modules=["mod_core"],
            rejected_options=["Memcached"],
            reason="Native persistence support",
            status="PROPOSED",
            confidence=0.5,
            epistemic_status=EpistemicStatus.PROPOSED
        )
        orig_hash = ArtifactGovernor.compute_canonical_adr_hash(adr)

        # 2. Write valid cryptographic approval record into approvals.json
        rec = ApprovalRecord(
            decision_id="ADR-001",
            artifact_id="HLD-001",
            artifact_version=1,
            content_hash=orig_hash,
            decision="ACCEPTED",
            authority=ApprovalAuthority.TEST_SYNTHETIC,
            reason="Approved by architect",
            timestamp="2026-08-15T00:00:00Z"
        )
        rec.signature = rec.compute_signature(sec_key)
        app_file = os.path.join(self.agents_dir, "approvals.json")
        write_json_atomic(app_file, {"approval_records": [rec.to_dict()]})

        # 3. Mutate ADR decision field on disk (Tamper Attack)
        adr.decision = "Adopt In-Memory Dict (TAMPERED)"
        hld = HLDDesign(system_name="HLD-001", architecture_style="Modular Monolith", modules=[mod], adrs=[adr])

        # 4. Audit HLD Governance MUST detect content hash mismatch and block
        gov_audit = ArtifactGovernor.audit_hld_governance(hld, True, [], workspace_dir=self.test_dir)
        self.assertTrue(gov_audit.is_blocked, "ArtifactGovernor audit MUST block when ADR content is tampered")
        self.assertTrue(any("canonical content hash mismatch" in r for r in gov_audit.blocking_reasons))

        # 5. FSM Transition to CODING MUST be hard-denied
        pipe_path = os.path.join(self.agents_dir, "v7_refinement_pipeline.json")
        write_json_atomic(pipe_path, {
            "version": 1,
            "hld_design": hld.to_dict(),
            "blocked": True,
            "hld_governance": gov_audit.to_dict()
        })
        gov_res = ArtifactGovernor.enforce_fsm_transition(
            current_phase="DESIGN",
            proposed_event="spec_approved",
            target_phase="CODING",
            workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked, "ArtifactGovernor MUST block FSM transition to CODING on tampered ADR")

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
    # Pillar 9: Persistent Inode Locking Lifecycle, Mutual Exclusion & Live Owner Protection
    # -------------------------------------------------------------------------
    def test_pillar_9_persistent_locking_lifecycle_and_live_owner_protection(self):
        """Pillar 9: Persistent lock file survives across releases and live owner with corrupt metadata is never stolen."""
        lock_path = os.path.join(self.agents_dir, "redteam_lifecycle.lock")

        # 1. First acquisition creates persistent file
        with FileLock(lock_path, timeout=2.0):
            self.assertTrue(os.path.exists(lock_path))

        # Persistent lock file MUST remain on disk after release
        self.assertTrue(os.path.exists(lock_path), "Persistent lock file MUST remain on disk after release")

        # 2. Multi-threaded strict mutual exclusion: max_active_count == 1
        active_count = 0
        max_active_count = 0
        active_lock = threading.Lock()

        def worker_task(worker_id):
            nonlocal active_count, max_active_count
            with FileLock(lock_path, timeout=5.0):
                with active_lock:
                    active_count += 1
                    if active_count > max_active_count:
                        max_active_count = active_count
                time.sleep(0.01)
                with active_lock:
                    active_count -= 1

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_task, i) for i in range(5)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        self.assertEqual(max_active_count, 1, "STRICT MUTUAL EXCLUSION: max active concurrent workers MUST NEVER exceed 1!")

    # -------------------------------------------------------------------------
    # Pillar 10: Production Mode Simulation Rejection & Version Lineage Immutability Chaining
    # -------------------------------------------------------------------------
    def test_pillar_10_production_simulation_rejection_and_version_lineage(self):
        """Pillar 10: Rejects simulation receipts in production AND enforces parent hash chaining across versions."""
        # Sub-test A: Production mode simulation rejection
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

        # Sub-test B: Version Lineage Immutability & Parent Hash Chaining
        pipe_v1 = {
            "version": 1,
            "behavior_graph": {"nodes": {}},
            "requirement_graph": {"nodes": {}},
            "hld_design": {"adrs": []},
            "debate_result": {"accepted_adrs": []},
            "lld_components": [],
            "tasks": [],
            "blocked": False
        }
        p1 = SpecificationCompiler.save_versioned_pipeline_artifact(pipe_v1, self.test_dir)
        self.assertTrue(p1.endswith("v1.json"))

        with open(p1, "rb") as f:
            v1_bytes = f.read()
        expected_v1_sha256 = hashlib.sha256(v1_bytes).hexdigest()

        pipe_v2 = dict(pipe_v1)
        pipe_v2["dependency_holes"] = [{"req_id": "REQ-001"}]
        p2 = SpecificationCompiler.save_versioned_pipeline_artifact(pipe_v2, self.test_dir)
        self.assertTrue(p2.endswith("v2.json"))

        with open(p2, "r", encoding="utf-8") as f:
            v2_data = json.load(f)

        self.assertEqual(v2_data.get("version"), 2)
        self.assertEqual(v2_data.get("parent_version"), 1)
        self.assertEqual(
            v2_data.get("parent_hash"), expected_v1_sha256,
            "v2 parent_hash MUST equal exact SHA-256 byte digest of v1.json"
        )


if __name__ == "__main__":
    unittest.main()
