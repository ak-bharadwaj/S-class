"""
Unit tests for sclass_grill.py (SpecGrillerEngine)
"""

import os
import json
import tempfile
import unittest
from sclass_grill import SpecGrillerEngine, GrillReport, ThreatVectorResult


class TestSpecGriller(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.agents_dir = os.path.join(self.test_dir, ".agents")
        os.makedirs(self.agents_dir, exist_ok=True)

    def test_grill_empty_specification(self):
        report = SpecGrillerEngine.grill_specification(workspace_dir=self.test_dir)
        self.assertIsInstance(report, GrillReport)
        self.assertFalse(report.overall_passed)
        self.assertGreater(report.critical_defects_found, 0)
        self.assertEqual(len(report.vector_results), 5)

    def test_grill_valid_specification(self):
        valid_blueprint = {
            "backend_spec": {
                "routes": [
                    {"method": "GET", "path": "/api/users", "dto": "UserResponseDTO"},
                    {"method": "POST", "path": "/api/users", "dto": "CreateUserDTO"}
                ],
                "middleware": ["authGuard", "zodValidation"],
                "async_transactions": True
            },
            "db_schema": {
                "tables": ["users", "posts"],
                "foreign_keys": ["posts.user_id -> users.id"],
                "indices": ["idx_posts_user_id"]
            },
            "frontend_layout": {
                "views": ["Dashboard", "UserProfile"],
                "loading_triggers": True,
                "disabled_states": True,
                "error_boundaries": True,
                "empty_state_fallbacks": True
            }
        }
        with open(os.path.join(self.agents_dir, "design_blueprint.json"), "w", encoding="utf-8") as f:
            json.dump(valid_blueprint, f)

        report = SpecGrillerEngine.grill_specification(workspace_dir=self.test_dir)
        self.assertTrue(report.overall_passed)
        self.assertEqual(report.critical_defects_found, 0)
        self.assertTrue(os.path.exists(os.path.join(self.agents_dir, "grill_report.json")))


if __name__ == "__main__":
    unittest.main()
