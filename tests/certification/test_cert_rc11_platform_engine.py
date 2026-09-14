"""
Certification Suite: RC.11 Platform Profile Engine, Compensation Policy, Verification Budget & Intervention Controller.
Certifies:
1. Codex platform reconciliation: long-horizon autonomy preservation, regression gating, micro-prompt suppression.
2. Claude Code platform reconciliation: reasoning preservation, execution bookkeeping, and state tracking.
3. Antigravity platform reconciliation: multi-agent swarm support, conflict detection, and parallel integrity.
4. Cursor platform reconciliation: fast inline editor preservation, multi-file diff verification.
5. Code intelligence signal integration: AST blast-radius and critical-path signals dynamically elevate verification gating.
6. VerificationBudgetController tracking: tokens, latency ms, compute cpu sec, cost USD, and headroom calculations.
7. Budget exhaustion graceful degradation: reduces verification tier instead of failing, while preserving standard gating on critical risk.
8. InterventionPolicy decisions: INTERVENE, STAY_SILENT, VERIFY, TERMINATE, and ESCALATE across platform archetypes.
"""

import pytest

from sclass.platform.profile import PlatformProfile
from sclass.platform.archetypes import (
    get_codex_profile,
    get_claude_code_profile,
    get_antigravity_profile,
    get_cursor_profile,
)
from sclass.platform.engine import PlatformOptimizationEngine
from sclass.platform.policy import (
    InterventionPolicy,
    InterventionDecision,
    VerificationLevel,
)
from sclass.platform.budget import (
    VerificationBudgetController,
    VerificationBudgetLimits,
    PerformanceBudget,
)


def test_rc11_platform_reconciliation_codex():
    """Certifies Codex archetype reconciliation: long-running autonomy preserved, micro-prompts suppressed."""
    profile = get_codex_profile()
    policy = PlatformOptimizationEngine.reconcile(profile=profile, risk="low")

    assert policy.platform_id == "codex"
    assert "interactive_micro_prompts" in policy.suppressed_interventions
    assert "constant_micro_checkpoints" in policy.suppressed_interventions
    assert "regression_detection" in policy.allowed_interventions
    assert "fast_feedback" in policy.allowed_interventions
    assert policy.should_stay_out_of_way("long_horizon_autonomy") is True


def test_rc11_platform_reconciliation_claude():
    """Certifies Claude Code archetype reconciliation: bookkeeping handled by S-Class, reasoning preserved."""
    profile = get_claude_code_profile()
    policy = PlatformOptimizationEngine.reconcile(profile=profile, risk="low")

    assert policy.platform_id == "claude_code"
    assert "execution_bookkeeping" in policy.allowed_interventions
    assert "state_tracking" in policy.allowed_interventions
    assert "redundant_history_injection" in policy.suppressed_interventions
    assert "state_rederivation_prompts" in policy.suppressed_interventions


def test_rc11_platform_reconciliation_antigravity():
    """Certifies Antigravity archetype reconciliation: multi-agent swarm integrity and conflict detection."""
    profile = get_antigravity_profile()
    state = {"subagents_count": 4}
    policy = PlatformOptimizationEngine.reconcile(profile=profile, state=state, risk="medium")

    assert policy.platform_id == "antigravity"
    assert "cross_agent_invalidation" in policy.allowed_interventions
    assert "conflict_detection" in policy.allowed_interventions
    assert "evidence_merging" in policy.allowed_interventions
    assert "task_serialization" in policy.suppressed_interventions


def test_rc11_platform_reconciliation_cursor():
    """Certifies Cursor archetype reconciliation: inline editor speed preserved, multi-file diffs verified."""
    profile = get_cursor_profile()
    policy = PlatformOptimizationEngine.reconcile(profile=profile, risk="low")

    assert policy.platform_id == "cursor"
    assert "multi_file_diff_verification" in policy.allowed_interventions
    assert "syntax_integrity" in policy.allowed_interventions
    assert "blocking_keystroke_checks" in policy.suppressed_interventions
    assert policy.should_stay_out_of_way("inline typing flow") is True


def test_rc11_code_intelligence_signal_integration():
    """Certifies that Code Intelligence signals (blast radius, critical path) dynamically elevate verification."""
    profile = get_cursor_profile()

    # Normal low-risk task without code intelligence signals defaults to standard gate
    normal_policy = PlatformOptimizationEngine.reconcile(profile=profile, risk="low")
    assert normal_policy.verification_gate == VerificationLevel.STANDARD.value

    # With high blast radius (>=5 symbols), verification gate elevates to thorough
    code_intel = {"blast_radius": 12, "critical_path": True, "affected_symbols": ["auth.login", "auth.token"]}
    elevated_policy = PlatformOptimizationEngine.reconcile(
        profile=profile,
        risk="low",
        code_intel_signals=code_intel,
    )
    assert elevated_policy.verification_gate == VerificationLevel.THOROUGH.value
    assert "blast_radius_containment" in elevated_policy.allowed_interventions
    assert "transitive_impact_analysis" in elevated_policy.allowed_interventions
    assert any("Code intelligence signal" in r for r in elevated_policy.rationale)


def test_rc11_verification_budget_controller_tracking():
    """Certifies VerificationBudgetController resource tracking, consumption accumulation, and headroom."""
    limits = VerificationBudgetLimits(
        max_tokens=10000,
        max_latency_ms=2000.0,
        max_compute_cpu_sec=10.0,
        max_cost_usd=1.0,
        degradation_threshold_pct=20.0,
    )
    controller = VerificationBudgetController(limits=limits)

    assert controller.is_budget_exhausted() is False
    assert controller.should_degrade() is False

    headroom = controller.check_headroom()
    assert headroom["tokens"] == 100.0
    assert headroom["latency"] == 100.0

    # Consume half the token budget
    controller.record_verification(duration_ms=400.0, tokens=5000, compute_cpu_sec=1.5, cost_usd=0.2)
    assert controller.verifications_run == 1
    metrics = controller.get_metrics()
    assert metrics["tokens_consumed"] == 5000
    assert metrics["latency_ms_consumed"] == 400.0
    assert metrics["headroom_pct"]["tokens"] == 50.0
    assert controller.should_degrade() is False


def test_rc11_budget_exhaustion_graceful_degradation():
    """Certifies graceful degradation: downshifting verification tiers instead of throwing errors."""
    limits = VerificationBudgetLimits(
        max_tokens=1000,
        max_latency_ms=500.0,
        degradation_threshold_pct=15.0,
    )
    controller = VerificationBudgetController(limits=limits)

    # Exhaust tokens to 90% (10% headroom <= 15% threshold)
    controller.record_verification(tokens=920, duration_ms=400.0)
    assert controller.should_degrade() is True

    # 1. Medium risk: thorough downshifts to standard, standard downshifts to minimal
    tier_med = controller.recommended_verification_tier(requested_tier="thorough", risk_level="medium")
    assert tier_med == "standard"
    tier_std = controller.recommended_verification_tier(requested_tier="standard", risk_level="medium")
    assert tier_std == "minimal"

    # 2. Critical risk: security boundary L3/L8 cannot degrade below standard
    tier_crit = controller.recommended_verification_tier(requested_tier="thorough", risk_level="critical")
    assert tier_crit == "standard"
    tier_crit_std = controller.recommended_verification_tier(requested_tier="standard", risk_level="critical")
    assert tier_crit_std == "standard"

    # 3. Integration with PlatformOptimizationEngine.reconcile
    profile = get_codex_profile()
    degraded_policy = PlatformOptimizationEngine.reconcile(
        profile=profile,
        risk="medium",
        budget_controller=controller,
    )
    assert degraded_policy.verification_gate == "minimal"
    assert any("Verification budget degradation triggered" in r for r in degraded_policy.rationale)


def test_rc11_intervention_policy_decisions():
    """Certifies InterventionPolicy evaluates INTERVENE, STAY_SILENT, VERIFY, TERMINATE, ESCALATE correctly."""
    # 1. STAY_SILENT on low risk typing/reasoning
    cursor_res = PlatformOptimizationEngine.evaluate_intervention(
        platform_id="cursor",
        action="inline_edit",
        risk="low",
    )
    assert cursor_res.decision == InterventionDecision.STAY_SILENT.value
    assert cursor_res.suppress_notification is True

    # 2. VERIFY on high blast radius
    intel = {"blast_radius": 8}
    verify_res = PlatformOptimizationEngine.evaluate_intervention(
        platform_id="codex",
        action="mutate_auth_module",
        risk="medium",
        code_intel_signals=intel,
    )
    assert verify_res.decision == InterventionDecision.VERIFY.value
    assert verify_res.recommended_tier == VerificationLevel.THOROUGH.value

    # 3. INTERVENE on Antigravity lease conflict
    antigrav_res = PlatformOptimizationEngine.evaluate_intervention(
        platform_id="antigravity",
        action="resolve_symbol_lease_conflict",
        risk="low",
    )
    assert antigrav_res.decision == InterventionDecision.INTERVENE.value

    # 4. TERMINATE on critical invariant violation
    term_res = PlatformOptimizationEngine.evaluate_intervention(
        platform_id="generic",
        action="bypass_authorization_kernel",
        risk=0.95,
        consecutive_failures=3,
        policy_violation=True,
    )
    assert term_res.decision == InterventionDecision.TERMINATE.value
    assert term_res.escalate is True

    # 5. ESCALATE when budget is exhausted under high risk
    exhausted_limits = VerificationBudgetLimits(max_tokens=100)
    ctrl = VerificationBudgetController(limits=exhausted_limits)
    ctrl.record_verification(tokens=150)
    assert ctrl.is_budget_exhausted() is True

    esc_res = PlatformOptimizationEngine.evaluate_intervention(
        platform_id="generic",
        action="run_security_scan",
        risk=0.75,
        budget_controller=ctrl,
    )
    assert esc_res.decision == InterventionDecision.ESCALATE.value
    assert esc_res.escalate is True
