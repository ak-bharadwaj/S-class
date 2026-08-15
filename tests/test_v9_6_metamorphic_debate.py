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

    def test_metamorphic_irrelevant_text_reordering(self):
        """Metamorphic Property 3: Reordering irrelevant prompt sentences must NOT change settled ADR decisions."""
        r_graph = RequirementGraph()
        b_graph = BehaviorGraph()

        p1 = "Build healthcare record portal with HIPAA compliance. Bananas are yellow. The sun sets in the west."
        p2 = "The sun sets in the west. Build healthcare record portal with HIPAA compliance. Bananas are yellow."

        hld1 = HLDCompiler.compile_hld(r_graph, b_graph, raw_request=p1)
        d1 = ArchitectureDebateEngine.run_debate_cycle(hld1, r_graph, b_graph, raw_request=p1, is_debate_phase=True)

        hld2 = HLDCompiler.compile_hld(r_graph, b_graph, raw_request=p2)
        d2 = ArchitectureDebateEngine.run_debate_cycle(hld2, r_graph, b_graph, raw_request=p2, is_debate_phase=True)

        adrs1 = {a.id: a.decision for a in d1.accepted_adrs}
        adrs2 = {a.id: a.decision for a in d2.accepted_adrs}
        self.assertEqual(adrs1, adrs2, "Reordering irrelevant prompt prose must NOT alter settled ADR decisions")

    def test_metamorphic_security_evidence_removal_blocks_security_gate(self):
        """Metamorphic Property 4: Removing security arch evidence reverts security evaluation to UNKNOWN/PROPOSED."""
        from requirement_ir import RequirementNode, RequirementKind, NFRCategory
        from behavior_graph import EpistemicStatus

        r_graph = RequirementGraph()
        b_graph = BehaviorGraph()

        sec_req = RequirementNode(
            id="REQ-SEC-001",
            kind=RequirementKind.NON_FUNCTIONAL,
            nfr_category=NFRCategory.SECURITY,
            statement="System must enforce zero-trust token encryption.",
            actor="admin",
            capability="encrypt_tokens",
            target="tokens",
            epistemic_status=EpistemicStatus.EXPLICIT,
            evidence=None
        )
        r_graph.add_requirement(sec_req)

        hld = HLDCompiler.compile_hld(r_graph, b_graph, raw_request="Build basic admin panel")
        d = ArchitectureDebateEngine.run_debate_cycle(hld, r_graph, b_graph, raw_request="Build basic admin panel", is_debate_phase=True)

        # Without security evidence, decision sufficiency gate in decision_records MUST NOT evaluate to PASS
        for rec in d.decision_records:
            status = rec.sufficiency_gate_result.get("status")
            self.assertNotEqual(status, "PASS", "Security requirement without architecture evidence must NOT pass decision sufficiency gate")


if __name__ == "__main__":
    unittest.main()
