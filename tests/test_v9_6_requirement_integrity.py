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

        # 3. Valid Quality preservation
        valid_item = EvidenceItem(id="EV-2", quality=0.75)
        self.assertEqual(valid_item.quality, 0.75)

    def test_fail_closed_evidence_integrity_adversarial(self):
        """Adversarial Falsification Test: Malformed/corrupted quality or provenance MUST fail closed (quality=0.0, provenance=INVALID, TypeError on unsupported objects)."""
        from requirement_ir import EvidenceItem, normalize_evidence
        from domain_primitives import ProvenanceKind

        # 1. NaN quality -> quality=0.0, provenance=INVALID
        ev_nan = EvidenceItem(id="EV-NAN", quality=float("nan"))
        self.assertEqual(ev_nan.quality, 0.0, "NaN quality MUST fail closed to 0.0!")
        self.assertEqual(ev_nan.provenance, ProvenanceKind.INVALID, "NaN quality MUST convert provenance to INVALID!")

        # 2. Inf quality -> quality=0.0, provenance=INVALID
        ev_inf = EvidenceItem(id="EV-INF", quality=float("inf"))
        self.assertEqual(ev_inf.quality, 0.0, "Inf quality MUST fail closed to 0.0!")
        self.assertEqual(ev_inf.provenance, ProvenanceKind.INVALID)

        # 3. Out-of-bounds negative quality -> quality=0.0, provenance=INVALID
        ev_neg = EvidenceItem(id="EV-NEG", quality=-5.0)
        self.assertEqual(ev_neg.quality, 0.0)
        self.assertEqual(ev_neg.provenance, ProvenanceKind.INVALID)

        # 4. Out-of-bounds high quality -> quality=0.0, provenance=INVALID
        ev_high = EvidenceItem(id="EV-HIGH", quality=99.0)
        self.assertEqual(ev_high.quality, 0.0)
        self.assertEqual(ev_high.provenance, ProvenanceKind.INVALID)

        # 5. Invalid string quality -> quality=0.0, provenance=INVALID
        ev_str_q = EvidenceItem(id="EV-STR", quality="garbage")
        self.assertEqual(ev_str_q.quality, 0.0)
        self.assertEqual(ev_str_q.provenance, ProvenanceKind.INVALID)

        # 6. Invalid provenance string -> provenance=INVALID, quality=0.0
        ev_prov = EvidenceItem.from_dict({"id": "EV-PROV", "provenance": "corrupted_garbage_provenance"})
        self.assertEqual(ev_prov.provenance, ProvenanceKind.INVALID, "Invalid provenance string MUST resolve to INVALID!")
        self.assertEqual(ev_prov.quality, 0.0, "Invalid provenance string MUST zero out quality!")

        # 7. Unsupported arbitrary object -> TypeError
        class ArbitraryObject:
            pass

        with self.assertRaises(TypeError):
            normalize_evidence(ArbitraryObject())


if __name__ == "__main__":
    unittest.main()
