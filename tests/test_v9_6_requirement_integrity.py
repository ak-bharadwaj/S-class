"""
S-Class V9.6 Hardening Suite Vector 2: Requirement Graph Integrity & Corruption Defense
"""

import unittest
from requirement_ir import (
    RequirementGraph,
    RequirementNode,
    RequirementKind,
    DuplicateIDConflictError,
    CircularDependencyError
)
from behavior_graph import EpistemicStatus
from domain_primitives import ProvenanceKind


class TestV96RequirementIntegrity(unittest.TestCase):

    def test_duplicate_id_semantic_conflict_rejection(self):
        """Invariant: Adding two requirements with identical ID but conflicting statement/capability MUST raise DuplicateIDConflictError."""
        r_graph = RequirementGraph()

        req1 = RequirementNode(
            id="REQ-001",
            kind=RequirementKind.FUNCTIONAL,
            statement="The system shall process student enrollment.",
            actor="student",
            capability="enrollment",
            target="course"
        )
        r_graph.add_requirement(req1)

        # Same ID but conflicting statement and capability
        req2 = RequirementNode(
            id="REQ-001",
            kind=RequirementKind.FUNCTIONAL,
            statement="The system shall delete instructor accounts permanently.",
            actor="admin",
            capability="delete_account",
            target="instructor"
        )

        with self.assertRaises(DuplicateIDConflictError):
            r_graph.add_requirement(req2)

    def test_duplicate_id_identical_content_deduplication(self):
        """Invariant: Adding the exact same requirement twice under the same ID deduplicates without error."""
        r_graph = RequirementGraph()

        req1 = RequirementNode(
            id="REQ-001",
            kind=RequirementKind.FUNCTIONAL,
            statement="The system shall process student enrollment.",
            actor="student",
            capability="enrollment",
            target="course"
        )
        r_graph.add_requirement(req1)
        r_graph.add_requirement(req1)

        self.assertEqual(len(r_graph.nodes), 1)

    def test_circular_dependency_rejection(self):
        """Invariant: Creating circular dependencies (REQ-001 -> REQ-002 -> REQ-001) MUST raise CircularDependencyError."""
        r_graph = RequirementGraph()

        req1 = RequirementNode(id="REQ-001", kind=RequirementKind.FUNCTIONAL, statement="R1", actor="a", capability="c1", target="t")
        req2 = RequirementNode(id="REQ-002", kind=RequirementKind.FUNCTIONAL, statement="R2", actor="a", capability="c2", target="t")

        r_graph.add_requirement(req1)
        r_graph.add_requirement(req2)

        r_graph.add_dependency("REQ-001", "REQ-002")

    def test_duplicate_id_subtle_semantic_conflict_actor_and_risk(self):
        """Invariant: Same ID and identical statement but differing actor or risk (e.g. doctor vs attacker) MUST trigger DuplicateIDConflictError."""
        r_graph = RequirementGraph()

        req1 = RequirementNode(
            id="REQ-001",
            kind=RequirementKind.FUNCTIONAL,
            statement="The system shall approve payment",
            actor="doctor",
            capability="approve_payment",
            target="payment",
            risk="LOW"
        )
        r_graph.add_requirement(req1)

        req2 = RequirementNode(
            id="REQ-001",
            kind=RequirementKind.FUNCTIONAL,
            statement="The system shall approve payment",
            actor="attacker",
            capability="approve_payment",
            target="payment",
            risk="HIGH"
        )

        with self.assertRaises(DuplicateIDConflictError):
            r_graph.add_requirement(req2)

    def test_epistemic_confidence_refinement_allowed_for_identical_semantic_identity(self):
        """Invariant: Refining confidence/epistemic status for identical semantic identity (same actor, capability, statement, risk) is ALLOWED and updates node."""
        r_graph = RequirementGraph()

        req1 = RequirementNode(
            id="REQ-001",
            kind=RequirementKind.FUNCTIONAL,
            statement="System must process payment",
            actor="operator",
            capability="payment",
            target="system",
            confidence=0.6,
            epistemic_status=EpistemicStatus.PROPOSED
        )
        r_graph.add_requirement(req1)

        req2 = RequirementNode(
            id="REQ-001",
            kind=RequirementKind.FUNCTIONAL,
            statement="System must process payment",
            actor="operator",
            capability="payment",
            target="system",
            confidence=0.95,
            epistemic_status=EpistemicStatus.EXPLICIT
        )
        # Identical semantic identity -> refinement allowed without raising DuplicateIDConflictError
        updated = r_graph.add_requirement(req2)
        self.assertEqual(updated.confidence, 0.95)
        self.assertEqual(updated.epistemic_status, EpistemicStatus.EXPLICIT)

    def test_epistemic_precedence_policy_prevents_downgrade_of_confirmed_status(self):
        """Invariant: Epistemic Precedence Merge Policy prevents lower-ranked PROPOSED status (even with confidence=0.99) from downgrading EXPLICIT/CONFIRMED status (confidence=0.85)."""
        r_graph = RequirementGraph()

        # Existing higher-ranked status
        req_confirmed = RequirementNode(
            id="REQ-CONF-001",
            kind=RequirementKind.FUNCTIONAL,
            statement="System must log all administrative actions.",
            actor="admin",
            capability="audit_log",
            target="logs",
            confidence=0.85,
            epistemic_status=EpistemicStatus.EXPLICIT,
            provenance=ProvenanceKind.EXPLICIT
        )
        r_graph.add_requirement(req_confirmed)

        # Proposed lower-ranked requirement with higher numeric confidence
        req_proposed = RequirementNode(
            id="REQ-CONF-001",
            kind=RequirementKind.FUNCTIONAL,
            statement="System must log all administrative actions.",
            actor="admin",
            capability="audit_log",
            target="logs",
            confidence=0.99,
            epistemic_status=EpistemicStatus.PROPOSED,
            provenance=ProvenanceKind.SPECULATIVE
        )

        res = r_graph.add_requirement(req_proposed)

        # Must NOT downgrade EXPLICIT to PROPOSED!
        self.assertEqual(res.epistemic_status, EpistemicStatus.EXPLICIT, "EpistemicPrecedencePolicy MUST prevent EXPLICIT -> PROPOSED downgrade")
        self.assertEqual(res.provenance, ProvenanceKind.EXPLICIT, "EpistemicPrecedencePolicy MUST prevent EXPLICIT -> SPECULATIVE downgrade")
        self.assertEqual(res.confidence, 0.85, "Higher epistemic status confidence MUST be preserved")

    def test_behavior_graph_to_requirement_graph_evidence_lineage(self):
        """Integration Test: Compiling BehaviorGraph to RequirementGraph MUST preserve structured evidence without character splitting."""
        from behavior_graph import BehaviorGraph, BehaviorNode, BehaviorNodeType, EpistemicStatus, ProvenanceKind
        from requirement_ir import EvidenceItem
        
        b_graph = BehaviorGraph()
        b_graph.add_node(BehaviorNode(
            id="cmd_001",
            name="ApproveLoan",
            behavior_type=BehaviorNodeType.COMMAND,
            actor_id="manager",
            target_entity_id="loan_application",
            epistemic_status=EpistemicStatus.EXPLICIT,
            provenance=ProvenanceKind.EXPLICIT,
            confidence=0.95,
            evidence_ref="User explicitly requested loan approval workflow"
        ))

        r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)
        reqs = list(r_graph.nodes.values())
        self.assertGreaterEqual(len(reqs), 1)

        req = r_graph.nodes["REQ-001"]
        self.assertEqual(len(req.evidence), 1, "Requirement evidence MUST contain exactly 1 EvidenceItem, not character-split list!")
        self.assertIsInstance(req.evidence[0], EvidenceItem, "Evidence item MUST be a structured EvidenceItem instance")
        self.assertEqual(req.evidence[0].content, "User explicitly requested loan approval workflow")

    def test_normalize_evidence_boundary_variants(self):
        """Unit Test: normalize_evidence boundary handles legacy string, EvidenceItem, dict, list, and invalid quality inputs cleanly."""
        from requirement_ir import EvidenceItem, normalize_evidence

        # 1. String normalization
        ev_str = normalize_evidence("Grounded specification requirement")
        self.assertEqual(len(ev_str), 1)
        self.assertEqual(ev_str[0].content, "Grounded specification requirement")

        # 2. EvidenceItem normalization
        item = EvidenceItem(id="EV-1", content="Direct AST route", quality=0.85)
        ev_item = normalize_evidence(item)
        self.assertEqual(len(ev_item), 1)
        self.assertEqual(ev_item[0].id, "EV-1")

        # 3. Quality boundary clamping (0.0 <= quality <= 1.0)
        invalid_q_nan = EvidenceItem(id="EV-2", quality=float("nan"))
        self.assertEqual(invalid_q_nan.quality, 1.0)

        invalid_q_inf = EvidenceItem(id="EV-3", quality=float("inf"))
        self.assertEqual(invalid_q_inf.quality, 1.0)

        invalid_q_neg = EvidenceItem(id="EV-4", quality=-5.0)
        self.assertEqual(invalid_q_neg.quality, 0.0)

        invalid_q_high = EvidenceItem(id="EV-5", quality=999.0)
        self.assertEqual(invalid_q_high.quality, 1.0)


if __name__ == "__main__":
    unittest.main()
