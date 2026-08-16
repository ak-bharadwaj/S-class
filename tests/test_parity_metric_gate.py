"""
Unit tests for ParityMetricGate single-source-of-truth declarative gating architecture.
Verifies upper-bound pass/fail, lower-bound pass/fail, exact-boundary conditions,
operational escalation margins, mandatory required gate enforcement, fail-closed empty behavior,
input validation (__post_init__), and verify_parity_certificate single-source verification.
"""

import math
import pytest
from benchmark.parity.file_lock_harness import (
    ParityMetricGate,
    GateDirection,
    STANDARD_LATENCY_MEDIAN_GATE,
    STANDARD_LATENCY_P95_GATE,
    STANDARD_THROUGHPUT_GATE,
    REQUIRED_CERTIFICATION_GATES,
    CERT_KEY_LAYER_A,
    CERT_KEY_LAYER_A_SP,
    CERT_KEY_LAYER_C,
    CERT_KEY_SOAK,
    CERT_KEY_INTEROP,
    CERT_KEY_DIFFERENTIAL,
    verify_parity_certificate,
    compute_paired_bootstrap_metrics
)


def test_parity_metric_gate_upper_bound_passing():
    gate = ParityMetricGate(
        name="latency_test",
        direction=GateDirection.UPPER_BOUND,
        threshold=1.005,
        escalation_margin=0.020
    )
    # Just inside threshold
    assert gate.is_passing(1.0049) is True
    # Exactly on threshold
    assert gate.is_passing(1.0050) is True
    # Just outside threshold
    assert gate.is_passing(1.0051) is False
    assert gate.is_passing(1.0100) is False


def test_parity_metric_gate_lower_bound_passing():
    gate = ParityMetricGate(
        name="throughput_test",
        direction=GateDirection.LOWER_BOUND,
        threshold=0.995,
        escalation_margin=0.020
    )
    # Just inside threshold
    assert gate.is_passing(0.9951) is True
    # Exactly on threshold
    assert gate.is_passing(0.9950) is True
    # Just outside threshold
    assert gate.is_passing(0.9949) is False
    assert gate.is_passing(0.9800) is False


def test_parity_metric_gate_escalation_boundary():
    upper_gate = ParityMetricGate(
        name="latency_test",
        direction=GateDirection.UPPER_BOUND,
        threshold=1.005,
        escalation_margin=0.020
    )
    # Far below boundary (0.850 < 0.985) -> No escalation
    assert upper_gate.is_near_boundary(0.850) is False
    # Just outside escalation margin (0.985 - 0.0001 = 0.9849) -> No escalation
    assert upper_gate.is_near_boundary(0.9849) is False
    # Exactly at escalation margin (1.005 - 0.020 = 0.985) -> Escalation triggered
    assert upper_gate.is_near_boundary(0.9850) is True
    # Inside escalation margin (0.995 > 0.985) -> Escalation triggered
    assert upper_gate.is_near_boundary(0.9950) is True
    # Exactly at threshold (1.005) -> Escalation triggered
    assert upper_gate.is_near_boundary(1.0050) is True
    # Beyond threshold (1.010 > 0.985) -> Escalation triggered
    assert upper_gate.is_near_boundary(1.0100) is True

    lower_gate = ParityMetricGate(
        name="throughput_test",
        direction=GateDirection.LOWER_BOUND,
        threshold=0.995,
        escalation_margin=0.020
    )
    # Far above boundary (1.200 > 1.015) -> No escalation
    assert lower_gate.is_near_boundary(1.200) is False
    # Just outside escalation margin (1.015 + 0.0001 = 1.0151) -> No escalation
    assert lower_gate.is_near_boundary(1.0151) is False
    # Exactly at escalation margin (0.995 + 0.020 = 1.015) -> Escalation triggered
    assert lower_gate.is_near_boundary(1.0150) is True
    # Inside escalation margin (1.000 < 1.015) -> Escalation triggered
    assert lower_gate.is_near_boundary(1.0000) is True
    # Exactly at threshold (0.995) -> Escalation triggered
    assert lower_gate.is_near_boundary(0.9950) is True
    # Below threshold (0.980 < 1.015) -> Escalation triggered
    assert lower_gate.is_near_boundary(0.9800) is True


def test_standard_required_gates_immutability():
    assert len(REQUIRED_CERTIFICATION_GATES) == 3
    assert REQUIRED_CERTIFICATION_GATES[0] == STANDARD_LATENCY_MEDIAN_GATE
    assert REQUIRED_CERTIFICATION_GATES[1] == STANDARD_LATENCY_P95_GATE
    assert REQUIRED_CERTIFICATION_GATES[2] == STANDARD_THROUGHPUT_GATE
    assert STANDARD_LATENCY_MEDIAN_GATE.threshold == 1.005
    assert STANDARD_LATENCY_P95_GATE.threshold == 1.005
    assert STANDARD_THROUGHPUT_GATE.threshold == 0.995


def test_optional_diagnostic_gate_cannot_suppress_required_gates():
    paired_data = [(100.0, 100.0) for _ in range(50)]
    metrics = compute_paired_bootstrap_metrics(paired_data)
    assert metrics["median_gate_passed"] is True
    assert metrics["p95_gate_passed"] is True
    assert metrics["throughput_gate_passed"] is True
    assert metrics["all_gates_passed"] is True


def test_empty_observations_fail_closed():
    empty_metrics = compute_paired_bootstrap_metrics([])
    assert empty_metrics["median_gate_passed"] is False
    assert empty_metrics["p95_gate_passed"] is False
    assert empty_metrics["throughput_gate_passed"] is False
    assert empty_metrics["all_gates_passed"] is False


def test_parity_metric_gate_post_init_validation():
    # Boolean threshold -> ValueError
    with pytest.raises(ValueError, match="non-boolean numeric type"):
        ParityMetricGate("bad_bool", GateDirection.UPPER_BOUND, True)

    # NaN threshold -> ValueError
    with pytest.raises(ValueError, match="finite number"):
        ParityMetricGate("bad_nan", GateDirection.UPPER_BOUND, float("nan"))

    # Inf threshold -> ValueError
    with pytest.raises(ValueError, match="finite number"):
        ParityMetricGate("bad_inf", GateDirection.UPPER_BOUND, float("inf"))

    # Non-numeric -> ValueError
    with pytest.raises(ValueError, match="non-boolean numeric type"):
        ParityMetricGate("bad_str", GateDirection.UPPER_BOUND, "1.005")


def _make_valid_sample_certificate():
    return {
        "certificate_id": "OSS-PARITY-GATE-1-FILELOCK-POSIX",
        "platform_scope": "POSIX / Python 3.12",
        "timestamp_utc": 1000.0,
        "final_verdict": "PASS",
        "provenance": {
            "os_platform": "linux",
            "tested_source_sha": "test_sha_12345",
            "git_commit_sha": "test_sha_12345"
        },
        "acceptance_criteria": {
            "soak_cycles_executed": 5000
        },
        CERT_KEY_LAYER_A: {
            "median_ratio_95_ci": [0.4, 0.5],
            "p95_ratio_95_ci": [0.4, 0.5],
            "throughput_ratio_95_ci": [2.0, 2.5],
            "verdict": "PASS"
        },
        CERT_KEY_LAYER_A_SP: {
            "median_ratio_95_ci": [0.4, 0.5],
            "p95_ratio_95_ci": [0.4, 0.5],
            "throughput_ratio_95_ci": [2.0, 2.5],
            "verdict": "PASS"
        },
        CERT_KEY_LAYER_C: {
            "median_ratio_95_ci": [0.7, 0.8],
            "p95_ratio_95_ci": [0.6, 0.7],
            "throughput_ratio_95_ci": [1.5, 1.8],
            "verdict": "PASS"
        },
        CERT_KEY_SOAK: {
            "rss_growth_ratio": 1.0,
            "verdict": "PASS"
        },
        CERT_KEY_INTEROP: {
            "verdict": "PASS"
        },
        CERT_KEY_DIFFERENTIAL: {
            "timeout": "PASS",
            "multithreading_400_count": "PASS",
            "multiprocessing_100_count": "PASS",
            "crash_recovery_os_exit": "PASS",
            "stale_metadata_takeover": "PASS",
            "gc_safety": "PASS"
        }
    }


def test_verify_parity_certificate_valid():
    cert = _make_valid_sample_certificate()
    assert verify_parity_certificate(cert, expected_sha="test_sha_12345") is True


def test_verify_parity_certificate_provenance_mismatch_fails_closed():
    cert = _make_valid_sample_certificate()
    cert["provenance"]["tested_source_sha"] = "old_commit_sha_9999"
    with pytest.raises(ValueError, match="Tested source SHA mismatch in certificate"):
        verify_parity_certificate(cert, expected_sha="current_checked_out_sha_12345")


def test_verify_parity_certificate_missing_field_fails_closed():
    cert = _make_valid_sample_certificate()
    # Mutate field name layer_c_1to1_lifecycle -> bad name
    del cert[CERT_KEY_LAYER_C]
    cert["layer_c_equivalent_lifecycle"] = {"verdict": "PASS"}

    with pytest.raises(KeyError, match=CERT_KEY_LAYER_C):
        verify_parity_certificate(cert)


def test_verify_parity_certificate_gate_failure_fails_closed():
    cert = _make_valid_sample_certificate()
    # Mutate Layer C upper P95 CI to 1.010 (> 1.005)
    cert[CERT_KEY_LAYER_C]["p95_ratio_95_ci"] = [0.95, 1.010]

    with pytest.raises(ValueError, match="Layer C P95 upper CI failed"):
        verify_parity_certificate(cert)
