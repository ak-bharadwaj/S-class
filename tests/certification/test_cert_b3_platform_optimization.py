"""
S-Class Phase B: B.3 Platform Optimization Core Certification Suite.

Certifies:
1. Generic PlatformProfile architecture (B.3.1) with zero hardcoded permanent superiority assumptions.
2. CompensationPolicy primitives (B.3.2) articulating where S-Class intervenes and where it stays out of the way.
3. The three initial optimization archetypes:
   - OpenAI Codex: "Let Codex run. Make the result more trustworthy."
   - Anthropic Claude Code: "Let Claude spend intelligence on reasoning; S-Class handles control bookkeeping."
   - Google Antigravity: "Let Antigravity maximize parallel intelligence; S-Class maximizes parallel integrity."
4. PerformanceBudget tracking across 7 overhead dimensions and computing Net Utility Ratio:
   useful_reliability_gained / S-Class overhead.
5. PlatformOptimizationEngine reconciling Profile + Task + Risk + State + Budget -> ControlPolicy.
6. Platform comparison benchmark measuring Native vs Native + S-Class across 9 operational dimensions.
7. Explicit architectural separation between CI Thresholds (tolerating VM jitter) and Product SLAs (strict engineering targets).
"""

import json
import pytest
from sclass.platform import (
    PlatformProfile,
    ExecutionStyle,
    ContextStyle,
    ConcurrencyModel,
    LongHorizonModel,
    CheckpointModel,
    ToolModel,
    CompensationPolicy,
    ObservationLevel,
    VerificationLevel,
    CheckpointLevel,
    InterruptionPolicy,
    EscalationPolicy,
    PerformanceBudget,
    BudgetLimits,
    OverheadConsumption,
    ReliabilityGain,
    PlatformOptimizationEngine,
    ControlPolicy,
    PlatformComparisonBenchmark,
    PlatformComparisonResult,
    PlatformMetrics,
    CIThresholds,
    ProductSLA,
    calculate_distribution,
    get_archetype,
    register_archetype,
    list_archetypes,
    get_codex_profile,
    get_codex_compensation_policy,
    get_claude_code_profile,
    get_claude_code_compensation_policy,
    get_antigravity_profile,
    get_antigravity_compensation_policy,
)


# ==============================================================================
# 1. B.3.1 — Platform Profile Contract & Flexibility
# ==============================================================================

def test_b3_1_platform_profile_contract_and_serialization():
    """Certifies generic PlatformProfile fields, validation, and JSON round-trip."""
    profile = PlatformProfile(
        platform_id="test_platform",
        version="2.0.1",
        capabilities=["terminal_execution", "ast_analysis", "mcp_client"],
        execution_style=ExecutionStyle.AUTONOMOUS_LONG_HORIZON.value,
        context_style=ContextStyle.PERSISTENT_SESSION.value,
        concurrency_model=ConcurrencyModel.PARALLEL_AGENTS.value,
        long_horizon_model=LongHorizonModel.AUTONOMOUS_SESSION.value,
        checkpoint_model=CheckpointModel.HARNESS_NATIVE.value,
        tool_model=ToolModel.AGENTS_API_TOOLS.value,
        native_strengths=["long_horizon_execution", "terminal_speed"],
        metadata={"custom_flag": True},
    )

    assert profile.platform_id == "test_platform"
    assert profile.version == "2.0.1"
    assert profile.has_capability("terminal_execution") is True
    assert profile.has_capability("non_existent") is False
    assert profile.has_strength("long_horizon_execution") is True
    assert profile.has_strength("unsupported_strength") is False

    # Immutability check
    with pytest.raises((AttributeError, TypeError)):
        profile.version = "3.0.0"  # type: ignore

    # Serialization roundtrip
    d = profile.to_dict()
    reconstructed = PlatformProfile.from_dict(d)
    assert reconstructed == profile

    json_str = profile.to_json()
    from_json = PlatformProfile.from_json(json_str)
    assert from_json == profile


def test_b3_1_no_permanent_assumptions_invariant():
    """
    Certifies that profiles do NOT encode immutable assumptions.
    A caller can create or override any profile dynamically (e.g. Codex reasoning or Claude long-horizon).
    """
    # A custom profile asserting Codex used in single-step deep reasoning mode
    custom_codex = PlatformProfile(
        platform_id="codex",
        version="experimental",
        capabilities=["deep_reasoning_step"],
        execution_style=ExecutionStyle.DEEP_REASONING_STEP.value,
        native_strengths=["deep_reasoning"],
    )
    assert custom_codex.execution_style == ExecutionStyle.DEEP_REASONING_STEP.value
    assert custom_codex.has_strength("deep_reasoning")

    # Cloned with modification
    evolved = custom_codex.clone_with(version="experimental-v2", native_strengths=["swarm_collaboration"])
    assert evolved.version == "experimental-v2"
    assert evolved.has_strength("swarm_collaboration")
    assert not evolved.has_strength("deep_reasoning")


# ==============================================================================
# 2. B.3.2 — Compensation Policy Contract
# ==============================================================================

def test_b3_2_compensation_policy_contract():
    """Certifies CompensationPolicy fields, preserve/compensate/avoid logic, and serialization."""
    policy = CompensationPolicy(
        preserve=["native_shell_execution", "multi_turn_autonomy"],
        compensate=["accuracy", "regression_detection", "security_boundaries"],
        avoid_interference=["unnecessary_interruptions", "duplicate_planning", "huge_context_injection"],
        observation_level=ObservationLevel.SAMPLED.value,
        verification_level=VerificationLevel.STANDARD.value,
        checkpoint_level=CheckpointLevel.MILESTONE_ONLY.value,
        context_budget=2048,
        interruption_policy=InterruptionPolicy.FATAL_ONLY.value,
        escalation_policy=EscalationPolicy.FAIL_CLOSED.value,
    )

    # Behavior predicates
    assert policy.should_preserve("native_shell_execution") is True
    assert policy.should_preserve("arbitrary_feature") is False
    assert policy.should_compensate("regression_detection") is True
    assert policy.should_avoid("unnecessary_interruptions") is True
    assert policy.should_avoid("duplicate_planning") is True

    # Interruption gating
    assert policy.permits_interruption("minor_status_update") is False
    assert policy.permits_interruption("fatal_corruption_detected") is True
    assert policy.permits_interruption("unauthorized_boundary_breach") is False  # FATAL_ONLY does not allow general breach unless fatal

    # Policy serialization
    d = policy.to_dict()
    reconstructed = CompensationPolicy.from_dict(d)
    assert reconstructed == policy

    json_str = policy.to_json()
    from_json = CompensationPolicy.from_json(json_str)
    assert from_json == policy


# ==============================================================================
# 3. Phase 2 — The Three Initial Optimization Archetypes
# ==============================================================================

def test_archetype_codex_optimization_profile():
    """
    Certifies Codex archetype:
    "Let Codex run. Make the result more trustworthy."
    Preserves autonomy, iteration, and parallel work.
    Compensates accuracy, regressions, and verification.
    Avoids unnecessary interruptions, duplicate planning, huge context, micro-checkpoints.
    """
    profile = get_codex_profile()
    policy = get_codex_compensation_policy()

    assert profile.platform_id == "codex"
    assert profile.execution_style == ExecutionStyle.AUTONOMOUS_LONG_HORIZON.value
    assert profile.concurrency_model == ConcurrencyModel.PARALLEL_AGENTS.value
    assert profile.has_strength("long-horizon autonomy")
    assert profile.has_strength("parallel work")

    # Preserve
    assert policy.should_preserve("long-horizon autonomy")
    assert policy.should_preserve("terminal execution")
    assert policy.should_preserve("parallel work")

    # Compensate
    assert policy.should_compensate("accuracy")
    assert policy.should_compensate("regression detection")
    assert policy.should_compensate("evidence quality")

    # Avoid interference
    assert policy.should_avoid("unnecessary interruptions")
    assert policy.should_avoid("duplicate planning")
    assert policy.should_avoid("huge context injection")
    assert policy.should_avoid("constant micro-checkpoints")

    assert policy.checkpoint_level == CheckpointLevel.MILESTONE_ONLY.value
    assert policy.context_budget <= 2048
    assert policy.interruption_policy == InterruptionPolicy.FATAL_ONLY.value


def test_archetype_claude_code_optimization_profile():
    """
    Certifies Claude Code archetype:
    "Let Claude spend intelligence on reasoning; S-Class handles control bookkeeping."
    Preserves deep reasoning, context synthesis, deliberate review.
    Compensates bookkeeping, context duplication, token waste, state tracking.
    Avoids feeding redundant history, making Claude re-derive state, unnecessary interruptions.
    """
    profile = get_claude_code_profile()
    policy = get_claude_code_compensation_policy()

    assert profile.platform_id == "claude_code"
    assert profile.execution_style == ExecutionStyle.DEEP_REASONING_STEP.value
    assert profile.has_strength("deep reasoning")
    assert profile.has_strength("architecture analysis")

    # Preserve
    assert policy.should_preserve("deep reasoning")
    assert policy.should_preserve("careful implementation")
    assert policy.should_preserve("deliberate review")

    # Compensate
    assert policy.should_compensate("execution bookkeeping")
    assert policy.should_compensate("context duplication")
    assert policy.should_compensate("token waste")
    assert policy.should_compensate("state tracking")

    # Avoid interference
    assert policy.should_avoid("feeding redundant history")
    assert policy.should_avoid("making Claude re-derive known state")
    assert policy.should_avoid("interrupting reasoning unnecessarily")

    # S-Class handles state tracking and trims injected context
    assert policy.observation_level == ObservationLevel.PASSIVE.value
    assert policy.context_budget <= 1024


def test_archetype_antigravity_optimization_profile():
    """
    Certifies Antigravity archetype:
    "Let Antigravity maximize parallel intelligence; S-Class maximizes parallel integrity."
    Preserves parallelism, agent delegation, multi-agent collaboration.
    Compensates state consistency, conflict detection, duplicate work, evidence merging.
    Avoids serializing parallel tasks, bottlenecking agent delegation.
    """
    profile = get_antigravity_profile()
    policy = get_antigravity_compensation_policy()

    assert profile.platform_id == "antigravity"
    assert profile.execution_style == ExecutionStyle.PARALLEL_SWARM.value
    assert profile.concurrency_model == ConcurrencyModel.PARALLEL_AGENTS.value
    assert profile.has_strength("parallelism")
    assert profile.has_strength("agent delegation")
    assert profile.has_strength("multi-agent execution")

    # Preserve
    assert policy.should_preserve("parallelism")
    assert policy.should_preserve("agent delegation")
    assert policy.should_preserve("multi-agent execution")

    # Compensate
    assert policy.should_compensate("state consistency")
    assert policy.should_compensate("conflict detection")
    assert policy.should_compensate("duplicate work")
    assert policy.should_compensate("evidence merging")
    assert policy.should_compensate("cross-agent invalidation")
    assert policy.should_compensate("global verification")

    # Avoid
    assert policy.should_avoid("serializing parallel tasks")
    assert policy.should_avoid("bottlenecking agent delegation")

    # Escalation policy quarantines single offending subagent rather than halting swarm
    assert policy.escalation_policy == EscalationPolicy.QUARANTINE_SUBAGENT.value


def test_archetype_registry_and_custom_extension():
    """Certifies archetype lookup, registration, and fallback."""
    registered = list_archetypes()
    assert "codex" in registered
    assert "claude_code" in registered
    assert "antigravity" in registered

    # Custom registration
    register_archetype(
        "cursor_v2",
        lambda: PlatformProfile(platform_id="cursor_v2", native_strengths=["inline_prediction"]),
        lambda: CompensationPolicy(preserve=["inline_prediction"]),
    )
    p, pol = get_archetype("cursor_v2")
    assert p.platform_id == "cursor_v2"
    assert pol.should_preserve("inline_prediction")

    # Fallback for unknown platform
    unknown_p, unknown_pol = get_archetype("unseen_future_engine")
    assert unknown_p.platform_id == "unseen_future_engine"
    assert unknown_pol.should_preserve("general_execution")


# ==============================================================================
# 4. Phase 3 — Performance Budget & Net Utility Ratio
# ==============================================================================

def test_b3_performance_budget_overhead_tracking():
    """Certifies overhead tracking across the 7 dimensions: latency, tokens, context, tool_calls, checkpoints, interruptions, compute."""
    budget = PerformanceBudget(
        limits=BudgetLimits(
            max_latency_ms=100.0,
            max_tokens=5000,
            max_context_bytes=32000,
            max_tool_calls=10,
            max_checkpoints=3,
            max_interruptions=2,
            max_compute_cpu_sec=2.0,
        )
    )

    budget.record_overhead(
        latency_ms=25.0,
        tokens=1200,
        context_bytes=8192,
        tool_calls=2,
        checkpoints=1,
        interruptions=0,
        compute_cpu_sec=0.45,
    )

    assert budget.is_within_budget() is True
    assert len(budget.exceeded_dimensions()) == 0

    headroom = budget.budget_headroom_pct()
    assert headroom["latency"] == 75.0
    assert headroom["tokens"] == 76.0
    assert headroom["checkpoints"] == 66.7
    assert headroom["interruptions"] == 100.0

    # Trigger budget violation
    budget.record_overhead(latency_ms=90.0) # total 115.0ms > 100.0ms limit
    assert budget.is_within_budget() is False
    assert "latency_ms" in budget.exceeded_dimensions()


def test_b3_net_utility_ratio_calculation():
    """
    Certifies Net Utility Ratio formula:
    useful reliability gained / S-Class overhead
    """
    budget = PerformanceBudget()

    # Case A: High reliability gains with modest overhead -> high utility ratio
    budget.record_reliability_gain(
        regressions_prevented=2,      # 2 * 25.0 = 50.0
        security_violations_blocked=1,# 1 * 30.0 = 30.0
        verification_passes=4,        # 4 * 5.0  = 20.0
        accuracy_gain=0.10,           # 0.10 * 100 = 10.0
    )
    rel_score = budget.compute_reliability_score()
    assert rel_score == 110.0

    budget.record_overhead(
        latency_ms=30.0,    # 30.0 * 0.1 = 3.0
        tokens=500,         # 500 * 0.01 = 5.0
        context_bytes=2000, # 2000 * 0.0005 = 1.0
        interruptions=0,    # 0.0
    )
    ovh_score = budget.compute_overhead_score()
    assert ovh_score == 9.0

    ratio = budget.compute_net_utility_ratio()
    expected_ratio = round(110.0 / 9.0, 4)
    assert ratio == expected_ratio
    assert ratio > 10.0  # Demonstrates strong positive utility

    # Case B: Zero overhead with gains -> returns capped ceiling
    pure_gain_budget = PerformanceBudget()
    pure_gain_budget.record_reliability_gain(regressions_prevented=1)
    assert pure_gain_budget.compute_net_utility_ratio() == 100.0


# ==============================================================================
# 5. Engine Reconciliation: Profile + Task + Risk + State + Budget -> ControlPolicy
# ==============================================================================

def test_engine_reconcile_codex_autonomy():
    """
    Certifies engine reconciles Codex profile to:
    - Suppress duplicate planning and micro-checkpoints
    - Allow fast feedback and regression detection
    - Retain long-horizon autonomy without interruption
    """
    engine = PlatformOptimizationEngine()
    profile = get_codex_profile()
    budget = PerformanceBudget()

    policy = engine.reconcile(
        profile=profile,
        task={"title": "Implement auth middleware", "description": "High performance token validation"},
        risk="low",
        state={"subagents_count": 0},
        budget=budget,
    )

    assert policy.platform_id == "codex"
    assert policy.is_intervention_suppressed("duplicate_planning") is True
    assert policy.is_intervention_suppressed("constant_micro_checkpoints") is True
    assert policy.is_intervention_suppressed("interactive_micro_prompts") is True
    assert policy.is_intervention_allowed("fast_feedback") is True
    assert policy.checkpoint_frequency == CheckpointLevel.MILESTONE_ONLY.value
    assert policy.interruption_policy == InterruptionPolicy.FATAL_ONLY.value


def test_engine_reconcile_claude_bookkeeping():
    """
    Certifies engine reconciles Claude Code profile to:
    - Take over execution bookkeeping and state tracking
    - Suppress redundant history injection
    - Keep context injection tightly constrained
    """
    engine = PlatformOptimizationEngine()
    profile = get_claude_code_profile()

    policy = engine.reconcile(
        profile=profile,
        task={"title": "Refactor data abstraction layer", "description": "Clean architecture pass"},
        risk="medium",
        budget=PerformanceBudget(),
    )

    assert policy.platform_id == "claude_code"
    assert policy.is_intervention_allowed("execution_bookkeeping") is True
    assert policy.is_intervention_allowed("state_tracking") is True
    assert policy.is_intervention_suppressed("redundant_history_injection") is True
    assert policy.is_intervention_suppressed("state_rederivation_prompts") is True
    assert policy.context_injection_limit <= 1024


def test_engine_reconcile_antigravity_multi_agent():
    """
    Certifies engine reconciles Antigravity swarm:
    - Activates cross-agent invalidation and conflict detection
    - Suppresses task serialization locks
    - Sets escalation to QUARANTINE_SUBAGENT
    """
    engine = PlatformOptimizationEngine()
    profile = get_antigravity_profile()

    policy = engine.reconcile(
        profile=profile,
        task={"title": "Parallel multi-agent test migration"},
        state={"subagents_count": 5},
        risk="medium",
        budget=PerformanceBudget(),
    )

    assert policy.platform_id == "antigravity"
    assert policy.is_intervention_allowed("cross_agent_invalidation") is True
    assert policy.is_intervention_allowed("conflict_detection") is True
    assert policy.is_intervention_allowed("evidence_merging") is True
    assert policy.is_intervention_suppressed("task_serialization") is True
    assert policy.escalation_policy == EscalationPolicy.QUARANTINE_SUBAGENT.value


def test_engine_dynamic_budget_throttling():
    """
    Certifies engine dynamically throttles interventions when performance budget is constrained:
    - Compresses context injection when tokens run low
    - Downshifts observation mode when latency runs high
    - Forbids interactive prompts when interruption quota is exhausted
    """
    engine = PlatformOptimizationEngine()
    profile = get_codex_profile()
    budget = PerformanceBudget(
        limits=BudgetLimits(
            max_latency_ms=100.0,
            max_tokens=4000,
            max_interruptions=1,
        )
    )

    # Exhaust 85% of tokens and 90% of latency, plus 1 interruption
    budget.record_overhead(
        latency_ms=90.0,
        tokens=3500,
        interruptions=1,
    )

    policy = engine.reconcile(
        profile=profile,
        risk="low",
        budget=budget,
    )

    # Context injection must be compressed
    assert policy.context_injection_limit <= 1024
    # Observation mode shifted to passive to save latency
    assert policy.observation_mode == ObservationLevel.PASSIVE.value
    # Interruption policy strictly fatal_only with micro prompts suppressed
    assert policy.is_intervention_suppressed("interactive_micro_prompts") is True


# ==============================================================================
# 6. Phase 4 — Platform Comparison Benchmark & CI vs SLA Separation
# ==============================================================================

def test_b3_benchmark_distribution_calculation():
    """Certifies p50, p95, p99, mean, and stddev calculations."""
    samples = [10.0, 12.0, 15.0, 18.0, 20.0, 25.0, 30.0, 45.0, 60.0, 100.0]
    dist = calculate_distribution(samples)

    assert dist["count"] == 10
    assert dist["min"] == 10.0
    assert dist["max"] == 100.0
    assert dist["p50"] == 25.0
    assert dist["p95"] == 100.0
    assert dist["mean"] == 33.5
    assert dist["stddev"] > 0.0


def test_b3_benchmark_ci_threshold_vs_product_sla_distinction():
    """
    CRITICAL ARCHITECTURAL CERTIFICATION:
    CI threshold ≠ Product SLA
    
    Proves that a run with CI VM latency jitter (e.g. p50 = 65ms):
    - PASSES CIThreshold (tolerates <= 75ms)
    - FAILS ProductSLA (requires strict <= 25ms)
    
    Ensures S-Class never lowers product engineering standards to satisfy CI noise.
    """
    bench = PlatformComparisonBenchmark(
        ci_thresholds=CIThresholds(max_p50_latency_ms=75.0),
        product_sla=ProductSLA(max_p50_latency_ms=25.0),
    )

    native = PlatformMetrics(
        task_success_rate=0.88,
        correctness_score=0.85,
        regressions_count=2,
        time_to_completion_sec=12.0,
        token_count=15000,
        interruptions_count=0,
    )

    # S-Class run experiencing Windows CI runner jitter (p50 = 62.0ms)
    sclass = PlatformMetrics(
        task_success_rate=0.99,
        correctness_score=0.98,
        regressions_count=0,
        time_to_completion_sec=14.0,
        token_count=16000,
        interruptions_count=0,
        latency_samples_ms=[50.0, 58.0, 62.0, 65.0, 70.0, 72.0],
    )

    result = bench.evaluate_comparison("codex", native, sclass)

    # Must pass CI threshold because 62ms <= 75ms
    assert result.ci_passed is True, f"CI should pass under relaxed VM jitter: {result.ci_violations}"

    # Must FAIL Product SLA because 62ms > 25ms strict product requirement
    assert result.product_sla_passed is False, "Product SLA must reject jittery performance"
    assert any("p50 latency" in v for v in result.product_sla_violations)

    # Core thesis is still validated because reliability gain is high and regressions were eliminated
    assert result.thesis_proven is True
    assert result.net_utility_ratio >= 1.0


def test_b3_benchmark_full_platform_comparison_report():
    """
    Certifies full 9-dimension platform benchmark evaluation and report generation:
    1. Task success rate
    2. Correctness score
    3. Regressions count
    4. Time to completion
    5. Token overhead
    6. Interruptions
    7. Verification failures
    8. Retries
    9. Cost
    """
    bench = PlatformComparisonBenchmark()

    # Native Claude run: high reasoning, but accumulates unmonitored state drift & token waste
    native = PlatformMetrics(
        task_success_rate=0.90,
        correctness_score=0.88,
        regressions_count=1,
        time_to_completion_sec=20.0,
        token_count=25000,
        context_bytes=80000,
        interruptions_count=0,
        verification_failures_count=0,
        retries_count=3,
        cost_estimate_usd=0.0750,
        latency_samples_ms=[5.0, 8.0, 10.0, 12.0, 15.0],
    )

    # Native + S-Class: S-Class provides state bookkeeping, eliminating regressions with minimal overhead
    sclass = PlatformMetrics(
        task_success_rate=1.0,
        correctness_score=0.99,
        regressions_count=0,
        time_to_completion_sec=21.2,
        token_count=26500, # +6% token overhead
        context_bytes=82000,
        interruptions_count=0,
        verification_failures_count=2, # S-Class caught 2 invalid outputs before commit
        retries_count=1,
        cost_estimate_usd=0.0795,
        latency_samples_ms=[12.0, 15.0, 18.0, 20.0, 22.0], # p50 = 18.0ms <= 25.0ms SLA
    )

    result = bench.evaluate_comparison("claude_code", native, sclass)

    # Passes both CI and strict Product SLA
    assert result.ci_passed is True
    assert result.product_sla_passed is True
    assert result.thesis_proven is True
    assert result.net_utility_ratio >= 2.0

    # Verify report formatting contains key sections
    report = result.format_report()
    assert "CLAUDE_CODE" in report
    assert "Task Success Rate" in report
    assert "Correctness Score" in report
    assert "Regressions" in report
    assert "Token Overhead" in report
    assert "Net Utility Ratio" in report
    assert "**CI Status (Tolerant VM):** PASSED" in report
    assert "**Product SLA (Strict):** PASSED" in report
    assert "YES - S-Class improves the host platform" in report


def test_b3_benchmark_detects_net_negative_regression():
    """
    Certifies that if S-Class introduces excessive overhead without improving reliability,
    the benchmark detects thesis failure and flags net utility deficit.
    """
    bench = PlatformComparisonBenchmark()

    native = PlatformMetrics(
        task_success_rate=0.95,
        correctness_score=0.95,
        regressions_count=0,
        token_count=10000,
    )

    # Bad S-Class configuration with huge interruptions and low correctness
    bad_sclass = PlatformMetrics(
        task_success_rate=0.80,
        correctness_score=0.82,
        regressions_count=1,
        token_count=20000,
        interruptions_count=8,  # Excessive interruptions!
        latency_samples_ms=[120.0, 150.0, 200.0],
    )

    result = bench.evaluate_comparison("antigravity", native, bad_sclass)

    assert result.thesis_proven is False
    assert result.ci_passed is False
    assert result.product_sla_passed is False
    assert len(result.ci_violations) > 0
    assert len(result.product_sla_violations) > 0


# ==============================================================================
# 7. Edge Cases, Attack Vectors & Invariant Hardening
# ==============================================================================

def test_b3_2_should_stay_out_of_way_and_should_intervene():
    """
    Certifies the core S-Class question:
    Where should S-Class intervene, and where should it deliberately stay out of the way?
    """
    policy = get_codex_compensation_policy()
    assert policy.should_stay_out_of_way("long-horizon autonomy") is True
    assert policy.should_stay_out_of_way("terminal execution") is True
    assert policy.should_stay_out_of_way("duplicate planning") is True
    assert policy.should_intervene("regression detection") is True
    assert policy.should_intervene("accuracy") is True
    assert policy.should_intervene("verification") is True

    # Empty string should never trigger
    assert policy.should_stay_out_of_way("") is False
    assert policy.should_intervene("") is False

    engine = PlatformOptimizationEngine()
    control = engine.reconcile(get_codex_profile())
    assert control.should_stay_out_of_way("duplicate_planning") is True
    assert control.should_intervene("regression_detection") is True
    assert control.should_stay_out_of_way("") is False
    assert control.should_intervene("") is False


def test_b3_edge_cases_empty_and_whitespace_inputs():
    """
    Certifies that empty, whitespace, or invalid inputs never crash or falsely trigger matches.
    """
    policy = get_claude_code_compensation_policy()
    for empty_input in ["", "   ", "\t\n"]:
        assert policy.should_preserve(empty_input) is False
        assert policy.should_compensate(empty_input) is False
        assert policy.should_avoid(empty_input) is False
        assert policy.should_stay_out_of_way(empty_input) is False
        assert policy.should_intervene(empty_input) is False
        assert policy.permits_interruption(empty_input) is False

    assert policy.permits_interruption(None) is False

    profile = get_claude_code_profile()
    assert profile.has_capability("") is False
    assert profile.has_capability("  ") is False
    assert profile.has_strength("") is False
    assert profile.has_strength("  ") is False

    # PlatformProfile rejects empty platform_id or version
    with pytest.raises(ValueError):
        PlatformProfile(platform_id="")
    with pytest.raises(ValueError):
        PlatformProfile(platform_id="test", version="")


def test_b3_substring_qualifier_precision():
    """
    Certifies that qualified suppression rules do NOT falsely suppress generic operations:
    - 'constant_micro_checkpoints' does NOT suppress generic 'checkpoint' or 'milestone_checkpoint'.
    - 'huge_context_injection' does NOT suppress generic 'context' or 'context_injection'.
    - But 'micro_checkpoints' and 'huge_context' ARE recognized as suppressed.
    """
    engine = PlatformOptimizationEngine()
    control = engine.reconcile(get_codex_profile())

    # Generic checkpoint is NOT suppressed (Codex uses milestone checkpoints!)
    assert control.is_intervention_suppressed("checkpoint") is False
    assert control.is_intervention_suppressed("milestone_checkpoint") is False

    # Specific micro-checkpoint IS suppressed
    assert control.is_intervention_suppressed("constant_micro_checkpoints") is True
    assert control.is_intervention_suppressed("micro_checkpoints") is True
    assert control.is_intervention_suppressed("micro_checkpoint") is True

    # Generic context is NOT suppressed (Codex has a 2048 token context budget!)
    assert control.is_intervention_suppressed("context") is False
    assert control.is_intervention_suppressed("context_injection") is False

    # Huge context IS suppressed
    assert control.is_intervention_suppressed("huge_context_injection") is True
    assert control.is_intervention_suppressed("huge_context") is True


def test_b3_critical_risk_exhausted_budget_failsafe():
    """
    ATTACK VECTOR CERTIFICATION:
    When risk is CRITICAL and both latency and token headroom are 0%,
    S-Class must NOT compromise security or observation:
    - observation_mode must NOT be degraded to PASSIVE
    - escalation_policy must remain FAIL_CLOSED
    - mandatory security verifications must remain allowed
    """
    engine = PlatformOptimizationEngine()
    exhausted_budget = PerformanceBudget(
        limits=BudgetLimits(max_latency_ms=10.0, max_tokens=1000, max_interruptions=0)
    )
    # 0% headroom on latency, tokens, interruptions
    exhausted_budget.record_overhead(latency_ms=50.0, tokens=2000, interruptions=1)

    control = engine.reconcile(
        profile=get_codex_profile(),
        risk="critical",
        budget=exhausted_budget,
    )

    # Observation mode must NOT be passive under critical risk
    assert control.observation_mode != ObservationLevel.PASSIVE.value
    # Escalation must remain fail-closed
    assert control.escalation_policy == EscalationPolicy.FAIL_CLOSED.value
    # Mandatory security controls are preserved
    assert control.is_intervention_allowed("security_boundary_enforcement") is True
    assert control.is_intervention_allowed("evidence_verification") is True
    assert control.is_intervention_allowed("regression_detection") is True


def test_b3_benchmark_enforces_all_ci_and_sla_dimensions():
    """
    Certifies that all declared CI and Product SLA dimensions are strictly evaluated:
    - min_correctness_rate
    - max_token_overhead_pct
    - max_p99_latency_ms
    - max_context_overhead_pct
    """
    bench = PlatformComparisonBenchmark()
    native = PlatformMetrics(
        task_success_rate=0.90,
        correctness_score=0.90,
        regressions_count=2,
        token_count=10000,
        context_bytes=50000,
    )

    # Subcase A: Fails CI on low correctness (10%)
    sclass_low_correctness = PlatformMetrics(
        task_success_rate=0.95,
        correctness_score=0.10,  # Below CI min (85%)
        regressions_count=0,
        token_count=10500,
        context_bytes=51000,
    )
    res_a = bench.evaluate_comparison("codex", native, sclass_low_correctness)
    assert res_a.ci_passed is False
    assert any("correctness" in v for v in res_a.ci_violations)

    # Subcase B: Fails CI on excessive token overhead (500%)
    sclass_huge_tokens = PlatformMetrics(
        task_success_rate=0.95,
        correctness_score=0.95,
        regressions_count=0,
        token_count=60000,  # 500% overhead > 30% CI max
        context_bytes=51000,
    )
    res_b = bench.evaluate_comparison("codex", native, sclass_huge_tokens)
    assert res_b.ci_passed is False
    assert any("token overhead" in v for v in res_b.ci_violations)

    # Subcase C: Fails Product SLA on p99 tail latency spike (500ms > 75ms)
    sclass_p99_spike = PlatformMetrics(
        task_success_rate=0.99,
        correctness_score=0.98,
        regressions_count=0,
        token_count=10500,
        context_bytes=51000,
        latency_samples_ms=[15.0] * 98 + [500.0] * 2,  # p50=15ms, p95=15ms, p99=500ms
    )
    res_c = bench.evaluate_comparison("codex", native, sclass_p99_spike)
    assert res_c.product_sla_passed is False
    assert any("p99 latency" in v for v in res_c.product_sla_violations)

    # Subcase D: Fails Product SLA on context overhead (50% > 20%)
    sclass_ctx_overhead = PlatformMetrics(
        task_success_rate=0.99,
        correctness_score=0.98,
        regressions_count=0,
        token_count=10500,
        context_bytes=75000,  # 50% overhead > 20% Product SLA max
        latency_samples_ms=[15.0] * 10,
    )
    res_d = bench.evaluate_comparison("codex", native, sclass_ctx_overhead)
    assert res_d.product_sla_passed is False
    assert any("context overhead" in v for v in res_d.product_sla_violations)


def test_b3_benchmark_task_success_regression_rejects_thesis():
    """
    Certifies that S-Class cannot claim thesis proven if task success rate regresses,
    even if correctness was higher on the tasks that finished.
    """
    bench = PlatformComparisonBenchmark()
    native = PlatformMetrics(
        task_success_rate=0.95,
        correctness_score=0.90,
        regressions_count=2,
    )
    # S-Class improved correctness on completed tasks, but half of all tasks failed!
    sclass_dropped_success = PlatformMetrics(
        task_success_rate=0.50,  # Regressed from 95% to 50%!
        correctness_score=0.99,
        regressions_count=0,
    )
    result = bench.evaluate_comparison("codex", native, sclass_dropped_success)
    assert result.thesis_proven is False


def test_b3_budget_zero_limit_headroom_and_validation():
    """
    Certifies BudgetLimits and OverheadConsumption non-negative clamping
    and accurate headroom reporting when limits are zero.
    """
    limits = BudgetLimits(max_latency_ms=0.0, max_tokens=-50)
    assert limits.max_latency_ms == 0.0
    assert limits.max_tokens == 0

    consumption = OverheadConsumption(latency_ms=-10.0, tokens=-100)
    assert consumption.latency_ms == 0.0
    assert consumption.tokens == 0

    budget = PerformanceBudget(limits=limits, consumption=consumption)
    # Zero consumption with zero limit -> 100% headroom
    assert budget.budget_headroom_pct()["latency"] == 100.0

    # Any consumption with zero limit -> 0% headroom
    budget.record_overhead(latency_ms=1.0)
    assert budget.budget_headroom_pct()["latency"] == 0.0
