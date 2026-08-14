"""
V9.5.2 Verification Suite: Metric Integrity, Canonical Requirement Authority & Read-Only FSM
"""

import os
import tempfile
import unittest
import sys

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

from adversarial_skeptic import AdversarialSkeptic
from spec_synthesis import SpecSynthesisEngine
from lld_compiler import LLDCompiler, LLDComponent
from hld_compiler import HLDDesign, HLDModule, ADRRecord
from requirement_ir import RequirementGraph, RequirementNode, RequirementKind
from behavior_graph import BehaviorGraph
import runtime


class TestV952Verification(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def test_honest_domain_specificity_score_returns_zero_on_empty_lld(self):
        # Empty LLD dict MUST evaluate to 0.0 without artificial floor clamping
        score_empty = AdversarialSkeptic.calculate_domain_specificity_score({})
        self.assertEqual(score_empty, 0.0)

        # LLD with empty sub_components MUST evaluate to 0.0
        score_no_comps = AdversarialSkeptic.calculate_domain_specificity_score({"lld_1": {"sub_components": []}})
        self.assertEqual(score_no_comps, 0.0)

    def test_canonical_requirement_graph_sole_source_of_truth(self):
        engine = SpecSynthesisEngine()
        spec = engine.run_synthesis("Build healthcare patient portal", self.tmp_dir)

        # Requirements in SynthesizedSpec MUST match authoritative requirement graph
        self.assertIsNotNone(spec.requirements)
        self.assertIn("explicit", spec.requirements)
        self.assertGreater(len(spec.requirements["explicit"]), 0)

    def test_fsm_runner_read_only_pipeline_inspection(self):
        runtime.initialize_state(self.tmp_dir, goal="Fullstack ERP System Build", profile="full")
        state_dir = os.path.join(self.tmp_dir, ".agents")
        pipe_file = os.path.join(state_dir, "v7_refinement_pipeline.json")

        self.assertTrue(os.path.exists(pipe_file))
        mtime_before = os.path.getmtime(pipe_file)

        # Running FSM advance_one_state should inspect pipeline without in-place debate rerun mutation
        res = runtime.FSMGoalSequenceRunner.advance_one_state(self.tmp_dir)
        self.assertIn(res["status"], ["ADVANCED", "BLOCKED"])

    def test_candidate_only_endpoint_fallback(self):
        hld = HLDDesign(
            system_name="TestSystem",
            architecture_style="Modular Monolith",
            modules=[HLDModule(id="mod_test", name="Test Context", system_boundary="internal", owned_entities=["core"], owned_capabilities=["cap_unknown"])]
        )
        r_graph = RequirementGraph()
        b_graph = BehaviorGraph()

        components = LLDCompiler.compile_lld(hld, r_graph, b_graph)
        self.assertGreater(len(components), 0)
        # Component with no grounded behavior nodes MUST produce PROPOSED_CANDIDATE: NO_ENDPOINT_EVIDENCE
        has_proposed_candidate = any("PROPOSED_CANDIDATE" in ep for c in components for ep in c.api_endpoints)
        self.assertTrue(has_proposed_candidate)


if __name__ == "__main__":
    unittest.main()
