"""D8 Autonomous Planning Substrate - Plan Evaluator & Gating Engine (§3.6, §8.1).

Enforces non-compensating hard constraint gates, D3 policy evaluation delegation,
governed risk bounds, and multi-objective Pareto ranking.
"""

from __future__ import annotations
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from domain.models import Obligation, Policy, Claim, ClaimSubject
from domain.types import Criticality, ObligationCategory, ObligationStatus, ClaimTier, ClaimStatus, PolicyScope, TargetType
from policy.evaluator import evaluate_policy
from policy.models import PolicyEvaluationContext, PolicyDecisionType, PolicyDecision, PolicyException
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

        # 2. Strategy Digest Integrity
        from planner.fingerprint import compute_execution_strategy_fingerprint
        expected_strat_digest = compute_execution_strategy_fingerprint(strategy)
        if strategy.strategy_digest != expected_strat_digest:
            violations.append(
                f"Execution strategy digest mismatch: '{strategy.strategy_digest}' != expected '{expected_strat_digest}'."
            )

        # 3. Obligation Existence, Validity, and Frontier Executability
        known_obl_ids = {
            obl["obligation_id"] for obl in state_view.content.obligations
        }
        exec_frontier_set = set(state_view.content.executable_frontier)
        total_cost = 0.0

        for node in strategy.nodes:
            # Check obligation reference
            if node.obligation_id not in known_obl_ids:
                violations.append(
                    f"Node '{node.node_id}' references unknown obligation '{node.obligation_id}'."
                )

            # Check executable frontier
            if node.obligation_id not in exec_frontier_set:
                violations.append(
                    f"Node '{node.node_id}' targets non-executable obligation '{node.obligation_id}' (not in executable frontier)."
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

        # 4. Budget Bound
        if total_cost > budget_remaining:
            violations.append(
                f"Total strategy cost ${total_cost:.2f} exceeds remaining budget ${budget_remaining:.2f}."
            )

        # 5. Structural Node and Reference Integrity (PlanCritic Criteria)
        node_ids = tuple(n.node_id for n in strategy.nodes)
        node_set = set(node_ids)
        if len(node_set) != len(node_ids):
            violations.append("Candidate plan contains duplicate node identifiers.")

        for src, dst in strategy.dependency_edges:
            if src not in node_set or dst not in node_set:
                violations.append(f"Dependency edge references non-existent node: ({src}->{dst}).")

        # 6. Target State Binding Verification
        if hasattr(state_view.content, "state_digest") and state_view.content.state_digest:
            if not isinstance(state_view.content.state_digest, str) or len(state_view.content.state_digest) < 32:
                violations.append("Invalid or corrupted state_digest in context.")

        # 7. Exact D3 Policy Evaluation Delegation (Pure D3 Consumer, Zero Policy Rule Inspection)
        claims_map = {c.get("claim_id"): c for c in state_view.content.claims if hasattr(c, "get")}
        for node in strategy.nodes:
            matching_obls = [
                o for o in state_view.content.obligations if o.get("obligation_id") == node.obligation_id
            ]
            if not matching_obls:
                continue
            obl_dict = matching_obls[0]
            target_policy_id = obl_dict.get("policy_id")

            # Match exact policy for this obligation (or task-scoped fallback if unassigned)
            target_policies = []
            for policy in getattr(state_view.content, "active_policies", ()):
                if isinstance(policy, Policy):
                    if target_policy_id and policy.policy_id == target_policy_id:
                        target_policies.append(policy)
                    elif not target_policy_id and policy.scope_level == PolicyScope.TASK:
                        target_policies.append(policy)

            for policy in target_policies:
                obl_claim_ids = obl_dict.get("claim_ids", [])
                eval_claims = []
                for cid in obl_claim_ids:
                    cd = claims_map.get(cid)
                    if cd:
                        clm_inst = Claim(
                            claim_id=cd.get("claim_id", cid),
                            obligation_id=node.obligation_id,
                            tier=ClaimTier(cd.get("tier", ClaimTier.V1_STRUCTURAL.value)),
                            subject=ClaimSubject(target_type=TargetType.FUNCTION, identifier=str(cd.get("predicate", "func"))),
                            predicate=cd.get("predicate", "Invariant"),
                            criticality=Criticality(obl_dict.get("criticality", Criticality.HIGH.value)),
                            status=ClaimStatus(cd.get("status", ClaimStatus.UNSUPPORTED.value)),
                        )
                        eval_claims.append(clm_inst)

                obl_inst = Obligation(
                    obligation_id=obl_dict["obligation_id"],
                    task_id=state_view.content.task_id,
                    category=ObligationCategory(obl_dict.get("category", ObligationCategory.CORRECTNESS_FUNCTIONAL.value)),
                    criticality=Criticality(obl_dict.get("criticality", Criticality.HIGH.value)),
                    status=ObligationStatus(obl_dict.get("status", ObligationStatus.OPEN.value)),
                    title=obl_dict.get("title", "Governed Obligation"),
                    description=obl_dict.get("description", "Governed Obligation"),
                    claim_ids=tuple(obl_claim_ids),
                    policy_id=target_policy_id,
                )

                matching_exceptions = tuple(
                    exc for exc in getattr(state_view.content, "exceptions", ())
                    if getattr(exc, "obligation_id", None) == node.obligation_id
                    and getattr(exc, "policy_id", None) == policy.policy_id
                )

                eval_context = PolicyEvaluationContext(
                    obligation=obl_inst,
                    claims=tuple(eval_claims),
                    evidence=(),
                    exceptions=matching_exceptions,
                )
                decision = evaluate_policy(policy, eval_context)
                if decision.decision == PolicyDecisionType.DENY:
                    violations.append(
                        f"D3 Policy '{policy.policy_id}' DENIED action for obligation '{node.obligation_id}': {decision.rationale}"
                    )

        # 8. Non-Compensating Risk Evaluation Gate
        risk = PlanEvaluator.assess_risk(strategy, state_view)
        if not risk.is_acceptable:
            violations.extend(risk.rejection_reasons)

        return (len(violations) == 0, tuple(violations))


class PlanEvaluator:
    """Evaluates candidate plans across hard gates, risk models, and preference rankings."""

    @staticmethod
    def assess_risk(
        strategy: ExecutionStrategyArtifact,
        state_view: PlannerStateView,
    ) -> PlannerRiskAssessment:
        """Computes formal multidimensional risk bounds incorporating analytical artifact implications."""
        security_risk = 0.0
        irreversible_risk = 0.0
        policy_violation_risk = 0.0
        dependency_violation_risk = 0.0
        unverified_claim_risk = 0.0
        rejections: List[str] = []

        # Factor in analytical implications from RiskRegressionAnalyst
        for artifact in getattr(state_view.content, "analysis_artifacts", ()):
            for imp in getattr(artifact, "implications", ()):
                if getattr(imp, "risk_level", "LOW") in ("HIGH", "CRITICAL"):
                    security_risk += 0.25

        # Calculate blast radius based on proportion of codebase files targeted
        unique_targets = {node.target for node in strategy.nodes}
        blast_radius = min(1.0, len(unique_targets) * 0.05)

        if blast_radius > MAX_GOVERNED_BLAST_RADIUS:
            rejections.append(
                f"Blast radius {blast_radius:.2f} exceeds governed limit {MAX_GOVERNED_BLAST_RADIUS:.2f} (CORE-14)."
            )

        for node in strategy.nodes:
            if node.action_type in IRREVERSIBLE_ACTION_TYPES:
                # Check for matching signed PolicyException
                has_valid_exception = False
                for exc in getattr(state_view.content, "exceptions", ()):
                    if getattr(exc, "obligation_id", None) == node.obligation_id:
                        has_valid_exception = True
                        break
                if not has_valid_exception:
                    irreversible_risk = 1.0
                    rejections.append(
                        f"Irreversible action '{node.action_type}' requires signed PolicyException (§3.5)."
                    )

            # Check critical obligation unverified claims
            for obl in state_view.content.obligations:
                if obl["obligation_id"] == node.obligation_id:
                    if obl.get("criticality") == Criticality.CRITICAL.value:
                        for clm_id in obl.get("claim_ids", []):
                            for clm in state_view.content.claims:
                                if clm["claim_id"] == clm_id and clm.get("status") not in ("SUPPORTED", "VERIFIED_TRUE"):
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
