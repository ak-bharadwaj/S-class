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

    def test_metamorphic_contradict_critical_requirement_triggers_rejection(self):
        """Metamorphic Property 5: Contradicting a critical requirement forces debate rejection or non-PASS outcome."""
        from requirement_ir import RequirementNode, RequirementKind
        from behavior_graph import EpistemicStatus

        r_graph = RequirementGraph()
        b_graph = BehaviorGraph()

        # Add explicit auth requirement
        r1 = RequirementNode(
            id="REQ-AUTH-001",
            kind=RequirementKind.FUNCTIONAL,
            statement="System must require OAuth2 authentication.",
            actor="user",
            capability="authenticate",
            target="system",
            epistemic_status=EpistemicStatus.EXPLICIT
        )
        r_graph.add_requirement(r1)

        # Add contradictory requirement under different ID
        r2 = RequirementNode(
            id="REQ-AUTH-002",
            kind=RequirementKind.FUNCTIONAL,
            statement="System must disable authentication entirely and grant public anonymous access.",
            actor="anonymous",
            capability="bypass_auth",
            target="system",
            epistemic_status=EpistemicStatus.EXPLICIT
        )
        r_graph.add_requirement(r2)

        hld = HLDCompiler.compile_hld(r_graph, b_graph, raw_request="Build secure access portal")
        d = ArchitectureDebateEngine.run_debate_cycle(hld, r_graph, b_graph, raw_request="Build secure access portal", is_debate_phase=True)

        # Contradictory security requirements must produce rejected ADRs or non-PASS sufficiency
        self.assertTrue(len(d.rejected_adrs) > 0 or len(d.required_revisions) > 0, "Contradictory security requirements MUST trigger candidate rejection or required revisions")

    def test_metamorphic_increase_throughput_requirement_increases_scale_risk(self):
        """Metamorphic Property 6: Increasing throughput requirement to 100k ev/s CANNOT decrease scale risk rating."""
        from requirement_ir import RequirementNode, RequirementKind, NFRCategory
        from behavior_graph import EpistemicStatus

        # Baseline graph
        r_base = RequirementGraph()
        b_base = BehaviorGraph()
        hld1 = HLDCompiler.compile_hld(r_base, b_base, raw_request="Build internal batch reporting service")
        d1 = ArchitectureDebateEngine.run_debate_cycle(hld1, r_base, b_base, raw_request="Build internal batch reporting service", is_debate_phase=True)

        # High-scale graph
        r_scale = RequirementGraph()
        b_scale = BehaviorGraph()
        high_scale_nfr = RequirementNode(
            id="REQ-PERF-999",
            kind=RequirementKind.NON_FUNCTIONAL,
            nfr_category=NFRCategory.PERFORMANCE,
            statement="System must handle 100k events/sec zero-downtime streaming.",
            actor="system",
            capability="stream_processing",
            target="cluster",
            epistemic_status=EpistemicStatus.EXPLICIT,
            confidence=0.9
        )
        r_scale.add_requirement(high_scale_nfr)
        hld2 = HLDCompiler.compile_hld(r_scale, b_scale, raw_request="Build internal batch reporting service with 100k events/sec streaming")
        d2 = ArchitectureDebateEngine.run_debate_cycle(hld2, r_scale, b_scale, raw_request="Build internal batch reporting service with 100k events/sec streaming", is_debate_phase=True)

        # High-scale NFR must produce more rejected candidate ADRs or required revisions than baseline
        challenges_base = sum(len(rec.sufficiency_gate_result.get("missing_evidence", [])) for rec in d1.decision_records)
        challenges_scale = sum(len(rec.sufficiency_gate_result.get("missing_evidence", [])) for rec in d2.decision_records)

        self.assertGreaterEqual(challenges_scale, challenges_base, "High-scale NFR requirement CANNOT decrease missing evidence challenges")


if __name__ == "__main__":
    unittest.main()
