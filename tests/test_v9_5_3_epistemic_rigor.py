"""
S-Class V9.5.3 Verification Suite: Epistemic Rigor, Immutable Versioning & SSOT Requirement Pipeline
"""

import os
import json
import shutil
import tempfile
import unittest
from spec_compiler import SpecificationCompiler
from spec_synthesis import SpecSynthesisEngine, SynthesizedSpec, RequirementType
from hld_compiler import HLDCompiler, HLDDesign
from requirement_ir import RequirementGraph, RequirementNode, RequirementKind
from behavior_graph import BehaviorGraph
from architecture_debate import ArchitectureDebateEngine, DecisionOutcome
from artifact_governor import ArtifactGovernor

def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestV953EpistemicRigor(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_debate_phase_does_not_grant_pass_without_evidence(self):
        """Verifier 1: Debate phase MUST NOT grant PASS or lower epistemic standards without positive evidence."""
        r_graph = RequirementGraph()
        b_graph = BehaviorGraph()
        hld = HLDCompiler.compile_hld(r_graph, b_graph, raw_request="Build complex enterprise platform")

        # Debate under is_debate_phase=True
        debate_result = ArchitectureDebateEngine.run_debate_cycle(
            hld, r_graph, b_graph, raw_request="Build complex enterprise platform", is_debate_phase=True
        )

        # Without grounded evidence, ADRs must NOT be automatically promoted to ACCEPTED
        # Unconfirmed candidate ADRs remain in rejected_adrs marked PROPOSED
        for adr in debate_result.rejected_adrs:
            self.assertEqual(adr.status, "PROPOSED")
            self.assertIn(adr.epistemic_status.value, ["proposed", "unvalidated"])

    def test_immutable_versioned_pipeline_artifacts(self):
        """Verifier 2: Refinement compilation saves immutable versioned artifacts (v1.json, v2.json) with lineage hashes."""
        res_pipe1 = SpecificationCompiler.compile_v7_refinement_pipeline(
            raw_request="System Build V1", workspace_dir=self.test_dir, is_debate_phase=False
        )

        state_dir = os.path.join(self.test_dir, ".agents")
        v1_file = os.path.join(state_dir, "v7_refinement_pipeline_v1.json")
        self.assertTrue(os.path.exists(v1_file), "v7_refinement_pipeline_v1.json must exist")

        with open(v1_file, "r", encoding="utf-8") as f:
            v1_content = f.read()

        # Execute V2 refinement compilation with updated architectural requirements
        res_pipe2 = SpecificationCompiler.compile_v7_refinement_pipeline(
            raw_request="System Build V2 with independent microservices scaling for high throughput 10k requests", workspace_dir=self.test_dir, is_debate_phase=True
        )

        v2_file = os.path.join(state_dir, "v7_refinement_pipeline_v2.json")
        self.assertTrue(os.path.exists(v2_file), "v7_refinement_pipeline_v2.json must exist")

        with open(v1_file, "r", encoding="utf-8") as f:
            v1_content_after = f.read()

        # Invariant: V1 artifact is IMMUTABLE (content untouched by V2 refinement compilation)
        self.assertEqual(v1_content, v1_content_after, "v1 pipeline artifact must remain immutable")

        v2_data = load_json(v2_file)
        self.assertEqual(v2_data.get("version"), 2)
        self.assertEqual(v2_data.get("parent_version"), 1)
        self.assertIsNotNone(v2_data.get("parent_hash"), "v2 artifact must contain parent hash")

    def test_pure_requirement_graph_derivation(self):
        """Verifier 3: SynthesizedSpec.requirements is derived 100% directly from Authoritative RequirementGraph."""
        engine = SpecSynthesisEngine()
        spec = engine.run_synthesis("Implement driving school portal with student enrollment and instructor schedules", self.test_dir)

        pipe_file = os.path.join(self.test_dir, ".agents", "v7_refinement_pipeline.json")
        pipe_data = load_json(pipe_file)
        r_graph_nodes = pipe_data.get("requirement_graph", {}).get("nodes", {})

        spec_req_ids = {r["id"] for req_list in spec.requirements.values() for r in req_list}
        r_graph_ids = set(r_graph_nodes.keys()) if isinstance(r_graph_nodes, dict) else {r.get("id", "") for r in r_graph_nodes}

        # SynthesizedSpec requirements MUST equal the RequirementGraph node set
        self.assertEqual(spec_req_ids, r_graph_ids, "SynthesizedSpec requirements must strictly equal Authoritative RequirementGraph nodes")

    def test_no_speculative_hld_fallback_modules(self):
        """Verifier 4: HLDCompiler returns empty modules when no boundary evidence exists, avoiding arbitrary prompt noun module invention."""
        r_graph = RequirementGraph()
        b_graph = BehaviorGraph()

        # Prompt with arbitrary nouns ("secure aviation telemetry analysis platform")
        hld = HLDCompiler.compile_hld(r_graph, b_graph, raw_request="Build a secure aviation telemetry analysis platform")

        # Must NOT invent "Aviation Management Context" out of thin air
        self.assertEqual(len(hld.modules), 0, "HLDCompiler must not create speculative fallback modules without graph evidence")

    def test_single_pipeline_version_persistence_owner(self):
        """Invariant: Single logical debate/refinement step produces exactly ONE new version file when content changes, and 0 when identical."""
        res1 = SpecificationCompiler.compile_v7_refinement_pipeline(
            raw_request="System Build V1", workspace_dir=self.test_dir, is_debate_phase=False
        )
        state_dir = os.path.join(self.test_dir, ".agents")
        v_files1 = [f for f in os.listdir(state_dir) if f.startswith("v7_refinement_pipeline_v") and f.endswith(".json")]
        self.assertEqual(len(v_files1), 1, "Initial compilation produces v1.json")

        # Serializing identical result must NOT increment version (deduplication)
        SpecificationCompiler.save_versioned_pipeline_artifact(res1, self.test_dir)
        v_files1_dedup = [f for f in os.listdir(state_dir) if f.startswith("v7_refinement_pipeline_v") and f.endswith(".json")]
        self.assertEqual(len(v_files1_dedup), 1, "Identical serialization produces 0 new version files")

        # Compilation with new architectural content produces exactly v2.json
        res2 = SpecificationCompiler.compile_v7_refinement_pipeline(
            raw_request="System Build V2 with independent microservices scaling for high throughput 10k requests", workspace_dir=self.test_dir, is_debate_phase=True
        )
        v_files2 = [f for f in os.listdir(state_dir) if f.startswith("v7_refinement_pipeline_v") and f.endswith(".json")]
        self.assertEqual(len(v_files2), 2, "New content compilation produces exactly v2.json (1 version increment)")

        # Serializing V2 result again must NOT produce v3.json (deduplication)
        SpecificationCompiler.save_versioned_pipeline_artifact(res2, self.test_dir)
        v_files2_dedup = [f for f in os.listdir(state_dir) if f.startswith("v7_refinement_pipeline_v") and f.endswith(".json")]
        self.assertEqual(len(v_files2_dedup), 2, "Duplicate V2 serialization produces 0 new version files")

    def test_same_pipeline_result_serialized_twice_deduplicated(self):
        """Invariant: Hashing identical pipeline result twice produces zero duplicate version files."""
        res_pipe = SpecificationCompiler.compile_v7_refinement_pipeline(
            raw_request="System Build Deduplication Test", workspace_dir=self.test_dir, is_debate_phase=False
        )
        state_dir = os.path.join(self.test_dir, ".agents")
        v1_file = os.path.join(state_dir, "v7_refinement_pipeline_v1.json")
        self.assertTrue(os.path.exists(v1_file))

        # Explicitly call save_versioned_pipeline_artifact a second time on identical result
        path2 = SpecificationCompiler.save_versioned_pipeline_artifact(res_pipe, self.test_dir)

        # Must return existing v1_file path and NOT create v2
        self.assertEqual(path2, v1_file, "Second serialization of identical payload must return existing version path")
        v_files = [f for f in os.listdir(state_dir) if f.startswith("v7_refinement_pipeline_v") and f.endswith(".json")]
        self.assertEqual(len(v_files), 1, f"Expected 1 version file after duplicate save attempt, found {v_files}")


if __name__ == "__main__":
    unittest.main()
