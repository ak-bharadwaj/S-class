"""
Unit tests for sclass_skill_orchestrator.py (SClassSkillOrchestrator & SkillTaxonomy)
"""

import os
import json
import tempfile
import unittest
from sclass_skill_orchestrator import SClassSkillOrchestrator, SkillTaxonomy


class TestSkillOrchestrator(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def test_taxonomy_skill_count(self):
        self.assertGreaterEqual(len(SkillTaxonomy.SKILLS), 30)
        self.assertIn("impeccable-craft", SkillTaxonomy.SKILLS)
        self.assertIn("impeccable-new-work", SkillTaxonomy.SKILLS)
        self.assertIn("taste-aesthetic", SkillTaxonomy.SKILLS)
        self.assertIn("taste-minimalist", SkillTaxonomy.SKILLS)
        self.assertIn("emil-apple-design", SkillTaxonomy.SKILLS)
        self.assertIn("emil-ask-sonner", SkillTaxonomy.SKILLS)
        self.assertIn("react-doctor", SkillTaxonomy.SKILLS)
        self.assertIn("zod-pydantic-contract", SkillTaxonomy.SKILLS)
        self.assertIn("auth-jwt-rbac", SkillTaxonomy.SKILLS)
        self.assertIn("prisma-drizzle-orm", SkillTaxonomy.SKILLS)
        self.assertIn("ci-cd-docker-deploy", SkillTaxonomy.SKILLS)

    def test_resolve_default_skills_in_coding_phase(self):
        skills = SClassSkillOrchestrator.resolve_active_skills(
            fsm_phase="CODING",
            goal_text="Build CSE Department ERP portal with attendance and marks tables",
            workspace_dir=self.test_dir
        )
        skill_ids = [s.id for s in skills]
        self.assertIn("frontend-design", skill_ids)
        self.assertIn("data-dense-ui", skill_ids)
        self.assertIn("data-visualization", skill_ids)
        self.assertNotIn("3d-webgl", skill_ids)  # Should NOT activate for standard tables

    def test_conditional_3d_activation(self):
        skills = SClassSkillOrchestrator.resolve_active_skills(
            fsm_phase="CODING",
            goal_text="Build CSE Department 3D lab map and course dependency graph",
            workspace_dir=self.test_dir
        )
        skill_ids = [s.id for s in skills]
        self.assertIn("3d-webgl", skill_ids)

    def test_skill_stack_receipt_file(self):
        SClassSkillOrchestrator.resolve_active_skills(
            fsm_phase="DESIGN",
            goal_text="Design CSE ERP",
            workspace_dir=self.test_dir
        )
        receipt_file = os.path.join(self.test_dir, ".agents", "active_skill_stack.json")
        self.assertTrue(os.path.exists(receipt_file))
        with open(receipt_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["fsm_phase"], "DESIGN")


if __name__ == "__main__":
    unittest.main()
