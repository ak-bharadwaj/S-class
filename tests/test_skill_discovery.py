"""
Unit tests for sclass_skill_discovery.py (SkillDiscoveryEngine)
"""

import os
import json
import tempfile
import unittest
from sclass_skill_discovery import SkillDiscoveryEngine


class TestSkillDiscovery(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def test_find_and_bind_required_skills(self):
        res = SkillDiscoveryEngine.find_and_bind_required_skills(
            goal_text="Build CSE Department ERP with 3d lab map, animations, and taste skill styling",
            workspace_dir=self.test_dir
        )
        self.assertEqual(res["status"], "DISCOVERED_AND_BOUND")
        self.assertGreater(res["discovered_skills_count"], 0)
        self.assertIn("3d-webgl", res["discovered_skills"])

        receipt_file = os.path.join(self.test_dir, ".agents", "skill_discovery_receipt.json")
        self.assertTrue(os.path.exists(receipt_file))

    def test_auto_connect_workspace_skills(self):
        # Create dummy workspace skill directory
        skills_dir = os.path.join(self.test_dir, ".agents", "skills", "custom-animation")
        os.makedirs(skills_dir, exist_ok=True)
        with open(os.path.join(skills_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: custom-animation\ndescription: Custom spring animation and transition skill for React UI\n---\n# Custom Animation\n")

        res = SkillDiscoveryEngine.auto_connect_workspace_skills(workspace_dir=self.test_dir)
        self.assertEqual(res["connected_count"], 1)
        self.assertEqual(res["connected_skills"][0]["skill_id"], "custom-animation")
        self.assertEqual(res["connected_skills"][0]["recommended_agent_id"], "dss_ui_ux")
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, ".agents", "skill_auto_connection_receipt.json")))


if __name__ == "__main__":
    unittest.main()
