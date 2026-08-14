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

    def test_concurrent_same_content_deduplication(self):
        """Invariant: 8 concurrent workers saving the exact SAME content produce exactly 1 version file (v1.json)."""
        from concurrent.futures import ThreadPoolExecutor

        state_dir = os.path.join(self.test_dir, ".agents")
        num_threads = 8

        # Compile single shared payload
        single_pipe = SpecificationCompiler.compile_v7_refinement_pipeline(
            raw_request="Concurrent Same Content Build Request", workspace_dir=None, is_debate_phase=False
        )

        def worker_save(thread_idx: int):
            return SpecificationCompiler.save_versioned_pipeline_artifact(single_pipe, self.test_dir)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_save, i) for i in range(num_threads)]
            saved_paths = [f.result() for f in futures]

        v_files = sorted([f for f in os.listdir(state_dir) if f.startswith("v7_refinement_pipeline_v") and f.endswith(".json")])
        self.assertEqual(len(v_files), 1, f"Concurrent identical save attempts must produce exactly 1 version file, found {v_files}")
        v1_file = os.path.join(state_dir, "v7_refinement_pipeline_v1.json")
        for p in saved_paths:
            self.assertEqual(p, v1_file, "All concurrent workers saving identical content must receive v1.json path")

    def test_concurrent_pipeline_version_allocation(self):
        """Invariant: Concurrent save_versioned_pipeline_artifact calls allocate version numbers atomically with FileLock."""
        from concurrent.futures import ThreadPoolExecutor
        import hashlib

        state_dir = os.path.join(self.test_dir, ".agents")
        num_threads = 8

        # Prepare 8 distinct pipeline payloads upfront without saving
        res_pipes = [
            SpecificationCompiler.compile_v7_refinement_pipeline(
                raw_request=f"Concurrent System Build Request Thread #{i} with microservice {i}",
                workspace_dir=None,
                is_debate_phase=False
            )
            for i in range(num_threads)
        ]

        def worker_save(thread_idx: int):
            return SpecificationCompiler.save_versioned_pipeline_artifact(res_pipes[thread_idx], self.test_dir)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_save, i) for i in range(num_threads)]
            saved_paths = [f.result() for f in futures]

        v_files = sorted([f for f in os.listdir(state_dir) if f.startswith("v7_refinement_pipeline_v") and f.endswith(".json")])

        # Verify no version collisions occurred (all version files v1..vN exist sequentially)
        version_numbers = sorted([int(f.replace("v7_refinement_pipeline_v", "").replace(".json", "")) for f in v_files])
        self.assertEqual(version_numbers, list(range(1, len(version_numbers) + 1)), "Version numbers must be strictly sequential without collisions or skips")

        # Verify parent lineage integrity for every file v2..vN
        for v_num in range(2, len(version_numbers) + 1):
            curr_file = os.path.join(state_dir, f"v7_refinement_pipeline_v{v_num}.json")
            parent_file = os.path.join(state_dir, f"v7_refinement_pipeline_v{v_num - 1}.json")
            curr_data = load_json(curr_file)
            with open(parent_file, "rb") as pf:
                expected_parent_hash = hashlib.sha256(pf.read()).hexdigest()
            self.assertEqual(curr_data.get("parent_version"), v_num - 1)
            self.assertEqual(curr_data.get("parent_hash"), expected_parent_hash, f"v{v_num} parent_hash must strictly match SHA-256 digest of v{v_num - 1}")

    def test_long_held_lock_live_owner_protection(self):
        """Invariant: A live lock owner holding FileLock beyond stale_ttl is NEVER evicted by competing workers."""
        from runtime import FileLock
        import time, threading

        state_dir = os.path.join(self.test_dir, ".agents")
        os.makedirs(state_dir, exist_ok=True)
        lock_path = os.path.join(state_dir, ".pipeline_version.lock")

        acquired_event = threading.Event()
        competer_blocked = [True]

        def long_holding_owner():
            # Set a very short stale_ttl (0.1s) so age immediately exceeds stale_ttl
            with FileLock(lock_path, stale_ttl=0.1):
                acquired_event.set()
                time.sleep(0.4) # Hold lock past stale_ttl while process (current thread/PID) is ALIVE

        def competing_worker():
            acquired_event.wait(timeout=2.0)
            # Try to acquire lock with short timeout (0.15s)
            start_compete = time.time()
            try:
                with FileLock(lock_path, timeout=0.15, stale_ttl=0.1):
                    competer_blocked[0] = False
            except TimeoutError:
                competer_blocked[0] = True

        t_owner = threading.Thread(target=long_holding_owner)
        t_competer = threading.Thread(target=competing_worker)

        t_owner.start()
        t_competer.start()

        t_owner.join()
        t_competer.join()

        # Competer MUST have timed out and failed to steal the lock from the live owner
        self.assertTrue(competer_blocked[0], "Competing worker must NOT steal FileLock from live owner even if lock age > stale_ttl")
        self.assertFalse(os.path.exists(lock_path), "Lock file must be released cleanly after live owner completes")


if __name__ == "__main__":
    unittest.main()
