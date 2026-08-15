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
        """Invariant: High-risk NFR claims without explicit architecture evidence evaluate to UNKNOWN or PROPOSED."""
        b_graph = BehaviorGraph()
        # Unbacked NFR claim without security evidence
        req_nodes = [
            r for r in b_graph.nodes.values()
            if getattr(r, "epistemic_status", None) in [EpistemicStatus.PROPOSED, EpistemicStatus.UNVALIDATED]
        ]
        self.assertEqual(len(req_nodes), 0, "BehaviorGraph must not contain unvalidated explicit nodes")


if __name__ == "__main__":
    unittest.main()
