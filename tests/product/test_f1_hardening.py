"""Comprehensive validation tests for F1: PD-CH5-011 and PD-CH5-012 hardening.

Verifies:
- Evaluators accept only valid measurement / canonical outcome records.
- Absent, malformed, incomplete, and caller-asserted baseline evidence are rejected.
- Fixture-role-only input never produces SATISFIED.
- Both direct evaluator functions and public gate paths are tested.
"""
from typing import Any, Dict
import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.performance_claims import (
    QUALIFIED_EVALUATOR_BOUNDARY as PERF_BOUNDARY,
    PerformancePolicy,
    evaluate_performance_claim,
    evaluate_performance_gate,
    evaluate_pd_ch5_011_performance_measurement,
)
from sclass.product.metrics import (
    QUALIFIED_EVALUATOR_BOUNDARY as METRICS_BOUNDARY,
    evaluate_f9_metric,
    evaluate_pd_ch5_012_outcome_disclosure,
)


# =============================================================================
# 1. PD-CH5-011 Tests (Performance Measurements)
# =============================================================================

def test_pd_ch5_011_valid_evidence_accepted():
    """Valid measurement record produces SATISFIED across direct evaluator and gate path."""
    valid_payload = {
        "must_id": "PD-CH5-011",
        "corpus_digest": "sha256:corpus12345",
        "sample_count": 1000,
        "unit": "ms",
        "percentile": "p99",
        "measured_result": 24.5,
    }
    # Direct evaluator
    res1 = evaluate_pd_ch5_011_performance_measurement(valid_payload, caller_authority=PERF_BOUNDARY)
    assert res1.state == GateState.SATISFIED
    assert str(res1) == "SATISFIED"

    # Public gate path
    res2 = evaluate_performance_gate(valid_payload, caller_authority=PERF_BOUNDARY)
    assert res2.state == GateState.SATISFIED
    assert str(res2) == "SATISFIED"

    # evaluate_performance_claim
    res3 = evaluate_performance_claim(valid_payload, caller_authority=PERF_BOUNDARY)
    assert res3.state == GateState.SATISFIED


def test_pd_ch5_011_fixture_role_only_never_satisfied():
    """Passing fixture_role='happy' without valid measurement fields fails closed with MISSING."""
    fixture_only = {
        "must_id": "PD-CH5-011",
        "fixture_role": "happy",
        "expected_gate_output": "SATISFIED",
    }
    res_direct = evaluate_pd_ch5_011_performance_measurement(fixture_only, caller_authority=PERF_BOUNDARY)
    assert res_direct.state == GateState.MISSING
    assert res_direct.must_id == "PD-CH5-011"

    res_gate = evaluate_performance_gate(fixture_only, caller_authority=PERF_BOUNDARY)
    assert res_gate.state == GateState.MISSING
    assert res_gate.must_id == "PD-CH5-011"


def test_pd_ch5_011_caller_asserted_baseline_rejected():
    """Caller-asserted baseline claims are not evidence and do not produce SATISFIED."""
    claimed_baseline = {
        "must_id": "PD-CH5-011",
        "baseline": "caller-claimed-baseline-value",
        "expected_gate_output": "SATISFIED",
        "objective_status": "OPEN",
    }
    res = evaluate_pd_ch5_011_performance_measurement(claimed_baseline, caller_authority=PERF_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH5-011"


def test_pd_ch5_011_absent_and_incomplete_evidence_rejected():
    """Omission of any mandatory measurement field produces MISSING."""
    full = {
        "corpus_digest": "CORP-01",
        "sample_count": 500,
        "unit": "ms",
        "percentile": "p99",
        "measured_result": 15.0,
    }
    # Omit each field in turn
    for field in ["corpus_digest", "sample_count", "unit", "percentile", "measured_result"]:
        incomplete = dict(full)
        del incomplete[field]
        res = evaluate_pd_ch5_011_performance_measurement(incomplete, caller_authority=PERF_BOUNDARY)
        assert res.state == GateState.MISSING, f"Expected MISSING when {field} is omitted"
        assert res.must_id == "PD-CH5-011"


def test_pd_ch5_011_malformed_evidence_rejected():
    """Malformed field types (non-integer sample count, invalid unit, negative/NaN result) fail closed."""
    base = {
        "corpus_digest": "CORP-01",
        "sample_count": 500,
        "unit": "ms",
        "percentile": "p99",
        "measured_result": 15.0,
    }
    # Non-integer sample count
    res_float_samples = evaluate_pd_ch5_011_performance_measurement(dict(base, sample_count=500.5), caller_authority=PERF_BOUNDARY)
    assert res_float_samples.state == GateState.MISSING

    # Negative measured result
    res_neg_result = evaluate_pd_ch5_011_performance_measurement(dict(base, measured_result=-1.0), caller_authority=PERF_BOUNDARY)
    assert res_neg_result.state == GateState.MISSING

    # NaN measured result
    res_nan_result = evaluate_pd_ch5_011_performance_measurement(dict(base, measured_result=float("nan")), caller_authority=PERF_BOUNDARY)
    assert res_nan_result.state == GateState.MISSING

    # Sample count below policy minimum for p99 (100)
    res_low_samples = evaluate_pd_ch5_011_performance_measurement(dict(base, sample_count=50), caller_authority=PERF_BOUNDARY)
    assert res_low_samples.state == GateState.MISSING

    # Sample count exceeding policy cap (100,000)
    res_cap_overflow = evaluate_pd_ch5_011_performance_measurement(dict(base, sample_count=100_001), caller_authority=PERF_BOUNDARY)
    assert res_cap_overflow.state == GateState.MISSING


def test_pd_ch5_011_unauthorized_caller_rejected():
    """Missing or unauthorized caller authority returns MISSING without checking payload."""
    payload = {
        "corpus_digest": "CORP-01",
        "sample_count": 500,
        "unit": "ms",
        "percentile": "p99",
        "measured_result": 15.0,
    }
    # None authority
    res_none = evaluate_pd_ch5_011_performance_measurement(payload, caller_authority=None)
    assert res_none.state == GateState.MISSING

    # 'AGENT' authority
    res_agent = evaluate_pd_ch5_011_performance_measurement(payload, caller_authority="AGENT")
    assert res_agent.state == GateState.MISSING


# =============================================================================
# 2. PD-CH5-012 Tests (Outcome Metrics & Telemetry Disclosure)
# =============================================================================

def test_pd_ch5_012_valid_evidence_accepted():
    """Valid canonical outcome record produces SATISFIED across direct evaluator and gate path."""
    valid_payload = {
        "must_id": "PD-CH5-012",
        "denominator": 2500,
        "observation_window": "7d",
        "unknown_telemetry_disclosure": "UNAVAILABLE",
    }
    # Direct evaluator
    res1 = evaluate_pd_ch5_012_outcome_disclosure(valid_payload, caller_authority=METRICS_BOUNDARY)
    assert res1.state == GateState.SATISFIED
    assert str(res1) == "SATISFIED"

    # Public gate path (evaluate_f9_metric)
    res2 = evaluate_f9_metric(valid_payload, caller_authority=METRICS_BOUNDARY)
    assert res2.state == GateState.SATISFIED
    assert str(res2) == "SATISFIED"


def test_pd_ch5_012_fixture_role_only_never_satisfied():
    """Passing fixture_role='happy' without denominator/window fails closed to MISSING."""
    fixture_only = {
        "must_id": "PD-CH5-012",
        "fixture_role": "happy",
        "expected_gate_output": "SATISFIED",
    }
    res_direct = evaluate_pd_ch5_012_outcome_disclosure(fixture_only, caller_authority=METRICS_BOUNDARY)
    assert res_direct.state == GateState.MISSING
    assert res_direct.must_id == "PD-CH5-012"

    res_gate = evaluate_f9_metric(fixture_only, caller_authority=METRICS_BOUNDARY)
    assert res_gate.state == GateState.MISSING
    assert res_gate.must_id == "PD-CH5-012"


def test_pd_ch5_012_caller_asserted_baseline_rejected():
    """Caller-supplied baseline claim without valid fields is rejected."""
    claimed_baseline = {
        "must_id": "PD-CH5-012",
        "baseline": {"some_claim": True},
        "expected_gate_output": "SATISFIED",
    }
    res = evaluate_pd_ch5_012_outcome_disclosure(claimed_baseline, caller_authority=METRICS_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH5-012"


def test_pd_ch5_012_absent_and_incomplete_evidence_rejected():
    """Omission of denominator, observation_window, or unknown telemetry disclosure returns MISSING."""
    full = {
        "denominator": 100,
        "observation_window": {"start": "T1", "end": "T2"},
        "unknown_telemetry_disclosure": "UNAVAILABLE",
    }
    # Omit denominator
    no_denom = dict(full)
    del no_denom["denominator"]
    res = evaluate_pd_ch5_012_outcome_disclosure(no_denom, caller_authority=METRICS_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH5-012"

    # Omit observation_window
    no_win = dict(full)
    del no_win["observation_window"]
    res2 = evaluate_pd_ch5_012_outcome_disclosure(no_win, caller_authority=METRICS_BOUNDARY)
    assert res2.state == GateState.MISSING
    assert res2.must_id == "PD-CH5-012"

    # Omit unknown telemetry disclosure
    no_telem = dict(full)
    del no_telem["unknown_telemetry_disclosure"]
    res3 = evaluate_pd_ch5_012_outcome_disclosure(no_telem, caller_authority=METRICS_BOUNDARY)
    assert res3.state == GateState.MISSING
    assert res3.must_id == "PD-CH5-012"


def test_pd_ch5_012_malformed_and_manipulated_inputs_rejected():
    """Denominator <= 0, manipulated observation window, or estimate telemetry returns MISSING."""
    base = {
        "denominator": 100,
        "observation_window": "24h",
        "unknown_telemetry_disclosure": "UNAVAILABLE",
    }
    # Zero denominator
    assert evaluate_pd_ch5_012_outcome_disclosure(dict(base, denominator=0), caller_authority=METRICS_BOUNDARY).state == GateState.MISSING

    # Negative denominator
    assert evaluate_pd_ch5_012_outcome_disclosure(dict(base, denominator=-5), caller_authority=METRICS_BOUNDARY).state == GateState.MISSING

    # Boolean denominator
    assert evaluate_pd_ch5_012_outcome_disclosure(dict(base, denominator=True), caller_authority=METRICS_BOUNDARY).state == GateState.MISSING

    # Manipulated observation window
    assert evaluate_pd_ch5_012_outcome_disclosure(dict(base, observation_window="shortened"), caller_authority=METRICS_BOUNDARY).state == GateState.MISSING
    assert evaluate_pd_ch5_012_outcome_disclosure(dict(base, observation_window="invalid"), caller_authority=METRICS_BOUNDARY).state == GateState.MISSING

    # Estimated telemetry instead of UNAVAILABLE
    assert evaluate_pd_ch5_012_outcome_disclosure(dict(base, unknown_telemetry_disclosure="estimate"), caller_authority=METRICS_BOUNDARY).state == GateState.MISSING
    assert evaluate_pd_ch5_012_outcome_disclosure(dict(base, unknown_telemetry_disclosure=0), caller_authority=METRICS_BOUNDARY).state == GateState.MISSING


def test_pd_ch5_012_unauthorized_caller_rejected():
    """Missing or unauthorized caller authority returns MISSING."""
    payload = {
        "denominator": 100,
        "observation_window": "24h",
        "unknown_telemetry_disclosure": "UNAVAILABLE",
    }
    assert evaluate_pd_ch5_012_outcome_disclosure(payload, caller_authority=None).state == GateState.MISSING
    assert evaluate_pd_ch5_012_outcome_disclosure(payload, caller_authority="AGENT").state == GateState.MISSING
