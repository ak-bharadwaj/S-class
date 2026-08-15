"""
S-Class V9.6 Hardening Suite Vector 4: Metamorphic Debate Engine Attack Suite
"""

import unittest
from architecture_debate import ArchitectureDebateEngine
from hld_compiler import HLDCompiler
from behavior_graph import BehaviorGraph
from requirement_ir import RequirementGraph


class TestV96MetamorphicDebate(unittest.TestCase):

    def test_metamorphic_irrelevant_text_insertion(self):
        """Metamorphic Property 1: Inserting irrelevant prose must NOT change settled ADR decisions."""
        r_graph = RequirementGraph()
        b_graph = BehaviorGraph()

        prompt_clean = "Build an enterprise portal with role-based access control and high availability zero downtime."
        hld1 = HLDCompiler.compile_hld(r_graph, b_graph, raw_request=prompt_clean)
        debate1 = ArchitectureDebateEngine.run_debate_cycle(hld1, r_graph, b_graph, raw_request=prompt_clean, is_debate_phase=True)

        prompt_noisy = prompt_clean + " The weather today is sunny. Bananas are rich in potassium and tropical fruits are yellow."
        hld2 = HLDCompiler.compile_hld(r_graph, b_graph, raw_request=prompt_noisy)
        debate2 = ArchitectureDebateEngine.run_debate_cycle(hld2, r_graph, b_graph, raw_request=prompt_noisy, is_debate_phase=True)

        # ADR count and decisions must be identical
        adrs1 = {a.id: a.decision for a in debate1.accepted_adrs}
        adrs2 = {a.id: a.decision for a in debate2.accepted_adrs}

        self.assertEqual(adrs1, adrs2, "Irrelevant prompt text insertion must NOT alter settled ADR decisions")

    def test_metamorphic_evidence_removal_drops_confidence(self):
        """Metamorphic Property 2: Removing critical grounding evidence MUST NOT increase confidence and must revert status to UNKNOWN/PROPOSED."""
        r_graph = RequirementGraph()
        b_graph = BehaviorGraph()

        prompt_grounded = "Build a microservice architecture with Kafka event bus, zero-trust OAuth2 authentication, and PostgreSQL read-replicas."
        hld_grounded = HLDCompiler.compile_hld(r_graph, b_graph, raw_request=prompt_grounded)
        debate_grounded = ArchitectureDebateEngine.run_debate_cycle(hld_grounded, r_graph, b_graph, raw_request=prompt_grounded, is_debate_phase=True)

        prompt_stripped = "Build a system."
        hld_stripped = HLDCompiler.compile_hld(r_graph, b_graph, raw_request=prompt_stripped)
        debate_stripped = ArchitectureDebateEngine.run_debate_cycle(hld_stripped, r_graph, b_graph, raw_request=prompt_stripped, is_debate_phase=True)

        conf_grounded = sum(a.confidence for a in debate_grounded.accepted_adrs) if debate_grounded.accepted_adrs else 0.0
        conf_stripped = sum(a.confidence for a in debate_stripped.accepted_adrs) if debate_stripped.accepted_adrs else 0.0

        self.assertLessEqual(conf_stripped, conf_grounded, "Stripping grounding evidence must NOT increase debate confidence")
        # Candidate ADRs in stripped prompt must remain in rejected_adrs marked PROPOSED
        for adr in debate_stripped.rejected_adrs:
            self.assertEqual(adr.status, "PROPOSED")


if __name__ == "__main__":
    unittest.main()
