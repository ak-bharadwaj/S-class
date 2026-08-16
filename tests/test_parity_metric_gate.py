"""
Unit tests for ParityMetricGate single-source-of-truth declarative gating architecture.
Verifies upper-bound pass/fail, lower-bound pass/fail, exact-boundary conditions,
operational escalation margins, mandatory required gate enforcement, fail-closed empty behavior,
and input validation (__post_init__).
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
    # Exactly at escalation margin (1.005 - 0.020 = 0.985) -> Escalation triggered
    assert upper_gate.is_near_boundary(0.985) is True
    # Inside escalation margin (0.995 > 0.985) -> Escalation triggered
    assert upper_gate.is_near_boundary(0.995) is True
    # Exactly at threshold (1.005) -> Escalation triggered
    assert upper_gate.is_near_boundary(1.005) is True
    # Beyond threshold (1.010 > 0.985) -> Escalation triggered
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
    # Exactly at threshold (0.995) -> Escalation triggered
    assert lower_gate.is_near_boundary(0.995) is True
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


def test_optional_diagnostic_gate_cannot_suppress_required_gates():
    # Pass a custom permissive diagnostic gate
    custom_gate = ParityMetricGate(
        name="custom_diagnostic",
        direction=GateDirection.UPPER_BOUND,
        threshold=5.000,
        escalation_margin=0.5
    )
    # Pairs where latency fails standard 1.005 threshold (ratio = 1.50)
    failing_pairs = [(150.0, 100.0) for _ in range(50)]
    metrics = compute_paired_bootstrap_metrics(failing_pairs, n_bootstraps=100, optional_diagnostic_gates=[custom_gate])

    # Required gates MUST still fail the run
    assert metrics["median_ratio"] == 1.5000
    assert metrics["median_gate_passed"] is False
    assert metrics["all_gates_passed"] is False


def test_empty_observations_fail_closed():
    empty_metrics = compute_paired_bootstrap_metrics([])
    assert empty_metrics["median_gate_passed"] is False
    assert empty_metrics["p95_gate_passed"] is False
    assert empty_metrics["throughput_gate_passed"] is False
    assert empty_metrics["all_gates_passed"] is False
    assert empty_metrics["bootstraps_evaluated"] == 0


def test_parity_metric_gate_post_init_validation():
    # Invalid empty name
    with pytest.raises(ValueError, match="non-empty string"):
        ParityMetricGate(name="", direction=GateDirection.UPPER_BOUND, threshold=1.005)

    # Invalid direction
    with pytest.raises(ValueError, match="instance of GateDirection"):
        ParityMetricGate(name="test", direction="UPPER", threshold=1.005)  # type: ignore

    # Non-positive or non-finite threshold
    with pytest.raises(ValueError, match="positive finite float"):
        ParityMetricGate(name="test", direction=GateDirection.UPPER_BOUND, threshold=0.0)
    with pytest.raises(ValueError, match="positive finite float"):
        ParityMetricGate(name="test", direction=GateDirection.UPPER_BOUND, threshold=-1.0)
    with pytest.raises(ValueError, match="positive finite float"):
        ParityMetricGate(name="test", direction=GateDirection.UPPER_BOUND, threshold=float("nan"))
    with pytest.raises(ValueError, match="positive finite float"):
        ParityMetricGate(name="test", direction=GateDirection.UPPER_BOUND, threshold=float("inf"))

    # Negative or non-finite escalation margin
    with pytest.raises(ValueError, match="non-negative finite float"):
        ParityMetricGate(name="test", direction=GateDirection.UPPER_BOUND, threshold=1.005, escalation_margin=-0.01)
    with pytest.raises(ValueError, match="non-negative finite float"):
        ParityMetricGate(name="test", direction=GateDirection.UPPER_BOUND, threshold=1.005, escalation_margin=float("nan"))

    # Non-positive bootstrap minimum
    with pytest.raises(ValueError, match="positive integer >= 1"):
        ParityMetricGate(name="test", direction=GateDirection.UPPER_BOUND, threshold=1.005, escalated_bootstrap_min=0)
    with pytest.raises(ValueError, match="positive integer >= 1"):
        ParityMetricGate(name="test", direction=GateDirection.UPPER_BOUND, threshold=1.005, escalated_bootstrap_min=-50)


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
