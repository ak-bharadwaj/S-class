"""
S-Class EOS V9.6 - Comprehensive Full-System Red-Team Audit & Reliability Campaign

Executes non-tautological adversarial falsification testing across all 10 core architectural pillars:
1. Pillar 1: Adversarial Grounding & Anti-Hallucination Isolation (Multi-Vector Matrix)
2. Pillar 2: Epistemic Fail-Closed Evidence & Authoritative Pipeline Downstream Propagation
3. Pillar 3: Requirement Graph Integrity, Precedence & DAG Cycle Rejection
4. Pillar 4: Non-Tautological Architectural Lineage Traceability & 3-Vector Governor Attacks
5. Pillar 5: Disambiguated Evidence-Conditioned Security (AUTHORIZED_FOR vs String Heuristic)
6. Pillar 6: Architecture Debate Epistemic Sufficiency & Trade-off Completeness
7. Pillar 7: Full End-to-End Cryptographic Governance Tamper Resistance, Fail-Closed Exceptions & Version Binding
8. Pillar 8: 19-State FSM Control Plane & Illegal Transition Rejection
9. Pillar 9: Persistent Inode Locking Lifecycle, Mutual Exclusion & Live Owner Protection
10. Pillar 10: Production Mode Simulation Rejection & Multi-Version Lineage Chaining
"""

import unittest
import os
import sys
import shutil
import tempfile
import time
import json
import math
import hashlib
import subprocess
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
    # Pillar 2: Epistemic Fail-Closed Evidence & Authoritative Pipeline Propagation
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

        # 2. Downstream Debate Propagation through the REAL production compiler and debate engine
        req_node = RequirementNode(
            id="REQ-INVALID-EVID",
            kind=RequirementKind.FUNCTIONAL,
            statement="Execute high-privilege kernel mutation with 100k scale",
            actor="unauthorized_actor",
            capability="kernel_mutation",
            target="kernel",
            nfr_category=NFRCategory.PERFORMANCE,
            evidence=[item_nan, item_fake_prov]
        )
        r_graph = RequirementGraph()
        r_graph.add_requirement(req_node)
        b_graph = BehaviorGraph()

        # Run authoritative HLD Compiler and verify EvidenceItem propagation into ADR
        hld = HLDCompiler.compile_hld(r_graph, b_graph)
        adr_evidence_ids = []
        for adr in hld.adrs:
            for ev in (adr.evidence or []):
                if isinstance(ev, dict) and "id" in ev:
                    adr_evidence_ids.append(ev["id"])
                elif isinstance(ev, str):
                    adr_evidence_ids.append(ev)

        self.assertIn("EV-NAN", adr_evidence_ids, "Upstream EvidenceItem 'EV-NAN' MUST be preserved in HLD ADR evidence lineage!")

        # Run authoritative Debate Engine directly
        debate_result = ArchitectureDebateEngine.run_debate_cycle(
            hld=hld,
            r_graph=r_graph,
            b_graph=b_graph,
            raw_request="",
            workspace_dir=self.test_dir,
            is_debate_phase=True
        )

        # Invariant: Authoritative Debate Pipeline MUST NOT accept any ADR backed by INVALID evidence
        self.assertEqual(len(debate_result.accepted_adrs), 0, "Real Debate Pipeline MUST NOT accept ADRs backed by INVALID evidence!")
        
        # Verify exact EvidenceItem ID and fail-closed quality score in DecisionRecord decomposed claims
        found_ev_nan_record = False
        for dec_rec in debate_result.decision_records:
            self.assertIn(dec_rec.decision_outcome, [DecisionOutcome.INSUFFICIENT_DEBATE, DecisionOutcome.REJECT], "Downstream DecisionOutcome must be INSUFFICIENT_DEBATE or REJECT")
            ev_records = dec_rec.decomposed_claim.get("evidence_quality_records", [])
            for r in ev_records:
                if r.get("evidence_id") == "EV-NAN":
                    found_ev_nan_record = True
                    self.assertEqual(r.get("evidence_state"), EvidenceState.NO_EVIDENCE.value)
                    self.assertEqual(r.get("quality_score"), 0.0)
                    self.assertEqual(r.get("strength"), 0.0)

        self.assertTrue(found_ev_nan_record, "DecisionRecord decomposed claim MUST explicitly contain 'EV-NAN' with NO_EVIDENCE and quality=0.0!")

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
    # Pillar 4: Non-Tautological Lineage Traceability & 3-Vector Governor Attacks
    # -------------------------------------------------------------------------
    def test_pillar_4_non_tautological_architectural_lineage(self):
        """Pillar 4: Exact object lookup and set inclusion verifying unbroken 5-layer lineage and 3-vector governor attacks."""
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

            # 2. Exact parent HLD object resolution
            self.assertIn(task.parent_hld, hld_map, f"Task parent_hld '{task.parent_hld}' must resolve to an actual HLDModule")

            # 3. Non-empty strict Requirement Graph subset inclusion
            self.assertGreater(len(task.parent_reqs), 0, "Task parent_reqs MUST NOT be empty")
            self.assertTrue(set(task.parent_reqs).issubset(set(r_graph.nodes.keys())), "Task parent_reqs must be a strict subset of RequirementGraph nodes")

            # 4. Non-empty strict Behavior Graph subset inclusion
            self.assertGreater(len(task.parent_behaviors), 0, "Task parent_behaviors MUST NOT be empty")
            self.assertTrue(set(task.parent_behaviors).issubset(set(b_graph.nodes.keys())), "Task parent_behaviors must be a strict subset of BehaviorGraph nodes")

            # 5. Semantic capability consistency
            self.assertIn(b_node.id, task.parent_behaviors)

        # 6. Negative Attack Vector 1: Missing parent reference (empty string)
        forged_missing_parent = TaskRecord(
            id="TSK-MISSING-PARENT", title="Missing Parent Task", description="desc",
            category=TaskCategory.API_ENDPOINT, parent_lld="",
            parent_hld=tasks[0].parent_hld, parent_reqs=[],
            parent_behaviors=tasks[0].parent_behaviors
        )
        gov_res_missing = ArtifactGovernor.audit_task_governance([forged_missing_parent], r_graph, lld_components, b_graph)
        self.assertTrue(gov_res_missing.is_blocked, "ArtifactGovernor MUST block task lacking parent references")
        self.assertEqual(gov_res_missing.validation_status, ValidationStatus.INVALID)

        # 7. Negative Attack Vector 2: Forged nonexistent parent reference
        forged_nonexistent_parent = TaskRecord(
            id="TSK-FORGED-PARENT", title="Forged Nonexistent Task", description="desc",
            category=TaskCategory.API_ENDPOINT, parent_lld="LLD-FORGED-999",
            parent_hld=tasks[0].parent_hld, parent_reqs=["REQ-NONEXISTENT-999"],
            parent_behaviors=tasks[0].parent_behaviors
        )
        gov_res_nonexistent = ArtifactGovernor.audit_task_governance([forged_nonexistent_parent], r_graph, lld_components, b_graph)
        self.assertTrue(gov_res_nonexistent.is_blocked, "ArtifactGovernor MUST block task with forged nonexistent parent references")
        self.assertEqual(gov_res_nonexistent.validation_status, ValidationStatus.INVALID)

        # 8. Negative Attack Vector 3: Wrong-but-existing parent reference (Cross-Domain Lineage Hijack)
        b_graph_multi = BehaviorGraph()
        b_graph_multi.add_node(BehaviorNode(
            id="cmd_dispatch", name="DispatchVehicle", behavior_type=BehaviorNodeType.COMMAND,
            actor_id="dispatcher", target_entity_id="vehicle", epistemic_status=EpistemicStatus.EXPLICIT,
            provenance=ProvenanceKind.EXPLICIT, confidence=1.0, evidence_ref="Dispatch vehicle"
        ))
        b_graph_multi.add_node(BehaviorNode(
            id="cmd_payment", name="ProcessPayment", behavior_type=BehaviorNodeType.COMMAND,
            actor_id="cashier", target_entity_id="payment", epistemic_status=EpistemicStatus.EXPLICIT,
            provenance=ProvenanceKind.EXPLICIT, confidence=1.0, evidence_ref="Process payment"
        ))
        r_graph_multi = RequirementGraph.compile_from_behavior_graph(b_graph_multi)
        hld_multi = HLDCompiler.compile_hld(r_graph_multi, b_graph_multi)
        lld_multi = LLDCompiler.compile_lld(hld_multi, r_graph_multi, b_graph_multi)
        tasks_multi = TaskCompiler.compile_tasks(lld_multi, r_graph_multi, b_graph_multi)

        # Find two different components
        vehicle_comp = next(c for c in lld_multi if "vehicle" in c.id.lower() or "vehicle" in c.name.lower())
        payment_comp = next(c for c in lld_multi if "payment" in c.id.lower() or "payment" in c.name.lower())

        # Forge a vehicle task pointing to payment component parent LLD
        vehicle_task = next(t for t in tasks_multi if "vehicle" in t.id.lower() or "vehicle" in t.title.lower())
        hijacked_task = TaskRecord(
            id="TSK-HIJACKED", title="Hijacked Task", description="desc",
            category=TaskCategory.API_ENDPOINT, parent_lld=payment_comp.id, # Wrong but existing LLD!
            parent_hld=vehicle_task.parent_hld, parent_reqs=vehicle_task.parent_reqs,
            parent_behaviors=vehicle_task.parent_behaviors
        )
        gov_res_wrong_existing = ArtifactGovernor.audit_task_governance([hijacked_task], r_graph_multi, lld_multi, b_graph_multi)
        self.assertTrue(gov_res_wrong_existing.is_blocked, "ArtifactGovernor MUST block task pointing to wrong but existing LLD parent component!")
        self.assertEqual(gov_res_wrong_existing.validation_status, ValidationStatus.INVALID)
        self.assertTrue(any("semantic parent mismatch" in r or "semantic domain mismatch" in r for r in gov_res_wrong_existing.blocking_reasons))

        # 9. Negative Attack Vector 4: Partial-Overlap Scope Attack ({REQ-A, REQ-UNOWNED} vs {REQ-A, REQ-B})
        req_owned = vehicle_task.parent_reqs[0]
        req_unowned = "REQ-UNOWNED-999"
        # Add unowned requirement to r_graph_multi so it's a valid ID but NOT owned by vehicle_comp
        r_graph_multi.add_requirement(RequirementNode(
            id=req_unowned, kind=RequirementKind.FUNCTIONAL, statement="Unrelated requirement",
            actor="admin", capability="unrelated_action", target="unrelated"
        ))
        partial_scope_task = TaskRecord(
            id="TSK-PARTIAL", title="Partial Scope Task", description="desc",
            category=TaskCategory.API_ENDPOINT, parent_lld=vehicle_comp.id,
            parent_hld=vehicle_task.parent_hld, parent_reqs=[req_owned, req_unowned],
            parent_behaviors=vehicle_task.parent_behaviors
        )
        gov_res_partial = ArtifactGovernor.audit_task_governance([partial_scope_task], r_graph_multi, lld_multi, b_graph_multi)
        self.assertTrue(gov_res_partial.is_blocked, "ArtifactGovernor MUST block task when requirement scope is not a strict subset of parent LLD scope!")
        self.assertEqual(gov_res_partial.validation_status, ValidationStatus.INVALID)
        self.assertTrue(any("semantic parent mismatch" in r and req_unowned in r for r in gov_res_partial.blocking_reasons))

        # 10. Negative Attack Vector 5: Behavior-ID Scope Lineage Attack ({BEH-A, BEH-UNOWNED} vs {BEH-A})
        beh_unowned = "cmd_unowned_999"
        b_graph_multi.add_node(BehaviorNode(
            id=beh_unowned, name="UnownedBehavior", behavior_type=BehaviorNodeType.COMMAND,
            actor_id="admin", target_entity_id="unrelated", epistemic_status=EpistemicStatus.EXPLICIT,
            provenance=ProvenanceKind.EXPLICIT, confidence=1.0, evidence_ref="Unowned behavior"
        ))
        partial_beh_task = TaskRecord(
            id="TSK-BEH-PARTIAL", title="Partial Behavior Task", description="desc",
            category=TaskCategory.API_ENDPOINT, parent_lld=vehicle_comp.id,
            parent_hld=vehicle_task.parent_hld, parent_reqs=vehicle_task.parent_reqs,
            parent_behaviors=[vehicle_task.parent_behaviors[0], beh_unowned]
        )
        gov_res_beh = ArtifactGovernor.audit_task_governance([partial_beh_task], r_graph_multi, lld_multi, b_graph_multi)
        self.assertTrue(gov_res_beh.is_blocked, "ArtifactGovernor MUST block task when behavior scope is not a strict subset of parent LLD behavior scope!")
        self.assertEqual(gov_res_beh.validation_status, ValidationStatus.INVALID)
        self.assertTrue(any("semantic parent mismatch" in r and beh_unowned in r for r in gov_res_beh.blocking_reasons))

        # 11. Negative Attack Vector 6: Semantic Capability Mismatch (Mutation Command -> Read-Only Surface)
        read_only_ui_comp = LLDComponent(
            id="ui_read_only", name="Vehicle Read-Only View", component_type=LLDComponentType.UI_SURFACE,
            parent=vehicle_comp.parent, role="frontend_interface", layout="read_only"
        )
        mutation_task = TaskRecord(
            id="TSK-MUTATION-MISMATCH", title="Execute Vehicle Mutation", description="desc",
            category=TaskCategory.API_ENDPOINT, parent_lld=read_only_ui_comp.id,
            parent_hld=vehicle_task.parent_hld, parent_reqs=vehicle_task.parent_reqs,
            parent_behaviors=vehicle_task.parent_behaviors
        )
        gov_res_cap_mismatch = ArtifactGovernor.audit_task_governance([mutation_task], r_graph_multi, [read_only_ui_comp], b_graph_multi)
        self.assertTrue(gov_res_cap_mismatch.is_blocked, "ArtifactGovernor MUST block task when mutation command is assigned to read-only UI surface!")
        self.assertEqual(gov_res_cap_mismatch.validation_status, ValidationStatus.INVALID)
        self.assertTrue(any("semantic capability mismatch" in r for r in gov_res_cap_mismatch.blocking_reasons))

        # 12. Negative Attack Vector 7: Missing Mandatory Canonical LLD Architecture Context at API Boundary
        gov_res_no_lld = ArtifactGovernor.audit_task_governance([vehicle_task], r_graph_multi, lld_components=[], b_graph=b_graph_multi)
        self.assertTrue(gov_res_no_lld.is_blocked, "ArtifactGovernor MUST block task governance audit when canonical LLD context is omitted or empty!")
        self.assertEqual(gov_res_no_lld.validation_status, ValidationStatus.INVALID)
        self.assertTrue(any("Missing mandatory canonical LLD component" in r for r in gov_res_no_lld.blocking_reasons))

        # 13. Negative Attack Vector 8: Missing Mandatory Canonical BehaviorGraph Context at API Boundary
        empty_b_graph = BehaviorGraph()
        gov_res_no_bgraph = ArtifactGovernor.audit_task_governance([vehicle_task], r_graph_multi, lld_multi, empty_b_graph)
        self.assertTrue(gov_res_no_bgraph.is_blocked, "ArtifactGovernor MUST block task governance audit when canonical BehaviorGraph context is omitted or empty!")
        self.assertEqual(gov_res_no_bgraph.validation_status, ValidationStatus.INVALID)
        self.assertTrue(any("Missing mandatory canonical BehaviorGraph context" in r for r in gov_res_no_bgraph.blocking_reasons))

        # 14. Invariant: LLDCompiler MUST NOT fabricate synthetic REQ-001 ancestry for ungrounded modules
        empty_r_graph = RequirementGraph()
        synthetic_mod = HLDModule(id="mod_synth", name="Synthetic", system_boundary="internal", owned_entities=["X"], owned_capabilities=["nonexistent_cap"])
        synthetic_hld = HLDDesign(system_name="HLD-001", architecture_style="Modular Monolith", modules=[synthetic_mod], adrs=[], version=1)
        synthetic_lld = LLDCompiler.compile_lld(synthetic_hld, empty_r_graph, BehaviorGraph())
        self.assertEqual(len(synthetic_lld[0].parent.req_ids), 0, "LLDCompiler MUST NOT manufacture fallback 'REQ-001' or all-requirements ancestry!")

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
    # Pillar 7: Cryptographic Governance Tamper Resistance, Fail-Closed Exceptions & Version Binding
    # -------------------------------------------------------------------------
    def test_pillar_7_end_to_end_governance_tamper_blocking(self):
        """Pillar 7: ArtifactGovernor blocks FSM transition when signed ADR is tampered, audit fails, or artifact version mismatches."""
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

        # 3. Initially write pipeline with blocked: False
        hld_initial = HLDDesign(system_name="HLD-001", architecture_style="Modular Monolith", modules=[mod], adrs=[adr], version=1)
        pipe_path = os.path.join(self.agents_dir, "v7_refinement_pipeline.json")
        write_json_atomic(pipe_path, {
            "version": 1,
            "hld_design": hld_initial.to_dict(),
            "blocked": False,
            "hld_governance": {"is_blocked": False}
        })

        # Verify initial transition is permitted
        gov_res_init = ArtifactGovernor.enforce_fsm_transition(
            current_phase="DESIGN",
            proposed_event="spec_approved",
            target_phase="CODING",
            workspace_dir=self.test_dir
        )
        self.assertFalse(gov_res_init.is_blocked, "Untampered approved ADR MUST be permitted to transition to CODING")

        # 4. Tamper ADR decision on disk while keeping pipeline blocked: False
        adr_tampered = ADRRecord.from_dict(adr.to_dict())
        adr_tampered.decision = "Adopt In-Memory Dict (TAMPERED)"
        hld_tampered = HLDDesign(system_name="HLD-001", architecture_style="Modular Monolith", modules=[mod], adrs=[adr_tampered], version=1)
        write_json_atomic(pipe_path, {
            "version": 1,
            "hld_design": hld_tampered.to_dict(),
            "blocked": False,
            "hld_governance": {"is_blocked": False}
        })

        # Governor enforcement MUST detect tampering dynamically and BLOCK transition to CODING
        gov_res = ArtifactGovernor.enforce_fsm_transition(
            current_phase="DESIGN",
            proposed_event="spec_approved",
            target_phase="CODING",
            workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked, "ArtifactGovernor MUST dynamically detect ADR tampering and block FSM transition to CODING")

        # 5. Fail-Closed Governance Audit Exception: malformed HLD on disk must fail closed (GOVERNANCE_AUDIT_ERROR)
        write_json_atomic(pipe_path, {
            "version": 1,
            "hld_design": {"modules": "CORRUPT_NOT_A_LIST", "adrs": "MALFORMED"},
            "blocked": False,
            "hld_governance": {"is_blocked": False}
        })
        gov_res_err = ArtifactGovernor.enforce_fsm_transition(
            current_phase="DESIGN",
            proposed_event="spec_approved",
            target_phase="CODING",
            workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res_err.is_blocked, "Governance exception MUST fail closed and block transition")
        self.assertTrue(any("GOVERNANCE_AUDIT_ERROR" in r for r in gov_res_err.blocking_reasons))

        # 6. Strict Governance: Missing 'version' inside HLDDesign must raise ValueError and fail closed
        write_json_atomic(pipe_path, {
            "version": 1,
            "hld_design": {
                "system_name": "HLD-001",
                "architecture_style": "Modular Monolith",
                "modules": [mod.to_dict()],
                "adrs": [adr.to_dict()]
                # Note: 'version' intentionally omitted inside hld_design
            },
            "blocked": False,
            "hld_governance": {"is_blocked": False}
        })
        gov_res_no_ver = ArtifactGovernor.enforce_fsm_transition(
            current_phase="DESIGN",
            proposed_event="spec_approved",
            target_phase="CODING",
            workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res_no_ver.is_blocked, "Missing 'version' in strict governance HLD MUST fail closed")
        self.assertTrue(any("GOVERNANCE_AUDIT_ERROR" in r for r in gov_res_no_ver.blocking_reasons))

        # 7. Strict Governance Schema: Boolean 'version: True' must be rejected (type(version) is int check)
        write_json_atomic(pipe_path, {
            "version": 1,
            "hld_design": {
                "system_name": "HLD-001",
                "architecture_style": "Modular Monolith",
                "modules": [mod.to_dict()],
                "adrs": [adr.to_dict()],
                "version": True  # Boolean instead of int!
            },
            "blocked": False,
            "hld_governance": {"is_blocked": False}
        })
        gov_res_bool_ver = ArtifactGovernor.enforce_fsm_transition(
            current_phase="DESIGN",
            proposed_event="spec_approved",
            target_phase="CODING",
            workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res_bool_ver.is_blocked, "Boolean 'version: True' in strict governance HLD MUST fail closed")
        self.assertTrue(any("GOVERNANCE_AUDIT_ERROR" in r for r in gov_res_bool_ver.blocking_reasons))

        # 8. Artifact Version Binding: Approval was for version 1; pipeline attempts to execute version 2 -> MUST BLOCK
        hld_v2 = HLDDesign(system_name="HLD-001", architecture_style="Modular Monolith", modules=[mod], adrs=[adr], version=2)
        write_json_atomic(pipe_path, {
            "version": 2,
            "hld_design": hld_v2.to_dict(),
            "blocked": False,
            "hld_governance": {"is_blocked": False}
        })
        gov_res_v2 = ArtifactGovernor.enforce_fsm_transition(
            current_phase="DESIGN",
            proposed_event="spec_approved",
            target_phase="CODING",
            workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res_v2.is_blocked, "ArtifactGovernor MUST block when executing artifact version 2 against version 1 approval")
        self.assertTrue(any("artifact version mismatch" in r for r in gov_res_v2.blocking_reasons))

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

        # 3. Live Owner holding lock with corrupt metadata MUST NOT be stolen even if stale_ttl is exceeded
        repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        code = f"""
import sys, time, os
sys.path.insert(0, r'{repo_dir}')
from runtime import FileLock
lock = FileLock(r'{lock_path}', timeout=5.0)
lock.__enter__()
if lock._fd is not None:
    os.ftruncate(lock._fd, 0)
    os.lseek(lock._fd, 0, os.SEEK_SET)
    os.write(lock._fd, b"CORRUPT_GARBAGE_JSON_PAYLOAD_12345")
    os.fsync(lock._fd)
print("HELD", flush=True)
time.sleep(30)
"""
        proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            line = proc.stdout.readline()
            self.assertIn("HELD", line, "Subprocess A must hold kernel lock first")

            competer_blocked = False
            try:
                with FileLock(lock_path, timeout=0.4, stale_ttl=0.01):
                    pass
            except TimeoutError:
                competer_blocked = True
            self.assertTrue(competer_blocked, "Live owner with corrupt metadata and exceeded stale_ttl MUST NEVER be stolen!")
        finally:
            if proc.poll() is None:
                proc.kill()

    # -------------------------------------------------------------------------
    # Pillar 10: Production Mode Simulation Rejection & Multi-Version Lineage Chaining
    # -------------------------------------------------------------------------
    def test_pillar_10_production_simulation_rejection_and_version_lineage(self):
        """Pillar 10: Rejects simulation receipts in production AND enforces 3-version parent hash lineage chaining."""
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

        # Sub-test B: Full 3-Version Lineage Immutability Chaining (v1 -> v2 -> v3)
        pipe_v1 = {
            "version": 1,
            "behavior_graph": {"nodes": {}},
            "requirement_graph": {"nodes": {}},
            "hld_design": {"adrs": []},
            "debate_result": {"accepted_adrs": []},
            "lld_components": [],
            "tasks": [],
            "dependency_holes": [{"req_id": "REQ-001"}],
            "blocked": False
        }
        p1 = SpecificationCompiler.save_versioned_pipeline_artifact(pipe_v1, self.test_dir)
        self.assertTrue(p1.endswith("v1.json"))

        with open(p1, "rb") as f:
            v1_hash = hashlib.sha256(f.read()).hexdigest()

        pipe_v2 = {
            "version": 2,
            "behavior_graph": {"nodes": {}},
            "requirement_graph": {"nodes": {}},
            "hld_design": {"adrs": []},
            "debate_result": {"accepted_adrs": []},
            "lld_components": [],
            "tasks": [],
            "dependency_holes": [{"req_id": "REQ-001"}, {"req_id": "REQ-002"}],
            "blocked": False,
            "parent_version": 1,
            "parent_hash": v1_hash
        }
        p2 = SpecificationCompiler.save_versioned_pipeline_artifact(pipe_v2, self.test_dir)
        self.assertTrue(p2.endswith("v2.json"))

        with open(p2, "rb") as f:
            v2_hash = hashlib.sha256(f.read()).hexdigest()

        pipe_v3 = {
            "version": 3,
            "behavior_graph": {"nodes": {}},
            "requirement_graph": {"nodes": {}},
            "hld_design": {"adrs": []},
            "debate_result": {"accepted_adrs": []},
            "lld_components": [],
            "tasks": [],
            "dependency_holes": [{"req_id": "REQ-001"}, {"req_id": "REQ-002"}, {"req_id": "REQ-003"}],
            "blocked": False,
            "parent_version": 2,
            "parent_hash": v2_hash
        }
        p3 = SpecificationCompiler.save_versioned_pipeline_artifact(pipe_v3, self.test_dir)
        self.assertTrue(p3.endswith("v3.json"))

        with open(p3, "r", encoding="utf-8") as f:
            v3_data = json.load(f)

        self.assertEqual(v3_data.get("version"), 3)
        self.assertEqual(v3_data.get("parent_version"), 2)
        self.assertEqual(
            v3_data.get("parent_hash"), v2_hash,
            "v3 parent_hash MUST equal exact SHA-256 byte digest of v2.json"
        )


if __name__ == "__main__":
    unittest.main()
