"""
Unit tests for ParityMetricGate single-source-of-truth declarative gating architecture.
Verifies upper-bound pass/fail, lower-bound pass/fail, exact-boundary conditions,
operational escalation margins, and mandatory required gate enforcement.
"""

import pytest
from benchmark.parity.file_lock_harness import (
    ParityMetricGate,
    GateDirection,
    STANDARD_LATENCY_MEDIAN_GATE,
    STANDARD_LATENCY_P95_GATE,
    STANDARD_THROUGHPUT_GATE,
    REQUIRED_CERTIFICATION_GATES,
    compute_paired_bootstrap_metrics
)


def test_parity_metric_gate_upper_bound_passing():
    gate = ParityMetricGate(
        name="latency_test",
        direction=GateDirection.UPPER_BOUND,
        threshold=1.005,
        escalation_margin=0.020
    )
    # Well below threshold -> PASS
    assert gate.is_passing(0.8500) is True
    # Exactly on threshold -> PASS
    assert gate.is_passing(1.0050) is True
    # Slightly above threshold -> FAIL
    assert gate.is_passing(1.0051) is False
    assert gate.is_passing(1.0100) is False


def test_parity_metric_gate_lower_bound_passing():
    gate = ParityMetricGate(
        name="throughput_test",
        direction=GateDirection.LOWER_BOUND,
        threshold=0.995,
        escalation_margin=0.020
    )
    # Well above threshold -> PASS
    assert gate.is_passing(1.2000) is True
    # Exactly on threshold -> PASS
    assert gate.is_passing(0.9950) is True
    # Slightly below threshold -> FAIL
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
    # Exactly at escalation margin (1.005 - 0.020 = 0.985) -> Escalation triggered
    assert upper_gate.is_near_boundary(0.985) is True
    # Inside escalation margin (0.995 > 0.985) -> Escalation triggered
    assert upper_gate.is_near_boundary(0.995) is True
    # Above threshold (1.010 > 0.985) -> Escalation triggered
    assert upper_gate.is_near_boundary(1.010) is True

    lower_gate = ParityMetricGate(
        name="throughput_test",
        direction=GateDirection.LOWER_BOUND,
        threshold=0.995,
        escalation_margin=0.020
    )
    # Far above boundary (1.200 > 1.015) -> No escalation
    assert lower_gate.is_near_boundary(1.200) is False
    # Exactly at escalation margin (0.995 + 0.020 = 1.015) -> Escalation triggered
    assert lower_gate.is_near_boundary(1.015) is True
    # Inside escalation margin (1.000 < 1.015) -> Escalation triggered
    assert lower_gate.is_near_boundary(1.000) is True
    # Below threshold (0.980 < 1.015) -> Escalation triggered
    assert lower_gate.is_near_boundary(0.980) is True


def test_standard_required_gates_immutability():
    assert len(REQUIRED_CERTIFICATION_GATES) == 3
    assert REQUIRED_CERTIFICATION_GATES[0] == STANDARD_LATENCY_MEDIAN_GATE
    assert REQUIRED_CERTIFICATION_GATES[1] == STANDARD_LATENCY_P95_GATE
    assert REQUIRED_CERTIFICATION_GATES[2] == STANDARD_THROUGHPUT_GATE
    assert STANDARD_LATENCY_MEDIAN_GATE.threshold == 1.005
    assert STANDARD_LATENCY_P95_GATE.threshold == 1.005
    assert STANDARD_THROUGHPUT_GATE.threshold == 0.995


def test_compute_paired_bootstrap_metrics_single_source_of_truth():
    # Synthetic pairs where S-Class is consistently 20% faster
    synthetic_pairs = [(100.0, 125.0) for _ in range(50)]
    metrics = compute_paired_bootstrap_metrics(synthetic_pairs, n_bootstraps=100)

    assert metrics["median_ratio"] == 0.8000
    assert metrics["p95_ratio"] == 0.8000
    assert metrics["throughput_ratio"] == 1.2500
    assert metrics["median_gate_passed"] is True
    assert metrics["p95_gate_passed"] is True
    assert metrics["throughput_gate_passed"] is True
    assert metrics["all_gates_passed"] is True
