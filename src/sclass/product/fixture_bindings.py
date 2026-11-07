"""Deterministic fixture bindings mapping Master Design document fixtures to evaluator calls.

Every binding records:
- fixture_id
- must_id
- master_line: exact line number in hash-verified master document
- category: "SINGLE" or "PAIR"
- role: "gaming", "happy", or "single"
- expected_output: copied verbatim from master document
- evaluator_dispatch: callable invoking qualified product evaluator, or None if pending
- not_run_reason: from closed list (NO_PUBLIC_EVALUATOR, MASTER_TEXT_NOT_DETERMINISTIC, BLOCK1_OUT_OF_SCOPE)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY: str = "QUALIFIED_EVALUATOR"

# Closed set of valid NOT_RUN reasons per CL specification
VALID_NOT_RUN_REASONS = {
    "NO_PUBLIC_EVALUATOR",
    "MASTER_TEXT_NOT_DETERMINISTIC",
    "BLOCK1_OUT_OF_SCOPE",
}


@dataclass(frozen=True)
class FixtureBinding:
    fixture_id: str
    must_id: str
    master_line: int
    category: str  # "SINGLE" or "PAIR"
    role: str  # "gaming", "happy", or "single"
    expected_output: str
    dispatch_name: str
    not_run_reason: Optional[str] = None


# -----------------------------------------------------------------------------
# BLOCK 2 AUTHORITATIVE 29 VECTORS (17 SINGLE + 6 PAIRS / 12 VECTORS)
# -----------------------------------------------------------------------------

BLOCK2_17_SINGLE_BINDINGS: List[FixtureBinding] = [
    # F5 Gate Evaluator (PD-F5-001..005)
    FixtureBinding("F5-T1", "PD-F5-001", 9510, "SINGLE", "single", "SATISFIED", "eval_f5_t1"),
    FixtureBinding("F5-T2", "PD-F5-002", 9524, "SINGLE", "single", "MISSING[PD-F5-002]", "eval_f5_t2"),
    FixtureBinding("F5-T3", "PD-F5-003", 9538, "SINGLE", "single", "MISSING[PD-F5-003]", "eval_f5_t3"),
    FixtureBinding("F5-T4", "PD-F5-004", 9547, "SINGLE", "single", "SATISFIED", "eval_f5_t4"),
    FixtureBinding("F5-T5a", "PD-F5-005", 9561, "SINGLE", "single", "DENIED", "eval_f5_t5a"),
    FixtureBinding("F5-T5b", "PD-F5-005", 9568, "SINGLE", "single", "MISSING[PD-F5-005]", "eval_f5_t5b"),
    FixtureBinding("F5-T5c", "PD-F5-005", 9575, "SINGLE", "single", "BLOCKED_ON_HUMAN[PD-F5-005]", "eval_f5_t5c"),
    FixtureBinding("F5-T6", "PD-F5-001", 9585, "SINGLE", "single", "SATISFIED", "eval_f5_t6"),
    FixtureBinding("F5-T7", "PD-F5-001", 9600, "SINGLE", "single", "MISSING[PD-F5-001]", "eval_f5_t7"),
    # F9 Outcome Metrics (PD-F9-001..004)
    FixtureBinding("F9-T1", "PD-F9-001", 9812, "SINGLE", "single", "SATISFIED", "eval_f9_t1"),
    FixtureBinding("F9-T2", "PD-F9-002", 9820, "SINGLE", "single", "MISSING[PD-F9-002]", "eval_f9_t2"),
    FixtureBinding("F9-T3", "PD-F9-003", 9828, "SINGLE", "single", "SATISFIED", "eval_f9_t3"),
    FixtureBinding("F9-T4", "PD-F9-004", 9838, "SINGLE", "single", "SATISFIED", "eval_f9_t4"),
    # Chapter 5 Single Rows (PD-CH5-003..006)
    FixtureBinding("CH5-T3", "PD-CH5-003", 10550, "SINGLE", "single", "MISSING[PD-CH5-003]", "eval_ch5_t3"),
    FixtureBinding("CH5-T4", "PD-CH5-004", 10558, "SINGLE", "single", "MISSING[PD-CH5-004]", "eval_ch5_t4"),
    FixtureBinding("CH5-T5", "PD-CH5-005", 10566, "SINGLE", "single", "NOT_APPLICABLE", "eval_ch5_t5"),
    FixtureBinding("CH5-T6", "PD-CH5-006", 10573, "SINGLE", "single", "MISSING[PD-CH5-006]", "eval_ch5_t6"),
]

BLOCK2_6_PAIRS_BINDINGS: List[FixtureBinding] = [
    # PD-CH5-007
    FixtureBinding("CH5-T7", "PD-CH5-007", 11560, "PAIR", "gaming", "MISSING[PD-CH5-007]", "eval_ch5_t7"),
    FixtureBinding("CH5-T8", "PD-CH5-007", 11588, "PAIR", "happy", "SATISFIED", "eval_ch5_t8"),
    # PD-CH5-008
    FixtureBinding("CH5-T9", "PD-CH5-008", 11600, "PAIR", "gaming", "MISSING[PD-CH5-008]", "eval_ch5_t9"),
    FixtureBinding("CH5-T10", "PD-CH5-008", 11629, "PAIR", "happy", "SATISFIED", "eval_ch5_t10"),
    # PD-CH5-009
    FixtureBinding("CH5-T11", "PD-CH5-009", 11641, "PAIR", "gaming", "MISSING[PD-CH5-009]", "eval_ch5_t11"),
    FixtureBinding("CH5-T12", "PD-CH5-009", 11670, "PAIR", "happy", "SATISFIED", "eval_ch5_t12"),
    # PD-CH5-010
    FixtureBinding("CH5-T13", "PD-CH5-010", 11682, "PAIR", "gaming", "MISSING[PD-CH5-010]", "eval_ch5_t13"),
    FixtureBinding("CH5-T14", "PD-CH5-010", 11710, "PAIR", "happy", "SATISFIED", "eval_ch5_t14"),
    # PD-CH5-011
    FixtureBinding("CH5-T15", "PD-CH5-011", 11722, "PAIR", "gaming", "MISSING[PD-CH5-011]", "eval_ch5_t15"),
    FixtureBinding("CH5-T16", "PD-CH5-011", 11750, "PAIR", "happy", "SATISFIED", "eval_ch5_t16"),
    # PD-CH5-012
    FixtureBinding("CH5-T17", "PD-CH5-012", 11762, "PAIR", "gaming", "MISSING[PD-CH5-012]", "eval_ch5_t17"),
    FixtureBinding("CH5-T18", "PD-CH5-012", 11790, "PAIR", "happy", "SATISFIED", "eval_ch5_t18"),
]


def execute_binding(binding: FixtureBinding) -> Any:
    """Invokes the qualified evaluator for a given fixture binding."""
    # F5 Evaluator dispatch
    if binding.fixture_id.startswith("F5-"):
        from sclass.product.gate_evaluator import (
            QUALIFIED_EVALUATOR_BOUNDARY as F5_BOUNDARY,
            evaluate_f5_gate,
        )
        if binding.fixture_id == "F5-T1":
            res = evaluate_f5_gate(
                phase="P2",
                canonical_state_binding={"id": "SB-1"},
                pinned_guidance={"id": "G-1"},
                policy_version="P-7",
                evaluator_version="EV-3",
                evaluation_instant="2026-11-07T00:00:00Z",
                kernel_execution_gate="ALLOWED",
                caller_authority=F5_BOUNDARY,
            )
            return res.combined
        elif binding.fixture_id == "F5-T2":
            res = evaluate_f5_gate(
                phase="P2",
                canonical_state_binding={"id": "SB-1"},
                pinned_guidance={"id": "G-1"},
                policy_version="P-7",
                evaluator_version="EV-3",
                evaluation_instant="2026-11-07T00:00:00Z",
                kernel_execution_gate="ALLOWED",
                checks=[
                    {"check_id": "C-02", "status": "MISSING", "must_id": "PD-F5-002", "inputs_digest": "D2"},
                    {"check_id": "C-01", "status": "MISSING", "must_id": "PD-F5-002", "inputs_digest": "D1"},
                    {"check_id": "C-09", "status": "BLOCKED_ON_HUMAN", "must_id": "PD-F5-002", "inputs_digest": "D3"},
                ],
                caller_authority=F5_BOUNDARY,
            )
            return res.combined
        elif binding.fixture_id == "F5-T3":
            res = evaluate_f5_gate(
                phase="P2",
                canonical_state_binding={"id": "SB-1"},
                pinned_guidance={"id": "G-1"},
                policy_version="P-7",
                evaluator_version="v6",
                pinned_evaluator_version="v7",
                evaluation_instant="2026-11-07T00:00:00Z",
                kernel_execution_gate="ALLOWED",
                caller_authority=F5_BOUNDARY,
            )
            return res.combined
        elif binding.fixture_id == "F5-T4":
            res = evaluate_f5_gate(
                phase="P7",
                canonical_state_binding={"id": "SB-2"},
                pinned_guidance={"id": "G-4"},
                policy_version="P-7",
                evaluator_version="EV-3",
                evaluation_instant="2026-11-07T00:00:00Z",
                kernel_execution_gate="ALLOWED",
                caller_authority=F5_BOUNDARY,
            )
            return res.combined
        elif binding.fixture_id == "F5-T5a":
            res = evaluate_f5_gate(
                phase="P7",
                canonical_state_binding={"id": "SB-2"},
                pinned_guidance={"id": "G-4"},
                policy_version="P-7",
                evaluator_version="EV-3",
                evaluation_instant="2026-11-07T00:00:00Z",
                kernel_execution_gate="DENIED",
                caller_authority=F5_BOUNDARY,
            )
            return res.combined
        elif binding.fixture_id == "F5-T5b":
            res = evaluate_f5_gate(
                phase="P7",
                canonical_state_binding={"id": "SB-2"},
                pinned_guidance={"id": "G-4"},
                policy_version="P-7",
                evaluator_version="EV-3",
                evaluation_instant="2026-11-07T00:00:00Z",
                kernel_execution_gate="ALLOWED",
                checks=[{"check_id": "CHK_FAIL", "status": "MISSING", "must_id": "PD-F5-005"}],
                caller_authority=F5_BOUNDARY,
            )
            return res.combined
        elif binding.fixture_id == "F5-T5c":
            res = evaluate_f5_gate(
                phase="P7",
                canonical_state_binding={"id": "SB-2"},
                pinned_guidance={"id": "G-4"},
                policy_version="P-7",
                evaluator_version="EV-3",
                evaluation_instant="2026-11-07T00:00:00Z",
                kernel_execution_gate="ALLOWED",
                checks=[{"check_id": "CHK_BLOCK", "status": "BLOCKED_ON_HUMAN", "must_id": "PD-F5-005"}],
                skill_added_checks=[{"check_id": "SKILL_1", "status": "SATISFIED", "must_id": "PD-F5-005"}],
                caller_authority=F5_BOUNDARY,
            )
            return res.combined
        elif binding.fixture_id == "F5-T6":
            res = evaluate_f5_gate(
                phase="P7",
                canonical_state_binding={"id": "SB-2"},
                pinned_guidance={"id": "G-4"},
                policy_version="P-7",
                evaluator_version="EV-3",
                evaluation_instant="2026-01-01T00:00:00Z",
                kernel_execution_gate="ALLOWED",
                caller_authority=F5_BOUNDARY,
            )
            return res.combined
        elif binding.fixture_id == "F5-T7":
            res = evaluate_f5_gate(
                phase="P7",
                canonical_state_binding={"id": "SB-2"},
                pinned_guidance={"id": "G-4"},
                policy_version="P-7",
                evaluator_version="EV-3",
                evaluation_instant="",
                kernel_execution_gate="ALLOWED",
                caller_authority=F5_BOUNDARY,
            )
            return res.combined

    # F9 Metrics dispatch
    if binding.fixture_id.startswith("F9-"):
        try:
            from sclass.product.metrics import (
                QUALIFIED_EVALUATOR_BOUNDARY as METRICS_BOUNDARY,
                evaluate_f9_metric_definition,
                evaluate_f9_outcome_metrics,
            )
            if binding.fixture_id == "F9-T1":
                return evaluate_f9_outcome_metrics(
                    events=["WORK_ASSIGNED", "VERIFICATION_COMPLETED", "EVIDENCE_ACCEPTED", "OBLIGATION_SATISFIED"],
                    caller_authority=METRICS_BOUNDARY,
                )
            elif binding.fixture_id == "F9-T2":
                return evaluate_f9_metric_definition(
                    metric_name="false_completion_rate",
                    numerator="invalidated_after_satisfaction",
                    denominator=None,
                    caller_authority=METRICS_BOUNDARY,
                )
            elif binding.fixture_id == "F9-T3":
                return evaluate_f9_outcome_metrics(
                    paired_eval=True,
                    false_completion_rate_old=0.10,
                    false_completion_rate_new=0.05,
                    false_block_rate_old=0.08,
                    false_block_rate_new=0.20,
                    caller_authority=METRICS_BOUNDARY,
                )
            elif binding.fixture_id == "F9-T4":
                return evaluate_f9_outcome_metrics(
                    events=["WORK_ASSIGNED", "VERIFICATION_COMPLETED", "EVIDENCE_ACCEPTED", "OBLIGATION_SATISFIED"],
                    agent_reported={"cost": 1, "time_seconds": 2},
                    canonical_events_cost=10,
                    canonical_events_time=20,
                    caller_authority=METRICS_BOUNDARY,
                )
        except ImportError:
            raise NotImplementedError("Metrics module pending upstream staging merge")

    # Chapter 5 Gate Cache dispatch
    if binding.fixture_id in ("CH5-T3", "CH5-T7", "CH5-T8", "CH5-T9", "CH5-T10", "CH5-T11", "CH5-T12", "CH5-T13", "CH5-T14"):
        from sclass.product.gate_cache import (
            QUALIFIED_EVALUATOR_BOUNDARY as CACHE_BOUNDARY,
            GateCache,
        )
        cache = GateCache()
        if binding.fixture_id == "CH5-T3":
            full_tuple = {
                "phase": "P2",
                "canonical_state_binding": "SB1",
                "pinned_guidance": "G1",
                "policy_version": "V1",
                "evaluator_version": "E1",
                "evaluation_instant": "2026-11-07T00:00:00Z",
            }
            return cache.evaluate_cache_lookup(
                cache_key="C_MISS",
                evaluation_tuple=full_tuple,
                cached_guidance_digest="G1",
                current_guidance_digest="G2",
                caller_authority=CACHE_BOUNDARY,
            )
        elif binding.fixture_id == "CH5-T7":
            return cache.evaluate_cache_lookup(
                cache_key="C_INCOMPLETE",
                evaluation_tuple={"phase": "P2"},  # Missing required elements
                caller_authority=CACHE_BOUNDARY,
            )
        elif binding.fixture_id == "CH5-T8":
            full_tuple = {
                "phase": "P2",
                "canonical_state_binding": {"policy_version": "V1"},
                "pinned_guidance": "G1",
                "policy_version": "V1",
                "evaluator_version": "E1",
                "evaluation_instant": "2026-11-07T00:00:00Z",
            }
            cache.put(
                cache_key="C_VALID",
                gate_output=GateOutput(GateState.SATISFIED),
                replay_record=full_tuple,
                caller_authority=CACHE_BOUNDARY,
            )
            return cache.evaluate_cache_lookup(
                cache_key="C_VALID",
                evaluation_tuple=full_tuple,
                cached_guidance_digest="G1",
                current_guidance_digest="G1",
                caller_authority=CACHE_BOUNDARY,
            )
        elif binding.fixture_id == "CH5-T9":
            return cache.evaluate_blocker_invalidation(
                binding_digest="B1",
                blocker_ids=["BLOCKER-1"],
                additive_evidence_digest="ADD_EV_1",
                authoritative_invalidation=False,
                caller_authority=CACHE_BOUNDARY,
            )
        elif binding.fixture_id == "CH5-T10":
            return cache.evaluate_blocker_invalidation(
                binding_digest="B1",
                blocker_ids=[],
                additive_evidence_digest="ADD_EV_1",
                authoritative_invalidation=True,
                caller_authority=CACHE_BOUNDARY,
            )
        elif binding.fixture_id == "CH5-T11":
            return cache.evaluate_key_digests_and_dependency(
                declared_key_digests=["KEY_1", "KEY_2"],
                lookup_digests=["KEY_1"],  # Missing KEY_2
                dependency_index_completeness="complete",
                cached_result_digest="RES_1",
                evaluator_record_ref="EV_REC_1",
                caller_authority=CACHE_BOUNDARY,
            )
        elif binding.fixture_id == "CH5-T12":
            return cache.evaluate_key_digests_and_dependency(
                declared_key_digests=["KEY_1"],
                lookup_digests=["KEY_1"],
                dependency_index_completeness="complete",
                cached_result_digest="RES_1",
                evaluator_record_ref="EV_REC_1",
                caller_authority=CACHE_BOUNDARY,
            )
        elif binding.fixture_id == "CH5-T13":
            return cache.evaluate_adapter_outcome(
                test_run_status="TIMEOUT",
                caller_authority=CACHE_BOUNDARY,
            )
        elif binding.fixture_id == "CH5-T14":
            return cache.evaluate_adapter_outcome(
                test_run_status="PASSED",
                adapter_result_digest="ADAPTER_RES_1",
                flaky_disagreement=False,
                caller_authority=CACHE_BOUNDARY,
            )

    # Performance claims (CH5-T4, CH5-T15, CH5-T16)
    if binding.fixture_id in ("CH5-T4", "CH5-T15", "CH5-T16"):
        try:
            from sclass.product.performance_claims import (
                QUALIFIED_EVALUATOR_BOUNDARY as PERF_BOUNDARY,
                evaluate_performance_claim,
            )
            if binding.fixture_id == "CH5-T4":
                return evaluate_performance_claim(
                    claim_text="p95 under 100 ms",
                    corpus_measured=False,
                    caller_authority=PERF_BOUNDARY,
                )
            elif binding.fixture_id == "CH5-T15":
                return evaluate_performance_claim(
                    claim_text="p99 under 50 ms",
                    sample_count=50,
                    corpus_measured=True,
                    caller_authority=PERF_BOUNDARY,
                )
            elif binding.fixture_id == "CH5-T16":
                return evaluate_performance_claim(
                    claim_text="p99 under 50 ms",
                    sample_count=100,
                    corpus_measured=True,
                    unit="ms",
                    percentile=99,
                    caller_authority=PERF_BOUNDARY,
                )
        except ImportError:
            raise NotImplementedError("Performance claims module pending upstream staging merge")

    # Check registry (CH5-T6)
    if binding.fixture_id == "CH5-T6":
        from sclass.product.check_registry import (
            QUALIFIED_EVALUATOR_BOUNDARY as REG_BOUNDARY,
            validate_check_id,
        )
        return validate_check_id(
            "PRODUCT-UNREGISTERED-CHECK",
            caller_authority=REG_BOUNDARY,
        )

    # Outcome metrics (CH5-T5, CH5-T17, CH5-T18)
    if binding.fixture_id in ("CH5-T5", "CH5-T17", "CH5-T18"):
        try:
            from sclass.product.metrics import (
                QUALIFIED_EVALUATOR_BOUNDARY as METRICS_BOUNDARY,
                evaluate_ch5_outcome_metric,
            )
            if binding.fixture_id == "CH5-T5":
                return evaluate_ch5_outcome_metric(
                    numerator=0,
                    denominator=0,
                    caller_authority=METRICS_BOUNDARY,
                )
            elif binding.fixture_id == "CH5-T17":
                return evaluate_ch5_outcome_metric(
                    denominator_declared=False,
                    caller_authority=METRICS_BOUNDARY,
                )
            elif binding.fixture_id == "CH5-T18":
                return evaluate_ch5_outcome_metric(
                    denominator_declared=True,
                    numerator=5,
                    denominator=10,
                    caller_authority=METRICS_BOUNDARY,
                )
        except ImportError:
            raise NotImplementedError("Metrics module pending upstream staging merge")

    raise NotImplementedError(f"No binding implementation for {binding.fixture_id}")
