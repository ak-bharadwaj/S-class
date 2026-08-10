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


if __name__ == "__main__":
    unittest.main()
