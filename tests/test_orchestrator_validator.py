"""
Unit Tests for PlanArtifactValidator.
"""

import pytest
from orchestrator.models import StrategicPlanArtifact, PlanStage
from orchestrator.validator import PlanArtifactValidator
from planner.models import PlanStatus
from domain.models import Obligation
from domain.types import ObligationCategory, Criticality, ObligationStatus


@pytest.fixture
def sample_obligations():
    obl1 = Obligation(
        obligation_id="OBL-VAL-01",
        task_id="TASK-VAL",
        category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
        criticality=Criticality.HIGH,
        title="Obligation 1",
        description="Desc 1",
        status=ObligationStatus.OPEN,
    )
    obl2 = Obligation(
        obligation_id="OBL-VAL-02",
        task_id="TASK-VAL",
        category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
        criticality=Criticality.MEDIUM,
        title="Obligation 2",
        description="Desc 2",
        status=ObligationStatus.OPEN,
    )
    return {"OBL-VAL-01": obl1, "OBL-VAL-02": obl2}


def test_validator_accepts_valid_plan(sample_obligations):
    """Verifies that a well-formed acyclic plan transitions to VALIDATED."""
    stage1 = PlanStage(
        stage_id="STAGE-1",
        title="Stage 1",
        target_obligation_ids=("OBL-VAL-01",),
        prerequisite_stage_ids=(),
        description="Do obl 1",
        verification_gate="Test gate 1",
        evidence_types_required=("D6_EXECUTION_OBSERVATION",),
    )
    stage2 = PlanStage(
        stage_id="STAGE-2",
        title="Stage 2",
        target_obligation_ids=("OBL-VAL-02",),
        prerequisite_stage_ids=("STAGE-1",),
        description="Do obl 2",
        verification_gate="Test gate 2",
        evidence_types_required=("D6_EXECUTION_OBSERVATION",),
    )
    plan = StrategicPlanArtifact(
        plan_id="PLAN-001",
        task_id="TASK-VAL",
        version=1,
        strategy_name="TDD_STRATEGY",
        rationale="Valid plan",
        plan_claims=("CLM-01", "CLM-02"),
        stages=(stage1, stage2),
        dependency_edges=(("STAGE-1", "STAGE-2"),),
        evidence_requirements=("D6_EXECUTION_OBSERVATION",),
        identified_risks=(),
        potential_contradictions=(),
        revision_lineage=(),
        status=PlanStatus.DRAFT,
    )

    valid, reason, validated_plan = PlanArtifactValidator.validate(plan, sample_obligations)
    assert valid is True
    assert validated_plan.status == PlanStatus.VALIDATED


def test_validator_rejects_plan_with_unknown_obligation(sample_obligations):
    """Verifies that referencing an obligation outside the task graph fails closed."""
    stage = PlanStage(
        stage_id="STAGE-1",
        title="Stage 1",
        target_obligation_ids=("OBL-NONEXISTENT",),
        prerequisite_stage_ids=(),
        description="Invalid obl",
        verification_gate="Test gate",
    )
    plan = StrategicPlanArtifact(
        plan_id="PLAN-002",
        task_id="TASK-VAL",
        version=1,
        strategy_name="TDD_STRATEGY",
        rationale="Invalid plan",
        plan_claims=("CLM-01",),
        stages=(stage,),
        dependency_edges=(),
        evidence_requirements=("D6_EXECUTION_OBSERVATION",),
        identified_risks=(),
        potential_contradictions=(),
        revision_lineage=(),
        status=PlanStatus.DRAFT,
    )

    valid, reason, rejected_plan = PlanArtifactValidator.validate(plan, sample_obligations)
    assert valid is False
    assert "unknown obligation" in reason
    assert rejected_plan.status == PlanStatus.REJECTED


def test_validator_rejects_cyclic_plan(sample_obligations):
    """Verifies that circular stage dependencies are rejected fail-closed."""
    stage1 = PlanStage(
        stage_id="STAGE-1",
        title="Stage 1",
        target_obligation_ids=("OBL-VAL-01",),
        prerequisite_stage_ids=("STAGE-2",),
        description="Cycle part 1",
        verification_gate="Gate 1",
    )
    stage2 = PlanStage(
        stage_id="STAGE-2",
        title="Stage 2",
        target_obligation_ids=("OBL-VAL-02",),
        prerequisite_stage_ids=("STAGE-1",),
        description="Cycle part 2",
        verification_gate="Gate 2",
    )
    plan = StrategicPlanArtifact(
        plan_id="PLAN-003",
        task_id="TASK-VAL",
        version=1,
        strategy_name="TDD_STRATEGY",
        rationale="Cyclic plan",
        plan_claims=("CLM-01",),
        stages=(stage1, stage2),
        dependency_edges=(("STAGE-1", "STAGE-2"), ("STAGE-2", "STAGE-1")),
        evidence_requirements=("D6_EXECUTION_OBSERVATION",),
        identified_risks=(),
        potential_contradictions=(),
        revision_lineage=(),
        status=PlanStatus.DRAFT,
    )

    valid, reason, rejected_plan = PlanArtifactValidator.validate(plan, sample_obligations)
    assert valid is False
    assert "Cyclic dependency" in reason
    assert rejected_plan.status == PlanStatus.REJECTED
