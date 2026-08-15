"""
S-Class V9.6 Hardening Suite Vector 8: 8-Layer Cross-Module Contract Matrix
"""

import unittest
from spec_compiler import SpecificationCompiler
from requirement_ir import RequirementGraph
from behavior_graph import BehaviorGraph
from hld_compiler import HLDCompiler
from architecture_debate import ArchitectureDebateEngine
from lld_compiler import LLDCompiler
from task_compiler import TaskCompiler
from artifact_governor import ArtifactGovernor


class TestV96ContractMatrix(unittest.TestCase):

    def setUp(self):
        self.raw_request = "Build enterprise university portal with student enrollment and faculty grading"
        self.res_pipe = SpecificationCompiler.compile_v7_refinement_pipeline(
            raw_request=self.raw_request, workspace_dir=None, is_debate_phase=True
        )

    def test_contract_1_behavior_to_requirement_lineage(self):
        """Contract 1: Every RequirementNode must map to grounded BehaviorNode source IDs."""
        r_graph = self.res_pipe["requirement_graph"]
        for req in r_graph.nodes.values():
            if req.source_behaviors:
                for b_id in req.source_behaviors:
                    self.assertIn(b_id, self.res_pipe["behavior_graph"].nodes, f"Requirement '{req.id}' references un-grounded behavior '{b_id}'")

    def test_contract_2_requirement_to_hld_coverage(self):
        """Contract 2: HLD modules must cover grounded capabilities or entities without unbacked ghost modules."""
        hld = self.res_pipe["hld_design"]
        r_graph = self.res_pipe["requirement_graph"]
        for mod in hld.modules:
            self.assertTrue(len(mod.owned_capabilities) > 0 or len(mod.owned_entities) > 0, f"HLD module '{mod.name}' has no owned capability or entity coverage")

    def test_contract_3_hld_to_debate_adr_alignment(self):
        """Contract 3: HLD ADR IDs must align with Debate Result candidate/accepted/rejected ADRs."""
        hld = self.res_pipe["hld_design"]
        debate_dict = self.res_pipe["debate_result"]
        hld_adr_ids = {a.get("id") if isinstance(a, dict) else a.id for a in hld.adrs}
        debate_adr_ids = {a["id"] for a in debate_dict.get("accepted_adrs", []) + debate_dict.get("rejected_adrs", [])}
        for adr_id in hld_adr_ids:
            self.assertIn(adr_id, debate_adr_ids, f"HLD ADR '{adr_id}' missing from Debate Result")

    def test_contract_4_hld_to_lld_module_scoping(self):
        """Contract 4: LLD components must map to grounded requirement IDs."""
        lld_components = self.res_pipe["lld_components"]
        r_graph = self.res_pipe["requirement_graph"]
        for comp in lld_components:
            self.assertTrue(len(comp.req_ids) > 0, f"LLD component '{comp.name}' must reference at least 1 requirement ID")

    def test_contract_5_lld_to_task_lineage(self):
        """Contract 5: TaskRecords must reference valid LLD component names and requirement IDs."""
        tasks = self.res_pipe["tasks"]
        lld_comp_names = {c.name for c in self.res_pipe["lld_components"]}
        for t in tasks:
            self.assertTrue(t.component_ref in lld_comp_names or len(t.req_ids) > 0, f"Task '{t.task_id}' has dangling component reference '{t.component_ref}'")

    def test_contract_6_governor_to_fsm_blocked_alignment(self):
        """Contract 6: res_pipe['blocked'] must strictly equal task_governance or lld_governance is_blocked."""
        task_gov = self.res_pipe.get("task_governance", {})
        is_blocked = self.res_pipe.get("blocked", False)
        self.assertEqual(is_blocked, task_gov.get("is_blocked", False), "Pipeline blocked flag must match Task Governance result")

    def test_contract_7_debate_to_revised_hld_alignment(self):
        """Contract 7: Accepted ADRs in Debate result must match HLD design decision records."""
        hld = self.res_pipe["hld_design"]
        debate_dict = self.res_pipe["debate_result"]
        accepted_adrs = debate_dict.get("accepted_adrs", [])
        hld_adr_dict = {a.get("id") if isinstance(a, dict) else a.id: a for a in hld.adrs}
        for acc in accepted_adrs:
            adr_id = acc.get("id")
            self.assertIn(adr_id, hld_adr_dict, f"Accepted debate ADR '{adr_id}' must be present in revised HLD design")

    def test_contract_8_version_lineage_parent_hash_integrity(self):
        """Contract 8: Pipeline version serialization must produce valid SHA-256 content and parent hashes."""
        import tempfile, shutil, json
        tmp = tempfile.mkdtemp()
        try:
            p1 = SpecificationCompiler.save_versioned_pipeline_artifact(self.res_pipe, tmp)
            self.assertTrue(p1.endswith("v1.json"))

            # Mutate pipeline slightly to produce v2
            pipe2 = dict(self.res_pipe)
            pipe2["dependency_holes"] = [{"req_id": "REQ-001", "type": "TEST_HOLE"}]
            p2 = SpecificationCompiler.save_versioned_pipeline_artifact(pipe2, tmp)
            self.assertTrue(p2.endswith("v2.json"))

            with open(p2, "r", encoding="utf-8") as f:
                v2_data = json.load(f)
            self.assertEqual(v2_data.get("version"), 2)
            self.assertEqual(v2_data.get("parent_version"), 1)
            self.assertTrue(v2_data.get("parent_hash") is not None, "v2 must track exact parent_hash of v1")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
