"""
Tests for Gate 2 Parity Certificate Verifier (Provenance & Fail-Closed Integrity).
Verifies that missing provenance, UNKNOWN SHA, mismatched SHA, or gate violations fail closed.
"""

import copy
import pytest
from typing import Dict, Any

from benchmark.hypothesis_parity.verify_gate_2_certificate import verify_gate2_certificate


@pytest.fixture
def valid_certificate() -> Dict[str, Any]:
    return {
        "certificate_id": "OSS-PARITY-GATE-2-PROPERTY-TESTING-LINUX-ABC123DEF456",
        "schema_version": "1.0.0",
        "gate_name": "Gate 2: Hypothesis Property Testing & Invariant Verification Parity",
        "provenance": {
            "runner_os": "Linux",
            "tested_source_sha": "abc123def4567890abcdef1234567890abcdef12",
            "workflow_run_id": "999999",
            "python_runtime_version": "3.12.13",
            "unicode_database_version": "15.0.0",
            "index_sha256_checksum": "abcdef",
            "timestamp_iso": "2026-08-17T06:00:00Z"
        },
        "acceptance_criteria": {
            "trials_per_domain": 1000,
            "total_paired_benchmark_trials": 6000,
            "soak_cycles_executed": 5000,
            "median_ratio_upper_bound": 1.05,
            "p95_ratio_upper_bound": 1.05,
            "throughput_ratio_lower_bound": 0.95,
            "soak_growth_upper_bound": 1.05
        },
        "aggregate_performance_metrics": {
            "median_ratio": 0.015,
            "median_ratio_95_ci": [0.010, 0.020],
            "p95_ratio": 0.040,
            "p95_ratio_95_ci": [0.035, 0.045],
            "throughput_ratio": 45.0,
            "throughput_ratio_95_ci": [42.0, 48.0],
            "median_gate_passed": True,
            "p95_gate_passed": True,
            "throughput_gate_passed": True,
            "all_gates_passed": True
        },
        "domain_performance_metrics": {
            "integers": {"domain_gate_passed": True},
            "floats": {"domain_gate_passed": True},
            "text": {"domain_gate_passed": True},
            "lists": {"domain_gate_passed": True},
            "from_regex": {"domain_gate_passed": True},
            "sampled_from": {"domain_gate_passed": True}
        },
        "long_soak_memory": {
            "soak_cycles_executed": 5000,
            "rss_growth_ratio": 1.0000,
            "soak_gate_passed": True
        },
        "final_verdict": "PASS"
    }


def test_verifier_passes_on_valid_certificate(valid_certificate):
    sha = "abc123def4567890abcdef1234567890abcdef12"
    assert verify_gate2_certificate(valid_certificate, expected_sha=sha) is True


def test_verifier_fails_on_missing_tested_source_sha(valid_certificate):
    cert = copy.deepcopy(valid_certificate)
    del cert["provenance"]["tested_source_sha"]
    with pytest.raises(ValueError, match="Provenance missing or UNKNOWN tested_source_sha"):
        verify_gate2_certificate(cert, expected_sha="abc123def4567890abcdef1234567890abcdef12")


def test_verifier_fails_on_unknown_tested_source_sha(valid_certificate):
    cert = copy.deepcopy(valid_certificate)
    cert["provenance"]["tested_source_sha"] = "UNKNOWN"
    with pytest.raises(ValueError, match="Provenance missing or UNKNOWN tested_source_sha"):
        verify_gate2_certificate(cert, expected_sha="abc123def4567890abcdef1234567890abcdef12")


def test_verifier_fails_on_empty_tested_source_sha(valid_certificate):
    cert = copy.deepcopy(valid_certificate)
    cert["provenance"]["tested_source_sha"] = ""
    with pytest.raises(ValueError, match="Provenance missing or UNKNOWN tested_source_sha"):
        verify_gate2_certificate(cert, expected_sha="abc123def4567890abcdef1234567890abcdef12")


def test_verifier_fails_on_mismatched_tested_source_sha(valid_certificate):
    cert = copy.deepcopy(valid_certificate)
    cert["provenance"]["tested_source_sha"] = "wrong_commit_sha_123456789"
    with pytest.raises(ValueError, match="Tested source SHA mismatch"):
        verify_gate2_certificate(cert, expected_sha="abc123def4567890abcdef1234567890abcdef12")


def test_verifier_fails_on_missing_provenance(valid_certificate):
    cert = copy.deepcopy(valid_certificate)
    del cert["provenance"]
    with pytest.raises(ValueError, match="Missing provenance"):
        verify_gate2_certificate(cert, expected_sha="abc123def4567890abcdef1234567890abcdef12")


def test_verifier_fails_on_invalid_certificate_id(valid_certificate):
    cert = copy.deepcopy(valid_certificate)
    cert["certificate_id"] = "INVALID-ID"
    with pytest.raises(ValueError, match="Invalid certificate_id"):
        verify_gate2_certificate(cert, expected_sha="abc123def4567890abcdef1234567890abcdef12")


def test_verifier_fails_on_insufficient_benchmark_trials(valid_certificate):
    cert = copy.deepcopy(valid_certificate)
    cert["acceptance_criteria"]["total_paired_benchmark_trials"] = 3000
    with pytest.raises(ValueError, match="Total paired benchmark trials must be at least 6000"):
        verify_gate2_certificate(cert, expected_sha="abc123def4567890abcdef1234567890abcdef12")


def test_verifier_fails_on_insufficient_soak_cycles(valid_certificate):
    cert = copy.deepcopy(valid_certificate)
    cert["acceptance_criteria"]["soak_cycles_executed"] = 1000
    with pytest.raises(ValueError, match="Soak cycles must be 5000"):
        verify_gate2_certificate(cert, expected_sha="abc123def4567890abcdef1234567890abcdef12")


def test_verifier_fails_on_median_ratio_ci_exceeded(valid_certificate):
    cert = copy.deepcopy(valid_certificate)
    cert["aggregate_performance_metrics"]["median_ratio_95_ci"] = [1.02, 1.08]
    with pytest.raises(ValueError, match="Aggregate median upper 95% CI failed"):
        verify_gate2_certificate(cert, expected_sha="abc123def4567890abcdef1234567890abcdef12")


def test_verifier_fails_on_p95_ratio_ci_exceeded(valid_certificate):
    cert = copy.deepcopy(valid_certificate)
    cert["aggregate_performance_metrics"]["p95_ratio_95_ci"] = [1.03, 1.09]
    with pytest.raises(ValueError, match="Aggregate P95 upper 95% CI failed"):
        verify_gate2_certificate(cert, expected_sha="abc123def4567890abcdef1234567890abcdef12")


def test_verifier_fails_on_throughput_ci_below_threshold(valid_certificate):
    cert = copy.deepcopy(valid_certificate)
    cert["aggregate_performance_metrics"]["throughput_ratio_95_ci"] = [0.88, 0.94]
    with pytest.raises(ValueError, match="Aggregate throughput lower 95% CI failed"):
        verify_gate2_certificate(cert, expected_sha="abc123def4567890abcdef1234567890abcdef12")


def test_verifier_fails_on_domain_gate_failure(valid_certificate):
    cert = copy.deepcopy(valid_certificate)
    cert["domain_performance_metrics"]["integers"]["domain_gate_passed"] = False
    with pytest.raises(ValueError, match="Domain 'integers' failed performance gate"):
        verify_gate2_certificate(cert, expected_sha="abc123def4567890abcdef1234567890abcdef12")


def test_verifier_fails_on_soak_memory_growth_exceeded(valid_certificate):
    cert = copy.deepcopy(valid_certificate)
    cert["long_soak_memory"]["rss_growth_ratio"] = 1.085
    with pytest.raises(ValueError, match="Soak memory growth failed"):
        verify_gate2_certificate(cert, expected_sha="abc123def4567890abcdef1234567890abcdef12")


def test_verifier_fails_on_failed_final_verdict(valid_certificate):
    cert = copy.deepcopy(valid_certificate)
    cert["final_verdict"] = "FAIL"
    with pytest.raises(ValueError, match="Final verdict must be PASS"):
        verify_gate2_certificate(cert, expected_sha="abc123def4567890abcdef1234567890abcdef12")
