"""
S-Class Multi-Factor State Optimizer & Dynamic Reasoning Router.

Evaluates multi-dimensional canonical state inputs without manufactured facts:
- Obligations DAG, Claim Epistemic Lattice, and Verified Assessment Receipts
- Authoritative Repository Facts, Task Risk Profile, and Verification Requirements
- Available Model Providers, Cognitive Tiers, Context Budget, and Prior Trajectories

Derives the optimal next reasoning mode, multi-skill composition, model tier,
bounded context slice specification, and expected governed artifact.
"""

from typing import Tuple, Optional, Sequence
from orchestrator.models import (
    ReasoningMode,
    ModelTier,
    ArtifactType,
    ContextSliceSpec,
    RoutingDecision,
    OrchestrationStateSnapshot,
)
from orchestrator.skills import EngineeringSkillRegistry
from claim.reducer import ClaimEpistemicState
from planner.models import PlanStatus
from domain.types import Criticality


class StateOptimizerRouter:
    """Multi-factor state optimizer deriving optimal reasoning decisions from canonical state."""

    @classmethod
    def derive_next_decision(cls, state: OrchestrationStateSnapshot) -> RoutingDecision:
        """Evaluates canonical state snapshot and computes optimal multi-factor routing decision."""

        # 1. Immediate Safety & Escalation Cutoffs (Fail-Closed)
        if state.remaining_budget_units <= 0 or state.turn_index > state.max_turns:
            return RoutingDecision(
                mode=ReasoningMode.ESCALATE,
                active_frontier_ids=(),
                selected_skills=(),
                target_provider_type="local",
                target_model_tier=ModelTier.LOCAL_DETERMINISTIC,
                reasoning_objective="Halt execution: Bounded turn budget or resource limit exhausted.",
                required_capabilities=(),
                expected_artifact_type=ArtifactType.ESCALATION_RECEIPT,
                verification_requirement="Halt and record session resource exhaustion receipt.",
                context_slice_spec=ContextSliceSpec(include_governance_header=True),
                rationale="Safety cutoff: turn_index or budget ceiling reached.",
            )

        if state.has_oscillation_detected:
            return RoutingDecision(
                mode=ReasoningMode.ESCALATE,
                active_frontier_ids=(),
                selected_skills=(),
                target_provider_type="local",
                target_model_tier=ModelTier.LOCAL_DETERMINISTIC,
                reasoning_objective="Halt execution: Plan oscillation or repair thrashing detected.",
                required_capabilities=(),
                expected_artifact_type=ArtifactType.ESCALATION_RECEIPT,
                verification_requirement="Halt and emit oscillation analysis report.",
                context_slice_spec=ContextSliceSpec(include_governance_header=True),
                rationale="OscillationDetector identified repeating cycle in strategy space.",
            )

        for obl_id, attempts in state.repair_attempts_by_obligation.items():
            if attempts >= 3 and obl_id in state.failed_obligation_ids:
                return RoutingDecision(
                    mode=ReasoningMode.ESCALATE,
                    active_frontier_ids=(obl_id,),
                    selected_skills=(),
                    target_provider_type="local",
                    target_model_tier=ModelTier.LOCAL_DETERMINISTIC,
                    reasoning_objective=f"Halt execution: Obligation '{obl_id}' exceeded maximum repair attempts (3).",
                    required_capabilities=(),
                    expected_artifact_type=ArtifactType.ESCALATION_RECEIPT,
                    verification_requirement="Escalate to human review with failure transcript.",
                    context_slice_spec=ContextSliceSpec(
                        include_governance_header=True,
                        target_obligation_ids=(obl_id,),
                        include_diagnostics=True,
                    ),
                    rationale=f"Repeated refutation on {obl_id} requires human review.",
                )

        # 2. Derive Effective Risk and Criticality from Authoritative State (No Manufactured Defaults)
        is_security_critical = False
        if state.task_risk.criticality_score is not None:
            is_security_critical = (state.task_risk.criticality_score >= 0.8)
        else:
            # Derive dynamically from obligations
            has_crit_obls = any(
                o.criticality in (Criticality.CRITICAL, Criticality.HIGH)
                for o in state.obligations
            )
            is_security_critical = has_crit_obls

        # 3. Discovery & Inception Path
        if not state.obligations:
            tier = ModelTier.REASONING_PRO
            provider = cls._select_provider_for_tier(tier, state.available_providers, state.remaining_budget_units)
            skills = EngineeringSkillRegistry.compose_skills_for_mode("ARCHITECT")
            return RoutingDecision(
                mode=ReasoningMode.DISCOVER,
                active_frontier_ids=(),
                selected_skills=skills,
                target_provider_type=provider,
                target_model_tier=tier,
                reasoning_objective="Inspect repository AST, files, and dependencies to formalize specification.",
                required_capabilities=("CAP_READ_CODE",),
                expected_artifact_type=ArtifactType.REPO_INVENTORY,
                verification_requirement="Verify repository layout and identify target modules.",
                context_slice_spec=ContextSliceSpec(include_governance_header=True, include_diagnostics=False),
                rationale="Initial state: workspace exploration required before formal specification.",
            )

        # 4. Governed Strategic Planning Path (Plan-as-Artifact)
        has_validated_plan = (
            state.active_plan is not None
            and state.active_plan.status == PlanStatus.VALIDATED
        )
        if not has_validated_plan and state.ready_obligation_ids:
            tier = ModelTier.REASONING_PRO
            provider = cls._select_provider_for_tier(tier, state.available_providers, state.remaining_budget_units)
            skills = EngineeringSkillRegistry.compose_skills_for_mode("ARCHITECT", is_security_critical=is_security_critical)
            return RoutingDecision(
                mode=ReasoningMode.PLAN,
                active_frontier_ids=state.ready_obligation_ids,
                selected_skills=skills,
                target_provider_type=provider,
                target_model_tier=tier,
                reasoning_objective="Synthesize governed StrategicPlanArtifact decomposing obligations into verification stages.",
                required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
                expected_artifact_type=ArtifactType.STRATEGIC_PLAN,
                verification_requirement="Deterministic plan artifact validation (DAG acyclicity & obligation coverage).",
                context_slice_spec=ContextSliceSpec(
                    include_governance_header=True,
                    target_obligation_ids=state.ready_obligation_ids,
                ),
                rationale="Formal plan generation required before entering implementation lifecycle.",
            )

        # 5. Failure / Refutation / Replan Path
        if state.failed_obligation_ids:
            active_failed_id = state.failed_obligation_ids[0]
            attempts = state.repair_attempts_by_obligation.get(active_failed_id, 0)

            # If failed repeatedly, trigger replanning rather than blind thrashing
            if attempts >= 2:
                tier = ModelTier.REASONING_PRO
                provider = cls._select_provider_for_tier(tier, state.available_providers, state.remaining_budget_units)
                skills = EngineeringSkillRegistry.compose_skills_for_mode("DIAGNOSE", has_refutation=True)
                return RoutingDecision(
                    mode=ReasoningMode.REPLAN,
                    active_frontier_ids=(active_failed_id,),
                    selected_skills=skills,
                    target_provider_type=provider,
                    target_model_tier=tier,
                    reasoning_objective=f"Replanning required: Obligation '{active_failed_id}' failed twice. Re-evaluate strategy.",
                    required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
                    expected_artifact_type=ArtifactType.REVISED_PLAN,
                    verification_requirement="Synthesize alternative implementation strategy.",
                    context_slice_spec=ContextSliceSpec(
                        include_governance_header=True,
                        target_obligation_ids=(active_failed_id,),
                        include_diagnostics=True,
                    ),
                    rationale=f"Multiple failed repair attempts ({attempts}) on {active_failed_id}; strategy replanning required.",
                )

            has_contradicted = any(
                cs.epistemic_state == ClaimEpistemicState.CONTRADICTED
                for cs in state.claim_states.values()
            )
            if has_contradicted:
                tier = ModelTier.REASONING_PRO
                provider = cls._select_provider_for_tier(tier, state.available_providers, state.remaining_budget_units)
                skills = EngineeringSkillRegistry.compose_skills_for_mode("DIAGNOSE", has_refutation=True)
                return RoutingDecision(
                    mode=ReasoningMode.DIAGNOSE,
                    active_frontier_ids=(active_failed_id,),
                    selected_skills=skills,
                    target_provider_type=provider,
                    target_model_tier=tier,
                    reasoning_objective=f"Isolate root-cause failure diagnostics for refuted obligation '{active_failed_id}'.",
                    required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
                    expected_artifact_type=ArtifactType.ROOT_CAUSE_DIAGNOSIS,
                    verification_requirement="Minimal reproduction test harness.",
                    context_slice_spec=ContextSliceSpec(
                        include_governance_header=True,
                        target_obligation_ids=(active_failed_id,),
                        include_diagnostics=True,
                    ),
                    rationale="Refuting evidence present; diagnostic root-cause isolation required before patching.",
                )
            else:
                tier = ModelTier.CODE_FAST
                provider = cls._select_provider_for_tier(tier, state.available_providers, state.remaining_budget_units)
                skills = EngineeringSkillRegistry.compose_skills_for_mode("REPAIR", has_refutation=True)
                return RoutingDecision(
                    mode=ReasoningMode.REPAIR,
                    active_frontier_ids=(active_failed_id,),
                    selected_skills=skills,
                    target_provider_type=provider,
                    target_model_tier=tier,
                    reasoning_objective=f"Synthesize minimal corrective patch for obligation '{active_failed_id}'.",
                    required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
                    expected_artifact_type=ArtifactType.REPAIR_PATCH,
                    verification_requirement="Isolated D6 sandbox pytest execution.",
                    context_slice_spec=ContextSliceSpec(
                        include_governance_header=True,
                        target_obligation_ids=(active_failed_id,),
                        include_diagnostics=True,
                    ),
                    rationale="Root cause analyzed; generating minimal corrective patch.",
                )

        # 6. Ready Decision Frontier
        if state.ready_obligation_ids:
            active_obl_id = state.ready_obligation_ids[0]
            active_claims = [c for c in state.claims if c.obligation_id == active_obl_id]
            all_supported = all(
                state.claim_states.get(c.claim_id, None) is not None
                and state.claim_states[c.claim_id].epistemic_state == ClaimEpistemicState.SUPPORTED
                for c in active_claims
            ) if active_claims else False

            obl_obj = next((o for o in state.obligations if o.obligation_id == active_obl_id), None)
            obl_cat = obl_obj.category.value if obl_obj else None

            if not all_supported:
                tier = ModelTier.CODE_FAST
                provider = cls._select_provider_for_tier(tier, state.available_providers, state.remaining_budget_units)
                skills = EngineeringSkillRegistry.compose_skills_for_mode(
                    "IMPLEMENT",
                    task_category=obl_cat,
                    is_security_critical=is_security_critical,
                )
                return RoutingDecision(
                    mode=ReasoningMode.IMPLEMENT,
                    active_frontier_ids=(active_obl_id,),
                    selected_skills=skills,
                    target_provider_type=provider,
                    target_model_tier=tier,
                    reasoning_objective=f"Implement source code patch and verification test for obligation '{active_obl_id}'.",
                    required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
                    expected_artifact_type=ArtifactType.CODE_PATCH,
                    verification_requirement="D6 sandbox test execution verifying must-invariants.",
                    context_slice_spec=ContextSliceSpec(
                        include_governance_header=True,
                        target_obligation_ids=(active_obl_id,),
                        include_diagnostics=False,
                    ),
                    rationale=f"Obligation '{active_obl_id}' is ready on the decision frontier.",
                )
            else:
                tier = ModelTier.EVALUATOR_ACCURATE
                provider = cls._select_provider_for_tier(tier, state.available_providers, state.remaining_budget_units)
                skills = EngineeringSkillRegistry.compose_skills_for_mode("REVIEW")
                return RoutingDecision(
                    mode=ReasoningMode.REGRESS,
                    active_frontier_ids=(active_obl_id,),
                    selected_skills=skills,
                    target_provider_type="local",
                    target_model_tier=tier,
                    reasoning_objective=f"Run full baseline regression suite verifying obligation '{active_obl_id}'.",
                    required_capabilities=("CAP_EXEC_TEST",),
                    expected_artifact_type=ArtifactType.REGRESSION_REPORT,
                    verification_requirement="0 regressions across full repository test suite.",
                    context_slice_spec=ContextSliceSpec(
                        include_governance_header=True,
                        target_obligation_ids=(active_obl_id,),
                    ),
                    rationale="Claims supported; verifying zero regressions against existing codebase.",
                )

        # 7. Global Convergence & Task Closure
        total_count = len(state.obligations)
        satisfied_count = len(state.satisfied_obligation_ids)
        if total_count > 0 and satisfied_count == total_count:
            skills = (EngineeringSkillRegistry.get("skill-provenance-collation"),)
            return RoutingDecision(
                mode=ReasoningMode.CLOSE,
                active_frontier_ids=(),
                selected_skills=skills,
                target_provider_type="local",
                target_model_tier=ModelTier.LOCAL_DETERMINISTIC,
                reasoning_objective="Mint task closure receipt and seal durable D2 audit log.",
                required_capabilities=(),
                expected_artifact_type=ArtifactType.CLOSURE_RECEIPT,
                verification_requirement="Verified Ed25519 authority signature on final closure receipt.",
                context_slice_spec=ContextSliceSpec(include_governance_header=True),
                rationale="All task obligations satisfied with verified cryptographic receipts.",
            )

        # Fallback to Architecture / Decomposition
        tier = ModelTier.REASONING_PRO
        provider = cls._select_provider_for_tier(tier, state.available_providers, state.remaining_budget_units)
        skills = EngineeringSkillRegistry.compose_skills_for_mode("ARCHITECT")
        return RoutingDecision(
            mode=ReasoningMode.DECOMPOSE,
            active_frontier_ids=(),
            selected_skills=skills,
            target_provider_type=provider,
            target_model_tier=tier,
            reasoning_objective="Evaluate dependency graph and resolve blocked obligation frontier.",
            required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
            expected_artifact_type=ArtifactType.OBLIGATION_DAG,
            verification_requirement="Topological DAG acyclicity and prerequisite satisfaction check.",
            context_slice_spec=ContextSliceSpec(include_governance_header=True),
            rationale="Frontier empty while unsatisfied obligations remain; graph re-evaluation required.",
        )

    @classmethod
    def _select_provider_for_tier(
        cls,
        tier: ModelTier,
        available_providers: Sequence[str],
        remaining_budget_units: float,
    ) -> str:
        """
        Dynamically selects the optimal provider based on cognitive tier, available providers,
        and remaining execution budget. Zero arbitrary universal ordering.
        """
        if tier == ModelTier.LOCAL_DETERMINISTIC or not available_providers:
            return "local"

        # Low budget mode: favor cost-effective or fast providers
        if remaining_budget_units < 3.0:
            for p in ("openai", "gemini", "anthropic", "local"):
                if p in available_providers:
                    return p

        # Deep reasoning tier: favors reasoning models
        if tier == ModelTier.REASONING_PRO:
            for p in ("gemini", "anthropic", "openai", "local"):
                if p in available_providers:
                    return p

        # Code fast tier: favors fast code execution
        if tier == ModelTier.CODE_FAST:
            for p in ("openai", "gemini", "anthropic", "local"):
                if p in available_providers:
                    return p

        # Evaluator accurate tier
        for p in ("anthropic", "openai", "gemini", "local"):
            if p in available_providers:
                return p

        return available_providers[0]
