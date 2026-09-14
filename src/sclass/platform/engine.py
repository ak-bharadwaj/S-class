"""
S-Class Platform Optimization Engine

Reconciles:
PlatformProfile + Task + Risk + State + PerformanceBudget -> ControlPolicy

Architectural Role:
Determines where S-Class intervenes and where it deliberately stays out of the way.
Dynamically tunes observation, verification, checkpoints, context injection,
and interventions to maximize Net Utility Ratio (useful reliability gained / overhead).
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Union

from sclass.platform.profile import PlatformProfile
from sclass.platform.policy import (
    CompensationPolicy,
    ObservationLevel,
    VerificationLevel,
    CheckpointLevel,
    InterruptionPolicy,
    EscalationPolicy,
    InterventionDecision,
    InterventionResult,
    InterventionPolicy,
)
from sclass.platform.budget import (
    PerformanceBudget,
    BudgetLimits,
    OverheadConsumption,
    ReliabilityGain,
    VerificationBudgetController,
)
from sclass.platform.archetypes import get_archetype


@dataclass(frozen=True)
class ControlPolicy:
    """
    Synthesized runtime control policy for an execution turn or task horizon.
    """
    platform_id: str
    observation_mode: str
    verification_gate: str
    checkpoint_frequency: str
    context_injection_limit: int
    interruption_policy: str
    escalation_policy: str
    allowed_interventions: List[str] = field(default_factory=list)
    suppressed_interventions: List[str] = field(default_factory=list)
    active_compensations: List[str] = field(default_factory=list)
    preserved_capabilities: List[str] = field(default_factory=list)
    budget: PerformanceBudget = field(default_factory=PerformanceBudget)
    rationale: List[str] = field(default_factory=list)

    def is_intervention_allowed(self, intervention: str) -> bool:
        """Check if an intervention is permitted and not explicitly suppressed."""
        if not intervention or not str(intervention).strip():
            return False
        if self.is_intervention_suppressed(intervention):
            return False
        target = str(intervention).strip().lower().replace("-", "_").replace(" ", "_")
        for a in self.allowed_interventions:
            norm_a = str(a).strip().lower().replace("-", "_").replace(" ", "_")
            if target == norm_a or norm_a in target:
                return True
            if target in norm_a and len(target) >= 4:
                return True
        return False

    def is_intervention_suppressed(self, intervention: str) -> bool:
        """Check if an intervention is actively suppressed to avoid platform interference."""
        if not intervention or not str(intervention).strip():
            return False
        target = str(intervention).strip().lower().replace("-", "_").replace(" ", "_")
        for s in self.suppressed_interventions:
            norm_s = str(s).strip().lower().replace("-", "_").replace(" ", "_")
            if target == norm_s or norm_s in target:
                return True
            # Only match if target contains specific qualifiers of the suppression rule
            # e.g. "micro_checkpoints" in "constant_micro_checkpoints" matches,
            # but generic "checkpoint" does NOT match qualified "constant_micro_checkpoints"
            if target in norm_s:
                target_words = set(target.split("_"))
                supp_words = set(norm_s.split("_"))
                qualifiers = {"micro", "constant", "huge", "redundant", "duplicate", "interactive", "verbose", "exhaustive"}
                if (supp_words & qualifiers):
                    if (target_words & qualifiers):
                        return True
                elif len(target) >= 5:
                    return True
        return False

    def should_stay_out_of_way(self, action_or_area: str) -> bool:
        """Evaluate if S-Class should deliberately stay out of the way of this action/area."""
        if not action_or_area or not str(action_or_area).strip():
            return False
        if self.is_intervention_suppressed(action_or_area):
            return True
        target = str(action_or_area).strip().lower().replace("-", "_").replace(" ", "_")
        return any(
            target in str(p).lower().replace("-", "_").replace(" ", "_")
            or str(p).lower().replace("-", "_").replace(" ", "_") in target
            for p in self.preserved_capabilities
        )

    def should_preserve(self, capability: str) -> bool:
        """Check if capability is in preserved capabilities."""
        if not capability or not str(capability).strip():
            return False
        target = str(capability).strip().lower().replace("-", "_").replace(" ", "_")
        return any(
            target in str(p).lower().replace("-", "_").replace(" ", "_")
            or str(p).lower().replace("-", "_").replace(" ", "_") in target
            for p in self.preserved_capabilities
        )

    def should_compensate(self, compensation: str) -> bool:
        """Check if compensation is in active compensations."""
        if not compensation or not str(compensation).strip():
            return False
        target = str(compensation).strip().lower().replace("-", "_").replace(" ", "_")
        return any(
            target in str(c).lower().replace("-", "_").replace(" ", "_")
            or str(c).lower().replace("-", "_").replace(" ", "_") in target
            for c in self.active_compensations
        )

    def should_intervene(self, action_or_area: str) -> bool:
        """Evaluate if S-Class should actively intervene in this action/area."""
        if not action_or_area or not str(action_or_area).strip():
            return False
        if self.is_intervention_suppressed(action_or_area):
            return False
        if self.is_intervention_allowed(action_or_area):
            return True
        target = str(action_or_area).strip().lower().replace("-", "_").replace(" ", "_")
        return any(
            target in str(c).lower().replace("-", "_").replace(" ", "_")
            or str(c).lower().replace("-", "_").replace(" ", "_") in target
            for c in self.active_compensations
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize ControlPolicy to dictionary."""
        return {
            "platform_id": self.platform_id,
            "observation_mode": self.observation_mode,
            "verification_gate": self.verification_gate,
            "checkpoint_frequency": self.checkpoint_frequency,
            "context_injection_limit": self.context_injection_limit,
            "interruption_policy": self.interruption_policy,
            "escalation_policy": self.escalation_policy,
            "allowed_interventions": list(self.allowed_interventions),
            "suppressed_interventions": list(self.suppressed_interventions),
            "active_compensations": list(self.active_compensations),
            "preserved_capabilities": list(self.preserved_capabilities),
            "budget": self.budget.to_dict(),
            "rationale": list(self.rationale),
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize ControlPolicy to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> ControlPolicy:
        """Construct ControlPolicy from dictionary."""
        return cls(
            platform_id=str(d.get("platform_id", "generic")),
            observation_mode=str(d.get("observation_mode", ObservationLevel.SAMPLED.value)),
            verification_gate=str(d.get("verification_gate", VerificationLevel.STANDARD.value)),
            checkpoint_frequency=str(d.get("checkpoint_frequency", CheckpointLevel.MILESTONE_ONLY.value)),
            context_injection_limit=int(d.get("context_injection_limit", 2048)),
            interruption_policy=str(d.get("interruption_policy", InterruptionPolicy.FATAL_ONLY.value)),
            escalation_policy=str(d.get("escalation_policy", EscalationPolicy.FAIL_CLOSED.value)),
            allowed_interventions=list(d.get("allowed_interventions", [])),
            suppressed_interventions=list(d.get("suppressed_interventions", [])),
            active_compensations=list(d.get("active_compensations", [])),
            preserved_capabilities=list(d.get("preserved_capabilities", [])),
            budget=PerformanceBudget.from_dict(d.get("budget", {})),
            rationale=list(d.get("rationale", [])),
        )


class PlatformOptimizationEngine:
    """
    Reconciles PlatformProfile + Task + Risk + State + PerformanceBudget -> ControlPolicy.
    """

    def __init__(self):
        pass

    @classmethod
    def reconcile(
        cls,
        profile: PlatformProfile,
        task: Optional[Any] = None,
        risk: Optional[Union[Dict[str, Any], str, float]] = None,
        state: Optional[Dict[str, Any]] = None,
        budget: Optional[PerformanceBudget] = None,
        compensation_policy: Optional[CompensationPolicy] = None,
        code_intel_signals: Optional[Dict[str, Any]] = None,
        budget_controller: Optional[VerificationBudgetController] = None,
    ) -> ControlPolicy:
        """
        Reconcile platform profile, task demands, risk posture, current state,
        and performance budget to produce a tailored ControlPolicy.
        """
        # 1. Base Compensation Policy from archetype or parameter
        if compensation_policy is None:
            _, compensation_policy = get_archetype(profile.platform_id)

        obs_mode = compensation_policy.observation_level
        verif_gate = compensation_policy.verification_level
        chk_freq = compensation_policy.checkpoint_level
        ctx_limit = compensation_policy.context_budget
        int_policy = compensation_policy.interruption_policy
        esc_policy = compensation_policy.escalation_policy

        allowed: Set[str] = set()
        suppressed: Set[str] = set()
        active_comps: Set[str] = set(compensation_policy.compensate)
        preserved: Set[str] = set(compensation_policy.preserve)
        rationale: List[str] = []

        # 2. Translate Avoid Interference rules into concrete intervention suppression
        for avoid in compensation_policy.avoid_interference:
            avoid_lower = avoid.lower()
            if "interruption" in avoid_lower:
                suppressed.add("unnecessary_interruptions")
                suppressed.add("interactive_micro_prompts")
            if "planning" in avoid_lower:
                suppressed.add("duplicate_planning")
                suppressed.add("planning_override")
            if "context" in avoid_lower:
                ctx_limit = min(ctx_limit, 2048)
                suppressed.add("huge_context_injection")
            if "checkpoint" in avoid_lower:
                suppressed.add("constant_micro_checkpoints")
                if chk_freq == CheckpointLevel.CONTINUOUS.value:
                    chk_freq = CheckpointLevel.MILESTONE_ONLY.value
            if "history" in avoid_lower:
                suppressed.add("redundant_history_injection")
            if "re-derive" in avoid_lower or "rederive" in avoid_lower:
                suppressed.add("state_rederivation_prompts")
            if "serializ" in avoid_lower:
                suppressed.add("task_serialization")
            if "bottleneck" in avoid_lower:
                suppressed.add("agent_delegation_bottlenecks")
            if "locking" in avoid_lower:
                suppressed.add("global_workspace_lock")

        # 3. Analyze Task Complexity
        if task is not None:
            task_title = getattr(task, "title", str(task) if not isinstance(task, dict) else task.get("title", ""))
            task_desc = getattr(task, "description", task.get("description", "") if isinstance(task, dict) else "")
            combined_task_text = f"{task_title} {task_desc}".lower()
            
            if any(k in combined_task_text for k in ["security", "auth", "crypto", "permission", "credential"]):
                rationale.append("Security-sensitive task detected: activating cryptographic evidence gating.")
                allowed.add("security_boundary_enforcement")
                active_comps.add("security_containment")
                if verif_gate == VerificationLevel.MINIMAL.value:
                    verif_gate = VerificationLevel.STANDARD.value

            if any(k in combined_task_text for k in ["refactor", "migration", "architecture", "deprecat"]):
                rationale.append("Structural refactoring task detected: activating regression detection.")
                allowed.add("regression_detection")
                active_comps.add("regression_detection")

        # 4. Analyze Risk
        risk_level = "low"
        if isinstance(risk, (int, float)):
            if risk >= 0.8:
                risk_level = "critical"
            elif risk >= 0.5:
                risk_level = "high"
            elif risk >= 0.2:
                risk_level = "medium"
            else:
                risk_level = "low"
        elif isinstance(risk, str):
            risk_level = risk.strip().lower()
        elif isinstance(risk, dict):
            risk_level = str(risk.get("level", "low")).lower()

        if risk_level in ("critical", "high"):
            rationale.append(f"Elevated risk ({risk_level}): enforcing strict verification gate and fail-closed boundaries.")
            allowed.add("security_boundary_enforcement")
            allowed.add("regression_detection")
            allowed.add("evidence_verification")
            if verif_gate in (VerificationLevel.MINIMAL.value, VerificationLevel.STANDARD.value):
                verif_gate = VerificationLevel.THOROUGH.value
            esc_policy = EscalationPolicy.FAIL_CLOSED.value
        else:
            rationale.append("Low/normal operational risk: preserving platform autonomy and suppressing invasive verifiers.")
            suppressed.add("mutation_testing")
            suppressed.add("synchronous_barrier")

        # 4b. Analyze Code Intelligence Signals (AST Blast Radius, Transitive Impact)
        if code_intel_signals:
            blast_radius = int(code_intel_signals.get("blast_radius", 0))
            critical_path = bool(code_intel_signals.get("critical_path", False))
            if blast_radius >= 5 or critical_path:
                rationale.append(
                    f"Code intelligence signal (blast_radius={blast_radius}, critical_path={critical_path}): "
                    f"elevating verification gate to thorough and activating blast radius containment."
                )
                verif_gate = VerificationLevel.THOROUGH.value
                allowed.add("blast_radius_containment")
                allowed.add("transitive_impact_analysis")
                active_comps.add("blast_radius_containment")
            elif blast_radius > 0:
                rationale.append(f"Code intelligence signal (blast_radius={blast_radius}): activating transitive impact analysis.")
                allowed.add("transitive_impact_analysis")
                active_comps.add("blast_radius_containment")

        # 5. Analyze State
        if state:
            subagents = int(state.get("subagents_count", state.get("subagent_count", 0)))
            if subagents > 1 or profile.platform_id == "antigravity":
                rationale.append(f"Multi-agent swarm active ({subagents} subagents): activating cross-agent invalidation and conflict detection.")
                allowed.add("cross_agent_invalidation")
                allowed.add("conflict_detection")
                allowed.add("evidence_merging")
                active_comps.add("cross-agent invalidation")
                active_comps.add("conflict detection")
                if esc_policy != EscalationPolicy.FAIL_CLOSED.value:
                    esc_policy = EscalationPolicy.QUARANTINE_SUBAGENT.value

            consecutive_failures = int(state.get("consecutive_failures", 0))
            if consecutive_failures >= 2:
                rationale.append(f"Detected {consecutive_failures} consecutive failures: elevating verification level.")
                verif_gate = VerificationLevel.THOROUGH.value
                allowed.add("fast_feedback")

        # 6. Evaluate Performance Budget & Apply Dynamic Throttling
        active_budget = budget or PerformanceBudget()
        headrooms = active_budget.budget_headroom_pct()

        # Check Token Headroom
        if headrooms["tokens"] < 25.0:
            rationale.append(f"Token budget constrained ({headrooms['tokens']}% headroom): compressing context injection.")
            ctx_limit = max(512, ctx_limit // 2)
            suppressed.add("verbose_metadata_injection")

        # Check Latency Headroom
        if headrooms["latency"] < 25.0:
            if risk_level in ("critical", "high"):
                rationale.append(f"Latency constrained ({headrooms['latency']}% headroom) but risk is {risk_level}: maintaining strict verification priority over latency.")
            else:
                rationale.append(f"Latency budget constrained ({headrooms['latency']}% headroom): downshifting observation mode.")
                obs_mode = ObservationLevel.PASSIVE.value
                suppressed.add("synchronous_ledger_wait")

        # Check Interruption Headroom
        if headrooms["interruptions"] <= 0.0:
            if risk_level in ("critical", "high"):
                rationale.append(f"Interruption quota depleted during {risk_level} risk: enforcing fail-closed escalation without interactive prompts.")
                int_policy = InterruptionPolicy.FATAL_ONLY.value
                esc_policy = EscalationPolicy.FAIL_CLOSED.value
            else:
                rationale.append("Interruption budget depleted: strictly forbidding interactive prompts.")
                int_policy = InterruptionPolicy.FATAL_ONLY.value
            suppressed.add("interactive_micro_prompts")
            suppressed.add("milestone_prompts")

        # Net Utility Check
        net_ratio = active_budget.compute_net_utility_ratio()
        if net_ratio < 1.0 and active_budget.compute_overhead_score() > 10.0:
            rationale.append(f"Net utility ratio ({net_ratio}) below break-even: shedding non-essential verification.")
            suppressed.add("exhaustive_lint_checks")
            suppressed.add("mutation_testing")

        # 6b. Verification Budget Controller Dynamic Degradation
        if budget_controller is not None:
            if budget_controller.should_degrade():
                orig_gate = verif_gate
                verif_gate = budget_controller.recommended_verification_tier(verif_gate, risk_level)
                rationale.append(
                    f"Verification budget degradation triggered ({budget_controller.check_headroom()}): "
                    f"gracefully downshifting verification tier from {orig_gate} to {verif_gate}."
                )

        # 7. Archetype-Specific Enhancements
        pid = profile.platform_id.lower()
        if pid == "codex":
            allowed.add("fast_feedback")
            allowed.add("regression_detection")
            allowed.add("claim_verification")
            suppressed.add("duplicate_planning")
            suppressed.add("constant_micro_checkpoints")
            suppressed.add("interactive_micro_prompts")
            rationale.append("Codex archetype applied: letting Codex run autonomously while gating accuracy and regressions.")

        elif pid == "claude_code":
            allowed.add("execution_bookkeeping")
            allowed.add("state_tracking")
            allowed.add("continuous_validation")
            suppressed.add("redundant_history_injection")
            suppressed.add("state_rederivation_prompts")
            rationale.append("Claude Code archetype applied: taking over execution bookkeeping so Claude spends intelligence on reasoning.")

        elif pid == "antigravity":
            allowed.add("cross_agent_invalidation")
            allowed.add("conflict_detection")
            allowed.add("evidence_merging")
            allowed.add("global_verification")
            suppressed.add("task_serialization")
            suppressed.add("agent_blocking")
            rationale.append("Antigravity archetype applied: maximizing parallel intelligence with parallel integrity.")

        elif pid == "cursor":
            allowed.add("multi_file_diff_verification")
            allowed.add("import_validation")
            allowed.add("syntax_integrity")
            suppressed.add("blocking_keystroke_checks")
            suppressed.add("interactive_micro_prompts")
            rationale.append("Cursor archetype applied: preserving fluid in-line editing while verifying multi-file diffs silently.")

        # Ensure suppressed interventions take precedence EXCEPT mandatory security controls under elevated risk
        if risk_level in ("critical", "high"):
            mandatory_security = {"security_boundary_enforcement", "evidence_verification", "regression_detection"}
            final_allowed = [a for a in sorted(allowed) if a not in suppressed or a in mandatory_security]
        else:
            final_allowed = [a for a in sorted(allowed) if a not in suppressed]
        final_suppressed = sorted(suppressed)

        return ControlPolicy(
            platform_id=profile.platform_id,
            observation_mode=obs_mode,
            verification_gate=verif_gate,
            checkpoint_frequency=chk_freq,
            context_injection_limit=ctx_limit,
            interruption_policy=int_policy,
            escalation_policy=esc_policy,
            allowed_interventions=final_allowed,
            suppressed_interventions=final_suppressed,
            active_compensations=sorted(list(active_comps)),
            preserved_capabilities=sorted(list(preserved)),
            budget=active_budget,
            rationale=rationale,
        )

    @classmethod
    def evaluate_intervention(
        cls,
        platform_id: str,
        action: str,
        risk: Optional[Union[Dict[str, Any], str, float]] = None,
        code_intel_signals: Optional[Dict[str, Any]] = None,
        budget_controller: Optional[VerificationBudgetController] = None,
        consecutive_failures: int = 0,
        policy_violation: bool = False,
    ) -> InterventionResult:
        """
        Evaluate intervention decision for a specific platform action using InterventionPolicy.
        """
        risk_score = 0.0
        if isinstance(risk, (int, float)):
            risk_score = float(risk)
        elif isinstance(risk, str):
            mapping = {"low": 0.1, "medium": 0.4, "high": 0.7, "critical": 0.95}
            risk_score = mapping.get(risk.lower(), 0.3)
        elif isinstance(risk, dict):
            raw = risk.get("score", risk.get("level", 0.0))
            if isinstance(raw, (int, float)):
                risk_score = float(raw)
            elif isinstance(raw, str):
                mapping = {"low": 0.1, "medium": 0.4, "high": 0.7, "critical": 0.95}
                risk_score = mapping.get(raw.lower(), 0.3)

        blast_radius = 0
        if code_intel_signals:
            blast_radius = int(code_intel_signals.get("blast_radius", 0))

        is_exhausted = False
        if budget_controller:
            is_exhausted = budget_controller.is_budget_exhausted()

        policy = InterventionPolicy(platform_id)
        result = policy.evaluate(
            action=action,
            risk_score=risk_score,
            blast_radius=blast_radius,
            is_budget_exhausted=is_exhausted,
            consecutive_failures=consecutive_failures,
            policy_violation=policy_violation,
        )

        if budget_controller and result.decision == InterventionDecision.VERIFY.value:
            risk_str = "critical" if risk_score >= 0.8 else ("high" if risk_score >= 0.5 else ("medium" if risk_score >= 0.2 else "low"))
            recommended = budget_controller.recommended_verification_tier(result.recommended_tier, risk_str)
            if recommended != result.recommended_tier:
                result = InterventionResult(
                    decision=result.decision,
                    action=result.action,
                    reason=f"{result.reason} [Verification tier degraded to {recommended} by budget controller]",
                    recommended_tier=recommended,
                    escalate=result.escalate,
                    suppress_notification=result.suppress_notification,
                    metadata=dict(result.metadata),
                )
        return result

