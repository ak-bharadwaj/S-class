"""
Unit tests for S-Class V12 Dynamic Skill Auto-Loader & Platform Projection Engine
(tests/test_skill_auto_loader.py)
"""

import os
import tempfile
import pytest
from skill_auto_loader import SkillAutoLoader, SkillDefinition


def test_skill_parser():
    sample_skill = """---
name: "test-playbook"
description: "Sample test engineering playbook"
triggers:
  file_patterns: ["*.py", "tests/*"]
  fsm_phases: ["CODING", "VERIFYING"]
  intent_keywords: ["test", "fuzz"]
token_budget: 800
dependencies: ["base-skill"]
---

# Sample Playbook
Execute tests diligently.
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_file = os.path.join(tmpdir, "SKILL.md")
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(sample_skill)

        skill = SkillAutoLoader.parse_skill_markdown(skill_file)
        assert skill is not None
        assert skill.name == "test-playbook"
        assert skill.description == "Sample test engineering playbook"
        assert skill.token_budget == 800
        assert "CODING" in skill.triggers["fsm_phases"]
        assert "base-skill" in skill.dependencies
        assert "Execute tests diligently." in skill.content


def test_detect_active_skills_and_dependencies():
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = os.path.join(tmpdir, ".agents", "skills")
        os.makedirs(os.path.join(skills_dir, "base"), exist_ok=True)
        os.makedirs(os.path.join(skills_dir, "derived"), exist_ok=True)

        with open(os.path.join(skills_dir, "base", "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("""---
name: "base-skill"
description: "Base dependency skill"
triggers:
  fsm_phases: ["ANALYSIS"]
token_budget: 500
dependencies: []
---
Base content
""")

        with open(os.path.join(skills_dir, "derived", "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("""---
name: "derived-skill"
description: "Derived skill with dependency"
triggers:
  fsm_phases: ["CODING"]
  intent_keywords: ["refactor"]
token_budget: 800
dependencies: ["base-skill"]
---
Derived content
""")

        loader = SkillAutoLoader(workspace_dir=tmpdir, skills_dir=skills_dir)
        assert len(loader.skills) == 2

        # Trigger derived skill via phase & keyword
        active = loader.detect_active_skills(current_phase="CODING", goal_text="please refactor this module")
        names = [s.name for s in active]
        assert "derived-skill" in names
        assert "base-skill" in names  # pulled in by dependency resolution


def test_project_skills_to_platforms():
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = SkillAutoLoader(workspace_dir=tmpdir)
        skill = SkillDefinition(
            name="tdd-workflow",
            description="Strict TDD playbook",
            triggers={"file_patterns": ["**/*test*.py"]},
            token_budget=600,
            dependencies=[],
            content="1. Red, 2. Green, 3. Refactor",
            file_path="",
        )

        res = loader.project_skills_to_platforms([skill], workspace_dir=tmpdir)
        assert len(res["cursor"]) == 1
        assert os.path.exists(res["cursor"][0])
        assert res["cursor"][0].endswith("tdd-workflow.mdc")

        assert len(res["claude"]) == 1
        assert os.path.exists(res["claude"][0])
        assert res["claude"][0].endswith("tdd-workflow.md")

        assert len(res["agents_md"]) == 1
        assert os.path.exists(res["agents_md"][0])

        assert len(res["gemini_md"]) == 1
        assert os.path.exists(res["gemini_md"][0])

        with open(res["cursor"][0], "r", encoding="utf-8") as f:
            cursor_content = f.read()
            assert "description: \"Strict TDD playbook\"" in cursor_content
            assert "1. Red, 2. Green, 3. Refactor" in cursor_content
