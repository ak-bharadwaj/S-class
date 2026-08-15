"""
S-Class V9.6 Hardening Suite Vector 1: Adversarial Grounding & Misleading Terminology Isolation
"""

import unittest
from spec_synthesis import SpecSynthesisEngine, RequirementType
from hld_compiler import HLDCompiler
from behavior_graph import BehaviorGraph, EpistemicStatus
from requirement_ir import RequirementGraph


class TestV96AdversarialGrounding(unittest.TestCase):

    def test_ambiguous_minimal_prompt_evaluation(self):
        """Invariant: Ambiguous/minimal prompts ('Make app better') must NOT invent speculative entities or roles."""
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        try:
            engine = SpecSynthesisEngine()
            spec = engine.run_synthesis("Make the system better and optimize UI", workspace_dir=tmp)

            # Unsupported assumptions must NOT be marked EXPLICIT or CONFIRMED
            for cat, reqs in spec.requirements.items():
                for r in reqs:
                    if isinstance(r, dict):
                        req_type = r.get("type")
                        self.assertNotEqual(req_type, "EXPLICIT", f"Requirement '{r.get('id')}' must not be EXPLICIT without prompt evidence")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_deceptive_noun_verb_isolation(self):
        """Invariant: Deceptive adjectives/verbs ('fast', 'quick', 'make', 'view') must not be extracted as primary domain entities."""
        r_graph = RequirementGraph()
        b_graph = BehaviorGraph()
        hld = HLDCompiler.compile_hld(r_graph, b_graph, raw_request="The system should quickly make fast views and code accesses")

        # Speculative fallback modules must be 0
        self.assertEqual(len(hld.modules), 0, "Deceptive nouns/verbs must not create speculative bounded context modules")

    def test_unsupported_nfr_remains_unconfirmed(self):
        """Invariant: High-risk NFR claims (100k events/sec zero-downtime) without explicit architecture evidence evaluate to UNKNOWN or PROPOSED, NEVER PASS or CONFIRMED."""
        from requirement_ir import RequirementNode, RequirementKind, NFRCategory
        from architecture_debate import ArchitectureDebateEngine

        r_graph = RequirementGraph()
        b_graph = BehaviorGraph()

        # Add unbacked high-scale NFR requirement to graph
        unbacked_nfr = RequirementNode(
            id="REQ-NFR-999",
            kind=RequirementKind.NON_FUNCTIONAL,
            nfr_category=NFRCategory.PERFORMANCE,
            statement="System must process 100k events/sec with zero downtime across multi-region clusters.",
            actor="system",
            capability="high_throughput_ingestion",
            target="cluster",
            epistemic_status=EpistemicStatus.PROPOSED,
            confidence=0.3,
            evidence=None
        )
        r_graph.add_requirement(unbacked_nfr)

        # Compile HLD with minimal unbacked prompt
        hld = HLDCompiler.compile_hld(r_graph, b_graph, raw_request="Build basic internal dashboard")
        debate = ArchitectureDebateEngine.run_debate_cycle(hld, r_graph, b_graph, raw_request="Build basic internal dashboard", is_debate_phase=True)

        # High-scale NFR requirement without grounded architecture evidence must NOT produce accepted CONFIRMED ADR
        for adr in debate.accepted_adrs:
            self.assertNotEqual(adr.status, "CONFIRMED", f"ADR '{adr.id}' must not be CONFIRMED without architecture evidence")

        # Must NOT grant PASS for unbacked NFR
        self.assertTrue(len(debate.rejected_adrs) > 0 or debate.decision_sufficiency != "PASS", "Debate cycle must NOT grant PASS for unbacked 100k events/sec NFR requirement")


if __name__ == "__main__":
    unittest.main()
