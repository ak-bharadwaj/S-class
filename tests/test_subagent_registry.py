"""
Unit tests for sclass_subagent_registry.py (SubagentRegistry)
"""

import os
import json
import tempfile
import unittest
from sclass_subagent_registry import SubagentRegistry


class TestSubagentRegistry(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def test_all_8_subagents_registered(self):
        self.assertEqual(len(SubagentRegistry.SUBAGENTS), 8)
        self.assertIn("dss_governor", SubagentRegistry.SUBAGENTS)
        self.assertIn("dss_ui_ux", SubagentRegistry.SUBAGENTS)
        self.assertIn("dss_frontend_dev", SubagentRegistry.SUBAGENTS)
        self.assertIn("dss_backend_dev", SubagentRegistry.SUBAGENTS)
        self.assertIn("dss_db_architect", SubagentRegistry.SUBAGENTS)
        self.assertIn("dss_cso_v2", SubagentRegistry.SUBAGENTS)
        self.assertIn("dss_qa_frontend", SubagentRegistry.SUBAGENTS)
        self.assertIn("dss_user_alias_v2", SubagentRegistry.SUBAGENTS)

    def test_prepare_full_8_subagent_dispatch(self):
        res = SubagentRegistry.prepare_full_8_subagent_dispatch(
            goal_text="Build CSE Department ERP portal",
            fsm_phase="DEBATE",
            workspace_dir=self.test_dir
        )
        self.assertEqual(res["total_subagents_dispatched"], 8)
        self.assertTrue(res["concurrent_execution"])
        self.assertTrue(res["skill_discovery_active"])

        dispatch_receipt = os.path.join(self.test_dir, ".agents", "full_8_subagent_dispatch.json")
        self.assertTrue(os.path.exists(dispatch_receipt))

    def test_prepare_subagent_dispatch_non_ui_strips_irrelevant_skills(self):
        """Verifies that non-UI algorithmic tasks filter UI and unrequested enterprise skills across all 3 sources."""
        res = SubagentRegistry.prepare_full_8_subagent_dispatch(
            goal_text="Implement Red-Black Tree in Python",
            fsm_phase="CODING",
            workspace_dir=self.test_dir
        )
        self.assertEqual(res["task_domain"], "algorithm")

        # UI subagents should be on standby
        ui_agent_ids = {"dss_ui_ux", "dss_frontend_dev", "dss_qa_frontend", "dss_user_alias_v2"}
        for sa in res["subagents"]:
            if sa["subagent_id"] in ui_agent_ids:
                self.assertEqual(sa["status"], "STANDBY_NON_UI")
                self.assertEqual(len(sa["assigned_skills"]), 0)
                self.assertFalse(sa["find_skill_enabled"])
            else:
                self.assertEqual(sa["status"], "DISPATCHED_CONCURRENTLY")
                self.assertTrue(sa["find_skill_enabled"])

        # Dispatched backend / security / db subagents must NOT receive UI-pattern or unrequested ORM skills
        flagged_irrelevant_skills = [
            "dark-mode-theme-system",
            "toast-notification-system",
            "emil-pick-ui-library",
            "prisma-drizzle-orm"
        ]
        dispatched_agents = [s for s in res["subagents"] if s["status"] == "DISPATCHED_CONCURRENTLY"]
        for sa in dispatched_agents:
            for flagged in flagged_irrelevant_skills:
                self.assertNotIn(
                    flagged,
                    sa["assigned_skills"],
                    f"Irrelevant skill '{flagged}' must not be present in {sa['subagent_id']}"
                )


if __name__ == "__main__":
    unittest.main()
