"""
Unit Tests for BoundedContextBuilder and EngineeringSkillRegistry.
"""

import pytest
from orchestrator.models import (
    ReasoningMode,
    ModelTier,
    ArtifactType,
    ContextSliceSpec,
    OrchestrationStateSnapshot,
    RoutingDecision,
)
from orchestrator.context import BoundedContextBuilder
from orchestrator.skills import EngineeringSkillRegistry
from domain.models import Obligation
from domain.types import ObligationCategory, Criticality, ObligationStatus


def test_skill_registry_lookup_and_selection():
    """Verifies skill lookup by ID and selection by reasoning mode."""
    skill = EngineeringSkillRegistry.get("skill-tdd-verification")
    assert skill is not None
    assert skill.name == "Test-Driven Verification Playbook"
    assert "CAP_EXEC_TEST" in skill.required_capabilities

    selected_diag = EngineeringSkillRegistry.select_for_mode("DIAGNOSE")
    assert selected_diag is not None
    assert selected_diag.skill_id == "skill-systematic-debug"

    composed = EngineeringSkillRegistry.compose_skills_for_mode("VERIFY")
    assert len(composed) >= 2


def test_bounded_context_builder_slices_frontier_and_sanitizes_feedback():
    """Verifies that BoundedContextBuilder includes only active frontier and truncates diagnostics."""
    obl1 = Obligation(
        obligation_id="OBL-01",
        task_id="TASK-01",
        category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
        criticality=Criticality.HIGH,
        title="Active Obligation",
        description="Active description",
        status=ObligationStatus.OPEN,
    )
    obl2 = Obligation(
        obligation_id="OBL-02",
        task_id="TASK-01",
        category=ObligationCategory.SECURITY_INTEGRITY,
        criticality=Criticality.MEDIUM,
        title="Inactive Obligation",
        description="Inactive description",
        status=ObligationStatus.OPEN,
    )
    snap = OrchestrationStateSnapshot(
        task_id="TASK-01",
        source_sha="a" * 40,
        policy_version=1,
        obligations=(obl1, obl2),
        ready_obligation_ids=("OBL-01",),
    )
    decision = RoutingDecision(
        mode=ReasoningMode.IMPLEMENT,
        active_frontier_ids=("OBL-01",),
        selected_skills=(EngineeringSkillRegistry.get("skill-tdd-verification"),),
        target_provider_type="gemini",
        target_model_tier=ModelTier.CODE_FAST,
        reasoning_objective="Implement square function",
        required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
        expected_artifact_type=ArtifactType.CODE_PATCH,
        verification_requirement="Pytest sandbox run.",
        context_slice_spec=ContextSliceSpec(
            include_governance_header=True,
            target_obligation_ids=("OBL-01",),
            include_diagnostics=True,
            max_diagnostic_lines=10,
        ),
        rationale="Active frontier slice",
    )

    long_diagnostics = [f"Traceback error line {i}" for i in range(50)]
    agent_ctx = BoundedContextBuilder.build_agent_context(
        state=snap,
        decision=decision,
        session_id="SESS-TEST-CTX",
        repository_id="REPO-01",
        symbol_context="def square(x): pass",
        failure_diagnostics=long_diagnostics,
        prior_turn_summaries=["Turn 1 failed syntax", "Turn 2 executed test"],
    )

    assert agent_ctx.session_id == "SESS-TEST-CTX"
    assert len(agent_ctx.frontier_obligation_ids) == 1
    assert agent_ctx.frontier_obligation_ids[0] == "OBL-01"
    assert "Active Obligation" in agent_ctx.objective
    assert "Inactive Obligation" not in agent_ctx.objective
    assert "Test-Driven Verification Playbook" in agent_ctx.objective
    assert "def square(x): pass" in agent_ctx.objective
    # Verify diagnostic truncation (capped at 10)
    assert len(agent_ctx.verification_feedback) == 50
    assert "Traceback error line 9" in agent_ctx.objective
    assert "Traceback error line 45" not in agent_ctx.objective
