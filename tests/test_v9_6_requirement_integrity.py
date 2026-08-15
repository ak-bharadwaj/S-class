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

        with self.assertRaises(CircularDependencyError):
            r_graph.add_dependency("REQ-002", "REQ-001")


if __name__ == "__main__":
    unittest.main()
