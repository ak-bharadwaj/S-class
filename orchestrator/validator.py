"""
S-Class Plan Artifact Validator.

Performs deterministic, out-of-LLM validation of candidate StrategicPlanArtifacts.
Validates DAG acyclicity, obligation coverage, stage sequencing, and evidence requirements.
"""

from typing import Tuple, Mapping, Set, Dict, List
from orchestrator.models import StrategicPlanArtifact, PlanStage
from planner.models import PlanStatus
from domain.models import Obligation


class PlanArtifactValidator:
    """Deterministic validator for candidate StrategicPlanArtifacts."""

    @classmethod
    def validate(
        cls,
        plan: StrategicPlanArtifact,
        obligations: Mapping[str, Obligation],
    ) -> Tuple[bool, str, StrategicPlanArtifact]:
        """
        Validates candidate plan artifact and returns (is_valid, reason, updated_plan).
        Never modifies state implicitly; returns a new plan instance with updated PlanStatus.
        """
        if not plan.stages:
            rejected = cls._set_status(plan, PlanStatus.REJECTED)
            return False, "Plan contains zero execution stages.", rejected

        if not plan.plan_claims:
            rejected = cls._set_status(plan, PlanStatus.REJECTED)
            return False, "Plan specifies no target claims.", rejected

        # 1. Obligation coverage validation
        for stage in plan.stages:
            for obl_id in stage.target_obligation_ids:
                if obl_id not in obligations:
                    rejected = cls._set_status(plan, PlanStatus.REJECTED)
                    return False, f"Stage '{stage.stage_id}' references unknown obligation '{obl_id}'.", rejected

        # 2. Stage dependency acyclicity validation
        stage_ids = {s.stage_id for s in plan.stages}
        for stage in plan.stages:
            for prereq in stage.prerequisite_stage_ids:
                if prereq not in stage_ids:
                    rejected = cls._set_status(plan, PlanStatus.REJECTED)
                    return False, f"Stage '{stage.stage_id}' references non-existent prerequisite stage '{prereq}'.", rejected

        adj: Dict[str, List[str]] = {s.stage_id: list(s.prerequisite_stage_ids) for s in plan.stages}
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for stage_id in stage_ids:
            if stage_id not in visited:
                if has_cycle(stage_id):
                    rejected = cls._set_status(plan, PlanStatus.REJECTED)
                    return False, "Cyclic dependency detected in plan stages.", rejected

        # 3. Evidence requirement completeness
        if not plan.evidence_requirements:
            rejected = cls._set_status(plan, PlanStatus.REJECTED)
            return False, "Plan contains no specified evidence requirements.", rejected

        validated = cls._set_status(plan, PlanStatus.VALIDATED)
        return True, "Plan validated successfully against obligation DAG and constraints.", validated

    @classmethod
    def _set_status(cls, plan: StrategicPlanArtifact, new_status: PlanStatus) -> StrategicPlanArtifact:
        """Returns a new StrategicPlanArtifact instance with updated status."""
        return StrategicPlanArtifact(
            plan_id=plan.plan_id,
            task_id=plan.task_id,
            version=plan.version,
            strategy_name=plan.strategy_name,
            rationale=plan.rationale,
            plan_claims=plan.plan_claims,
            stages=plan.stages,
            dependency_edges=plan.dependency_edges,
            evidence_requirements=plan.evidence_requirements,
            identified_risks=plan.identified_risks,
            potential_contradictions=plan.potential_contradictions,
            revision_lineage=plan.revision_lineage,
            status=new_status,
            estimated_risk_score=plan.estimated_risk_score,
            plan_digest=plan.plan_digest,
            created_at_iso=plan.created_at_iso,
        )
