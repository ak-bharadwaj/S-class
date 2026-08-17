"""
S-Class EOS V11.2 - Gate 2 Phase 7: Mutation & Injected Defect Suite.
Deliberately mutates candidate observations, shrinkers, domain boundaries, and replay outcomes
to prove that the IndependentDifferentialOracle catches 100% of injected defects.
Supported Python Versions: 3.10-3.13.
"""

import pytest
import math
from typing import Dict, Any
from benchmark.hypothesis_parity.observation import StrategySpec, ObservationRecord, compute_size
from benchmark.hypothesis_parity.differential_oracle import IndependentDifferentialOracle, DifferentialVerdict


# =============================================================================
# Mutation 1: Candidate Reports False Failure on Passing Example
# =============================================================================

def test_mutation_candidate_reports_false_failure_on_passing_input():
    """Mutation: Candidate self-reports FAIL, but the emitted counterexample actually PASSES the property."""
    specs = {"x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 100})}

    def strictly_positive_property(x: int) -> bool:
        assert x >= 0, "x is negative"
        return True

    # Injected bogus observation: claims failure on x=50
    mutated_obs = ObservationRecord(
        engine_name="S-Class/MutatedCandidate",
        verdict="FAIL",
        cases_executed=10,
        initial_counterexample={"x": 50},
        shrunk_counterexample={"x": 50},
        exception_class="AssertionError"
    )

    valid, violations = IndependentDifferentialOracle.validate_observation(mutated_obs, strictly_positive_property, specs)
    assert valid is False
    assert any("actually PASSES property" in v for v in violations)


# =============================================================================
# Mutation 2: Non-Monotonic Shrinking Size Growth
# =============================================================================

def test_mutation_shrinker_expands_size_non_monotonic():
    """Mutation: Candidate shrinker produces a counterexample whose size is larger than the initial counterexample."""
    specs = {"s": StrategySpec(strategy_type="text", params={"min_size": 1, "max_size": 50})}

    def no_forbidden_substring(s: str) -> bool:
        assert "FAIL" not in s, "Found FAIL"
        return True

    # Injected bogus observation: initial has length 4, shrunk has length 10
    mutated_obs = ObservationRecord(
        engine_name="S-Class/MutatedCandidate",
        verdict="FAIL",
        cases_executed=15,
        initial_counterexample={"s": "FAIL"},
        shrunk_counterexample={"s": "FAIL_EXTRA_CHARS"},
        exception_class="AssertionError"
    )

    valid, violations = IndependentDifferentialOracle.validate_observation(mutated_obs, no_forbidden_substring, specs)
    assert valid is False
    assert any("not monotonic" in v for v in violations)


# =============================================================================
# Mutation 3: Shrunk Counterexample Violates Domain Constraints
# =============================================================================

def test_mutation_shrunk_counterexample_violates_domain_bounds():
    """Mutation: Shrunk counterexample value lies outside the StrategySpec parameter bounds."""
    specs = {"x": StrategySpec(strategy_type="integers", params={"min_value": 10, "max_value": 50})}

    def below_20_property(x: int) -> bool:
        assert x <= 20, "x > 20"
        return True

    # Injected bogus observation: shrunk value x=5 violates min_value=10
    mutated_obs = ObservationRecord(
        engine_name="S-Class/MutatedCandidate",
        verdict="FAIL",
        cases_executed=12,
        initial_counterexample={"x": 25},
        shrunk_counterexample={"x": 5},
        exception_class="AssertionError"
    )

    valid, violations = IndependentDifferentialOracle.validate_observation(mutated_obs, below_20_property, specs)
    assert valid is False
    assert any("violates domain strategy spec" in v for v in violations)


# =============================================================================
# Mutation 4: Verdict Disagreement (False Negative)
# =============================================================================

def test_mutation_candidate_claims_pass_when_reference_fails():
    """Mutation: Reference correctly finds a counterexample, while candidate falsely reports PASS."""
    specs = {"x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 100})}

    def strict_zero_property(x: int) -> bool:
        assert x == 0, "x != 0"
        return True

    ref_obs = ObservationRecord(
        engine_name="Hypothesis/Reference",
        verdict="FAIL",
        cases_executed=5,
        initial_counterexample={"x": 10},
        shrunk_counterexample={"x": 1},
        exception_class="AssertionError"
    )

    mutated_cand_obs = ObservationRecord(
        engine_name="S-Class/MutatedCandidate",
        verdict="PASS",
        cases_executed=100
    )

    verdict = IndependentDifferentialOracle.compare_observations(ref_obs, mutated_cand_obs, strict_zero_property, specs)
    assert verdict.overall_status == "DISCREPANCY"
    assert verdict.verdict_agreement is False
    assert any("Verdict mismatch" in v for v in verdict.violations)


# =============================================================================
# Mutation 5: Exception Class Mismatch
# =============================================================================

def test_mutation_exception_class_mismatch():
    """Mutation: Reference records TypeError, while candidate records AssertionError."""
    specs = {"x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 100})}

    def type_error_property(x: int) -> bool:
        return x / "invalid_str"

    ref_obs = ObservationRecord(
        engine_name="Hypothesis/Reference",
        verdict="FAIL",
        cases_executed=1,
        initial_counterexample={"x": 5},
        shrunk_counterexample={"x": 0},
        exception_class="TypeError"
    )

    mutated_cand_obs = ObservationRecord(
        engine_name="S-Class/MutatedCandidate",
        verdict="FAIL",
        cases_executed=1,
        initial_counterexample={"x": 5},
        shrunk_counterexample={"x": 0},
        exception_class="AssertionError"
    )

    verdict = IndependentDifferentialOracle.compare_observations(ref_obs, mutated_cand_obs, type_error_property, specs)
    assert verdict.overall_status == "DISCREPANCY"
    assert verdict.exception_class_agreement is False
    assert any("Exception class mismatch" in v for v in verdict.violations)


# =============================================================================
# Mutation 6: Out-of-Spec Float NaN/Infinity Injection
# =============================================================================

def test_mutation_out_of_spec_nan_float_injection():
    """Mutation: Candidate emits NaN when allow_nan=False."""
    specs = {"f": StrategySpec(strategy_type="floats", params={"min_value": 0.0, "max_value": 10.0, "allow_nan": False})}

    def dummy_property(f: float) -> bool:
        assert f < 5.0, "f >= 5.0"
        return True

    mutated_obs = ObservationRecord(
        engine_name="S-Class/MutatedCandidate",
        verdict="FAIL",
        cases_executed=5,
        initial_counterexample={"f": float("nan")},
        shrunk_counterexample={"f": float("nan")},
        exception_class="AssertionError"
    )

    valid, violations = IndependentDifferentialOracle.validate_observation(mutated_obs, dummy_property, specs)
    assert valid is False
    assert any("violates domain strategy spec" in v for v in violations)
