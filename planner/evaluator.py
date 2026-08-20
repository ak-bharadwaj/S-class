"""D8 Autonomous Planning Substrate - Plan Evaluator & Gating Engine (§3.6, §8.1).

Enforces non-compensating hard constraint gates, D3 policy evaluation delegation,
governed risk bounds, and multi-objective Pareto ranking.
"""

from __future__ import annotations
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from domain.models import Obligation, Policy
from domain.types import Criticality, ObligationStatus
from planner.dependency import DependencyPlanner
from planner.models import (
    ExecutionStrategyArtifact,
    PlanNode,
    PlanQualityScore,
    PlannerRiskAssessment,
    PlannerStateView,
)

ALLOWED_ACTION_TYPES = {
    "EXECUTE_TEST",
    "STATIC_ANALYSIS",
    "TYPE_CHECK",
    "FUZZ_CONTRACT",
    "APPLY_PATCH",
    "READ_FILE",
}

IRREVERSIBLE_ACTION_TYPES = {
    "FORCE_PUSH",
    "DELETE_REMOTE_BRANCH",
    "DROP_DATABASE",
    "PUBLISH_PACKAGE",
}

MAX_GOVERNED_BLAST_RADIUS = 0.30


class HardConstraintGate:
    """Non-compensating gate: ANY failure results in categorical plan rejection."""

    @staticmethod
    def evaluate(
        strategy: ExecutionStrategyArtifact,
        state_view: PlannerStateView,
        budget_remaining: float = 100.0,
    ) -> Tuple[bool, Tuple[str, ...]]:
        """Evaluates hard invariant preconditions on the candidate execution strategy."""
        violations: List[str] = []

        # 1. Structural DAG Acyclicity
        if not DependencyPlanner.validate_acyclicity(strategy):
            violations.append("Dependency cycle detected in execution strategy DAG.")

        # 2. Obligation Existence and Validity
        known_obl_ids = {
            obl["obligation_id"] for obl in state_view.content.obligations
        }
        total_cost = 0.0

        for node in strategy.nodes:
            # Check obligation reference
            if node.obligation_id not in known_obl_ids:
                violations.append(
                    f"Node '{node.node_id}' references unknown obligation '{node.obligation_id}'."
                )

            # Check action type permission
            if node.action_type not in ALLOWED_ACTION_TYPES:
                violations.append(
                    f"Node '{node.node_id}' uses unpermitted action type '{node.action_type}'."
                )

            # Accumulate cost
            total_cost += node.estimated_cost_usd

            # Check timeout bounds
            if node.timeout_seconds > 600:
                violations.append(
                    f"Node '{node.node_id}' timeout {node.timeout_seconds}s exceeds maximum ceiling (600s)."
                )

        # 3. Budget Bound
        if total_cost > budget_remaining:
            violations.append(
                f"Total strategy cost ${total_cost:.2f} exceeds remaining budget ${budget_remaining:.2f}."
            )

        return (len(violations) == 0, tuple(violations))


class PlanEvaluator:
    """Evaluates candidate plans across hard gates, risk models, and preference rankings."""

    @staticmethod
    def assess_risk(
        strategy: ExecutionStrategyArtifact,
        state_view: PlannerStateView,
    ) -> PlannerRiskAssessment:
        """Computes formal multidimensional risk bounds."""
        security_risk = 0.0
        irreversible_risk = 0.0
        policy_violation_risk = 0.0
        dependency_violation_risk = 0.0
        unverified_claim_risk = 0.0
        rejections: List[str] = []

        # Calculate blast radius based on proportion of codebase files targeted
        unique_targets = {node.target for node in strategy.nodes}
        blast_radius = min(1.0, len(unique_targets) * 0.05)

        if blast_radius > MAX_GOVERNED_BLAST_RADIUS:
            rejections.append(
                f"Blast radius {blast_radius:.2f} exceeds governed limit {MAX_GOVERNED_BLAST_RADIUS:.2f} (CORE-14)."
            )

        for node in strategy.nodes:
            if node.action_type in IRREVERSIBLE_ACTION_TYPES:
                irreversible_risk = 1.0
                rejections.append(
                    f"Irreversible action '{node.action_type}' requires signed PolicyException (§3.5)."
                )

            # Check if targeting critical obligation with unverified claims
            for obl in state_view.content.obligations:
                if obl["obligation_id"] == node.obligation_id:
                    if obl.get("criticality") == Criticality.CRITICAL.value:
                        for clm_id in obl.get("claim_ids", []):
                            for clm in state_view.content.claims:
                                if clm["claim_id"] == clm_id and clm.get("status") != "SUPPORTED":
                                    unverified_claim_risk = max(unverified_claim_risk, 0.8)
                                    rejections.append(
                                        f"Critical claim '{clm_id}' for obligation '{node.obligation_id}' is unverified (§4.2)."
                                    )

        is_acceptable = len(rejections) == 0

        return PlannerRiskAssessment(
            security_risk=security_risk,
            irreversible_risk=irreversible_risk,
            blast_radius=blast_radius,
            policy_violation_risk=policy_violation_risk,
            budget_overrun_risk=0.0,
            dependency_violation_risk=dependency_violation_risk,
            unverified_claim_risk=unverified_claim_risk,
            is_acceptable=is_acceptable,
            rejection_reasons=tuple(rejections),
        )

    @staticmethod
    def evaluate(
        strategy: ExecutionStrategyArtifact,
        state_view: PlannerStateView,
        budget_remaining: float = 100.0,
    ) -> Tuple[bool, PlanQualityScore]:
        """Evaluates strategy and returns (is_admissible, quality_score)."""
        hard_pass, hard_reasons = HardConstraintGate.evaluate(
            strategy=strategy,
            state_view=state_view,
            budget_remaining=budget_remaining,
        )

        risk_assessment = PlanEvaluator.assess_risk(strategy, state_view)

        # Total expected cost
        total_cost = sum(node.estimated_cost_usd for node in strategy.nodes)
        total_duration = sum(node.timeout_seconds for node in strategy.nodes)

        # Compute parallelism factor
        frontiers = DependencyPlanner.compute_parallel_frontiers(strategy)
        parallelism = (
            len(strategy.nodes) / len(frontiers)
            if frontiers and len(frontiers) > 0
            else 1.0
        )

        # Compute claim coverage
        targeted_obls = {node.obligation_id for node in strategy.nodes}
        total_open_obls = len([
            obl for obl in state_view.content.obligations
            if obl.get("status") in (ObligationStatus.OPEN.value, "OPEN")
        ])
        claim_coverage = (
            len(targeted_obls) / total_open_obls
            if total_open_obls > 0
            else 1.0
        )

        # Progress potential Phi(s): higher coverage, higher parallelism, lower cost
        progress_potential = (claim_coverage * 10.0) + (parallelism * 2.0) - (total_cost * 1.5)

        is_admissible = hard_pass and risk_assessment.is_acceptable

        quality_score = PlanQualityScore(
            risk_assessment=risk_assessment,
            expected_cost_usd=total_cost,
            parallelism_factor=parallelism,
            estimated_duration_seconds=total_duration,
            claim_coverage=min(1.0, claim_coverage),
            progress_potential=max(0.0, progress_potential),
            pareto_rank=0 if is_admissible else 999,
        )

        return (is_admissible, quality_score)
