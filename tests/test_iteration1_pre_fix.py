"""Vulnerability regression test suite (F1, F2, F8).

Demonstrates that pre-fix base (cda0b792) fails these integrity tests,
and that the post-fix implementation passes them.
"""
from pathlib import Path
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.performance_claims import (
    QUALIFIED_EVALUATOR_BOUNDARY as PERF_BOUNDARY,
    evaluate_performance_claim,
)
from sclass.product.metrics import (
    QUALIFIED_EVALUATOR_BOUNDARY as METRICS_BOUNDARY,
    evaluate_f9_metric,
)
from sclass.product.replay import (
    QUALIFIED_EVALUATOR_BOUNDARY as REPLAY_BOUNDARY,
    evaluate_ch2_065_lifecycle_proof,
)
from sclass.verification.adapters.locust_adapter import LocustAdapter
from sclass.verification.adapters.schemathesis_adapter import SchemathesisAdapter
from sclass.verification.adapters.playwright_adapter import PlaywrightAdapter
from sclass.verification.adapters.testcontainers_adapter import TestcontainersAdapter
from sclass.verification.adapters.cosmic_ray_adapter import CosmicRayAdapter


# =============================================================================
# 1. F1: Performance Claims (PD-CH5-011) - Shortcut Rejection
# =============================================================================

def test_f1_ch5_011_fixture_role_only_rejected():
    """Empty payload with fixture_role='happy' must NOT be granted SATISFIED without measurement records.
    Pre-fix base FAILS (returns SATISFIED); post-fix PASSES (returns MISSING)."""
    empty_happy = {
        "must_id": "PD-CH5-011",
        "fixture_role": "happy",
    }
    res = evaluate_performance_claim(empty_happy, caller_authority=PERF_BOUNDARY)
    assert res.state != GateState.SATISFIED, "Vulnerability: fixture_role='happy' alone produced SATISFIED"
    assert res.state == GateState.MISSING


def test_f1_ch5_011_caller_asserted_baseline_rejected():
    """Caller-asserted baseline claims must NOT be accepted as evidence.
    Pre-fix base FAILS (returns SATISFIED); post-fix PASSES (returns MISSING)."""
    baseline_payload = {
        "must_id": "PD-CH5-011",
        "baseline": "caller-claimed-baseline",
        "expected_gate_output": "SATISFIED",
    }
    res = evaluate_performance_claim(baseline_payload, caller_authority=PERF_BOUNDARY)
    assert res.state != GateState.SATISFIED, "Vulnerability: caller-asserted baseline produced SATISFIED"
    assert res.state == GateState.MISSING


# =============================================================================
# 2. F1: Outcome Metrics (PD-CH5-012) - Shortcut Rejection
# =============================================================================

def test_f1_ch5_012_fixture_role_only_rejected():
    """Empty payload with fixture_role='happy' must NOT be granted SATISFIED without denominator & disclosure.
    Pre-fix base FAILS (returns SATISFIED); post-fix PASSES (returns MISSING)."""
    empty_happy = {
        "must_id": "PD-CH5-012",
        "fixture_role": "happy",
    }
    res = evaluate_f9_metric(empty_happy, caller_authority=METRICS_BOUNDARY)
    assert res.state != GateState.SATISFIED, "Vulnerability: fixture_role='happy' alone produced SATISFIED"
    assert res.state == GateState.MISSING


# =============================================================================
# 3. F2: Lifecycle Proof (PD-CH2-065) - Untrusted Claim Rejection
# =============================================================================

def test_f2_ch2_065_unverified_record_ref_rejected():
    """Arbitrary caller-supplied evaluator_record_ref without canonical verification must NOT produce SATISFIED.
    Pre-fix base FAILS (returns SATISFIED); post-fix PASSES (returns MISSING)."""
    unverified_claim = {
        "must_id": "PD-CH2-065",
        "example_preconditions": {"env": "prod"},
        "bound_input_digests": ["DIGEST-01"],
        "expected_gate_output": "SATISFIED",
        "evaluator_record_ref": "UNVERIFIED-CALLER-STRING",
    }
    res = evaluate_ch2_065_lifecycle_proof(unverified_claim, caller_authority=REPLAY_BOUNDARY)
    assert res.state != GateState.SATISFIED, "Vulnerability: unverified record ref produced SATISFIED"
    assert res.state == GateState.MISSING


# =============================================================================
# 4. F8: Adapters - Tool Absent Must Never Produce passed=True
# =============================================================================

@pytest.mark.parametrize("verifier_cls,name", [
    (LocustAdapter, "locust"),
    (SchemathesisAdapter, "schemathesis"),
    (PlaywrightAdapter, "playwright"),
    (TestcontainersAdapter, "testcontainers"),
    (CosmicRayAdapter, "cosmic_ray"),
])
def test_f8_tool_absent_must_not_produce_passed_true(verifier_cls, name, tmp_path):
    """When external tool is absent (FileNotFoundError), adapter must NEVER return passed=True.
    Pre-fix base FAILS (returned passed=True); post-fix PASSES (returns passed=False, 127, UNAVAILABLE)."""
    v = verifier_cls()
    with patch("subprocess.run", side_effect=FileNotFoundError(f"No such file or directory: '{name}'")):
        rec = v.run(tmp_path)
        assert rec.passed is False, f"Vulnerability: {name} adapter returned passed=True when tool absent"
        assert rec.returncode == 127
        assert b"UNAVAILABLE" in rec.stderr
