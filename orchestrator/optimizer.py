"""
S-Class State Optimizer & Reasoning Router.

Evaluates canonical state snapshots and derives the next reasoning mode,
active decision frontier, appropriate skill playbook, and target model tier.
"""

from typing import Tuple, Optional
from orchestrator.models import (
    ReasoningMode,
    OrchestrationStateSnapshot,
    RoutingDecision,
)
from orchestrator.skills import EngineeringSkillRegistry
from claim.reducer import ClaimEpistemicState


class StateOptimizerRouter:
    """Deterministic state-to-reasoning-mode optimizer and dynamic router."""

    @classmethod
    def derive_next_decision(cls, state: OrchestrationStateSnapshot) -> RoutingDecision:
        """Derives the next reasoning mode and task slice from canonical state snapshot."""

        # 1. Immediate Safety & Escalation Checks
        if state.remaining_budget_units <= 0 or state.turn_index > state.max_turns:
            return RoutingDecision(
                mode=ReasoningMode.ESCALATE,
                active_frontier_ids=(),
                selected_skill=None,
                target_provider_type="local",
                target_model_tier="evaluator",
                reasoning_objective="Halt execution: Bounded turn budget or resource limit exhausted.",
                required_capabilities=(),
                rationale="Safety cutoff: turn_index or budget ceiling reached.",
            )

        if state.has_oscillation_detected:
            return RoutingDecision(
                mode=ReasoningMode.ESCALATE,
                active_frontier_ids=(),
                selected_skill=None,
                target_provider_type="local",
                target_model_tier="evaluator",
                reasoning_objective="Halt execution: Plan oscillation or repair thrashing detected.",
                required_capabilities=(),
                rationale="OscillationDetector identified repeating cycle in strategy space.",
            )

        for obl_id, attempts in state.repair_attempts_by_obligation.items():
            if attempts >= 3 and obl_id in state.failed_obligation_ids:
                return RoutingDecision(
                    mode=ReasoningMode.ESCALATE,
                    active_frontier_ids=(obl_id,),
                    selected_skill=None,
                    target_provider_type="local",
                    target_model_tier="evaluator",
                    reasoning_objective=f"Halt execution: Obligation '{obl_id}' exceeded maximum repair attempts (3).",
                    required_capabilities=(),
                    rationale=f"Repeated refutation on {obl_id} requires human review or replanning.",
                )

        # 2. Specification & Discovery Inception
        if not state.obligations:
            return RoutingDecision(
                mode=ReasoningMode.DISCOVER,
                active_frontier_ids=(),
                selected_skill=None,
                target_provider_type="gemini",
                target_model_tier="reasoning_pro",
                reasoning_objective="Inspect repository AST and directory layout to formalize specification.",
                required_capabilities=("CAP_READ_CODE",),
                rationale="Initial state: workspace exploration required before formal specification.",
            )

        # 3. Active Failure / Refutation Path
        if state.failed_obligation_ids:
            active_failed_id = state.failed_obligation_ids[0]
            # Check if we have unanalyzed contradicted claims
            has_contradicted = any(
                cs.epistemic_state == ClaimEpistemicState.CONTRADICTED
                for cs in state.claim_states.values()
            )
            if has_contradicted:
                skill = EngineeringSkillRegistry.select_for_mode("DIAGNOSE", has_refutation=True)
                return RoutingDecision(
                    mode=ReasoningMode.DIAGNOSE,
                    active_frontier_ids=(active_failed_id,),
                    selected_skill=skill,
                    target_provider_type="gemini",
                    target_model_tier="reasoning_pro",
                    reasoning_objective=f"Isolate root-cause failure for refuted obligation '{active_failed_id}'.",
                    required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
                    rationale="Refuting evidence present; diagnostic root-cause analysis required before patch.",
                )
            else:
                skill = EngineeringSkillRegistry.select_for_mode("REPAIR", has_refutation=True)
                return RoutingDecision(
                    mode=ReasoningMode.REPAIR,
                    active_frontier_ids=(active_failed_id,),
                    selected_skill=skill,
                    target_provider_type="gemini",
                    target_model_tier="code_fast",
                    reasoning_objective=f"Synthesize targeted repair patch for obligation '{active_failed_id}'.",
                    required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
                    rationale="Root cause analyzed; generating minimal corrective patch.",
                )

        # 4. Ready Decision Frontier
        if state.ready_obligation_ids:
            active_obl_id = state.ready_obligation_ids[0]
            # Check claims associated with active obligation
            active_claims = [c for c in state.claims if c.obligation_id == active_obl_id]
            all_supported = all(
                state.claim_states.get(c.claim_id, None) is not None
                and state.claim_states[c.claim_id].epistemic_state == ClaimEpistemicState.SUPPORTED
                for c in active_claims
            ) if active_claims else False

            if not all_supported:
                # If claims are unsupported, we need implementation or test verification
                skill = EngineeringSkillRegistry.select_for_mode("VERIFY")
                return RoutingDecision(
                    mode=ReasoningMode.IMPLEMENT,
                    active_frontier_ids=(active_obl_id,),
                    selected_skill=skill,
                    target_provider_type="gemini",
                    target_model_tier="code_fast",
                    reasoning_objective=f"Implement source code patch and verification test for obligation '{active_obl_id}'.",
                    required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
                    rationale=f"Obligation '{active_obl_id}' is ready on the decision frontier.",
                )
            else:
                # Claims supported, run regression suite
                return RoutingDecision(
                    mode=ReasoningMode.REGRESS,
                    active_frontier_ids=(active_obl_id,),
                    selected_skill=None,
                    target_provider_type="local",
                    target_model_tier="evaluator",
                    reasoning_objective=f"Run full baseline regression suite for obligation '{active_obl_id}'.",
                    required_capabilities=("CAP_EXEC_TEST",),
                    rationale="Claims supported; verifying zero regressions against existing codebase.",
                )

        # 5. Global Convergence & Task Closure
        total_count = len(state.obligations)
        satisfied_count = len(state.satisfied_obligation_ids)
        if total_count > 0 and satisfied_count == total_count:
            return RoutingDecision(
                mode=ReasoningMode.CLOSE,
                active_frontier_ids=(),
                selected_skill=None,
                target_provider_type="local",
                target_model_tier="evaluator",
                reasoning_objective="Mint task closure receipt and seal durable D2 audit log.",
                required_capabilities=(),
                rationale="All task obligations satisfied with verified cryptographic receipts.",
            )

        # Fallback to Architecture / Decomposition if frontier stalled
        return RoutingDecision(
            mode=ReasoningMode.DECOMPOSE,
            active_frontier_ids=(),
            selected_skill=None,
            target_provider_type="gemini",
            target_model_tier="reasoning_pro",
            reasoning_objective="Evaluate dependency graph and resolve blocked obligation frontier.",
            required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
            rationale="Frontier empty while unsatisfied obligations remain; graph re-evaluation required.",
        )
