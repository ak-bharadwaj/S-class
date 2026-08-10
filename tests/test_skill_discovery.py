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


if __name__ == "__main__":
    unittest.main()
