"""
Unit Tests for S-Class 9-Category Engineering Skill Ecosystem.
"""

import pytest
from orchestrator.models import SkillCategory, ArtifactType
from orchestrator.skills import EngineeringSkillRegistry


def test_all_nine_categories_represented_in_registry():
    """Verifies that all 9 canonical skill categories are populated in the registry."""
    categories_found = set()
    for skill in EngineeringSkillRegistry.all_skills():
        categories_found.add(skill.category)

    for cat in SkillCategory:
        assert cat in categories_found, f"Category {cat} missing from registry"


def test_skill_attributes_and_procedures():
    """Verifies that skills define concrete guidelines, capabilities, and expected artifact outputs."""
    tdd = EngineeringSkillRegistry.get("skill-tdd-verification")
    assert tdd is not None
    assert tdd.category == SkillCategory.CORE_ENGINEERING
    assert "CAP_EXEC_TEST" in tdd.required_capabilities
    assert tdd.expected_artifact_type == ArtifactType.TEST_HARNESS
    assert len(tdd.guidelines) >= 2

    debug = EngineeringSkillRegistry.get("skill-systematic-debug")
    assert debug is not None
    assert debug.category == SkillCategory.DIAGNOSIS
    assert debug.expected_artifact_type == ArtifactType.ROOT_CAUSE_DIAGNOSIS


def test_compose_skills_for_different_modes_and_contexts():
    """Verifies multi-skill composition across modes, task domains, and security profiles."""
    diag_skills = EngineeringSkillRegistry.compose_skills_for_mode("DIAGNOSE", has_refutation=True)
    diag_ids = [s.skill_id for s in diag_skills]
    assert "skill-systematic-debug" in diag_ids
    assert "skill-traceback-isolation" in diag_ids

    fintech_sec_skills = EngineeringSkillRegistry.compose_skills_for_mode(
        "IMPLEMENT",
        task_category="FINTECH / LEDGER",
        is_security_critical=True,
    )
    fintech_ids = [s.skill_id for s in fintech_sec_skills]
    assert "skill-tdd-verification" in fintech_ids
    assert "skill-fintech-ledger-invariance" in fintech_ids
    assert "skill-boundary-sanitization" in fintech_ids
