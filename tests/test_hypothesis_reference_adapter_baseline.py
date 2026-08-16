"""
S-Class EOS V11.2 - Hypothesis Reference Adapter & Differential Oracle Baseline Tests.
Certifies the ReferenceHypothesisAdapter and IndependentDifferentialOracle against the frozen behavioral contract.
"""

import pytest
from typing import List
from benchmark.hypothesis_parity.observation import StrategySpec, ObservationRecord, compute_size
from benchmark.hypothesis_parity.reference_adapter import ReferenceHypothesisAdapter
from benchmark.hypothesis_parity.differential_oracle import IndependentDifferentialOracle


def test_reference_adapter_clean_passing_property():
    """Validates that a universally satisfied invariant produces a verified PASS observation."""
    specs = {
        "x": StrategySpec(strategy_type="integers", params={"min_value": -1000, "max_value": 1000}),
        "y": StrategySpec(strategy_type="integers", params={"min_value": -1000, "max_value": 1000})
    }

    def commutative_addition(x: int, y: int) -> bool:
        return (x + y) == (y + x)

    obs = ReferenceHypothesisAdapter.run_campaign(specs, commutative_addition, max_examples=50)
    assert obs.verdict == "PASS"
    assert obs.cases_executed >= 50
    assert obs.initial_counterexample is None
    assert obs.shrunk_counterexample is None

    valid, violations = IndependentDifferentialOracle.validate_observation(obs, commutative_addition, specs)
    assert valid is True
    assert len(violations) == 0


def test_reference_adapter_failing_integer_property_with_shrinking():
    """Validates that a failing integer invariant is caught and shrunk to minimal falsifying boundary."""
    specs = {
        "x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 1000})
    }

    def bound_check(x: int) -> bool:
        assert x <= 10, f"Invariant violated: {x} > 10"
        return True

    obs = ReferenceHypothesisAdapter.run_campaign(specs, bound_check, max_examples=50, enable_shrinking=True)
    assert obs.verdict == "FAIL"
    assert obs.exception_class == "AssertionError"
    assert obs.initial_counterexample is not None
    assert obs.shrunk_counterexample is not None
    # Minimized integer should be 11 (the smallest integer > 10)
    assert obs.shrunk_counterexample["x"] == 11

    valid, violations = IndependentDifferentialOracle.validate_observation(obs, bound_check, specs)
    assert valid is True
    assert len(violations) == 0


def test_reference_adapter_failing_string_property_with_shrinking():
    """Validates string strategy generation and lexicographical shrinking on failing invariant."""
    specs = {
        "s": StrategySpec(strategy_type="text", params={"alphabet": "abcdefghijklmnopqrstuvwxyz", "min_size": 1, "max_size": 30})
    }

    def no_forbidden_character(s: str) -> bool:
        assert "z" not in s, f"Found forbidden char 'z' in '{s}'"
        return True

    obs = ReferenceHypothesisAdapter.run_campaign(specs, no_forbidden_character, max_examples=100, enable_shrinking=True)
    assert obs.verdict == "FAIL"
    assert obs.shrunk_counterexample is not None
    # Minimized string containing 'z' should be 'z'
    assert obs.shrunk_counterexample["s"] == "z"

    valid, violations = IndependentDifferentialOracle.validate_observation(obs, no_forbidden_character, specs)
    assert valid is True
    assert len(violations) == 0


def test_reference_adapter_failing_list_property_with_shrinking():
    """Validates list strategy generation and element-wise shrinking."""
    specs = {
        "items": StrategySpec(
            strategy_type="lists",
            params={
                "elements": StrategySpec(strategy_type="integers", params={"min_value": 1, "max_value": 50}),
                "min_size": 1,
                "max_size": 20
            }
        )
    }

    def max_sum_under_30(items: List[int]) -> bool:
        assert sum(items) < 30, f"Sum {sum(items)} exceeds 30"
        return True

    obs = ReferenceHypothesisAdapter.run_campaign(specs, max_sum_under_30, max_examples=100, enable_shrinking=True)
    assert obs.verdict == "FAIL"
    assert obs.shrunk_counterexample is not None
    shrunk_items = obs.shrunk_counterexample["items"]
    # Shrunk list must still violate invariant (sum >= 30)
    assert sum(shrunk_items) >= 30

    valid, violations = IndependentDifferentialOracle.validate_observation(obs, max_sum_under_30, specs)
    assert valid is True
    assert len(violations) == 0


def test_reference_adapter_filtered_strategy():
    """Validates that strategy.filter() strictly prevents invalid domain values from reaching property."""
    specs = {
        "even_num": StrategySpec(
            strategy_type="integers",
            params={"min_value": 0, "max_value": 200},
            filter_fn=lambda n: n % 2 == 0
        )
    }

    received_odds = []

    def verify_only_evens(even_num: int) -> bool:
        if even_num % 2 != 0:
            received_odds.append(even_num)
        return even_num % 2 == 0

    obs = ReferenceHypothesisAdapter.run_campaign(specs, verify_only_evens, max_examples=40)
    assert obs.verdict == "PASS"
    assert len(received_odds) == 0

    valid, violations = IndependentDifferentialOracle.validate_observation(obs, verify_only_evens, specs)
    assert valid is True
    assert len(violations) == 0


def test_reference_adapter_replay_and_determinism():
    """Validates deterministic execution with fixed seed and direct counterexample replay."""
    specs = {
        "x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 500})
    }

    def failing_prop(x: int) -> bool:
        assert x < 25, "x is >= 25"
        return True

    obs1 = ReferenceHypothesisAdapter.run_campaign(specs, failing_prop, max_examples=50, seed=42)
    obs2 = ReferenceHypothesisAdapter.run_campaign(specs, failing_prop, max_examples=50, seed=42)

    assert obs1.verdict == "FAIL"
    assert obs2.verdict == "FAIL"
    assert obs1.shrunk_counterexample == obs2.shrunk_counterexample

    # Verify direct replay
    reproduced = ReferenceHypothesisAdapter.replay_case(failing_prop, obs1.shrunk_counterexample)
    assert reproduced is True


def test_differential_oracle_catches_bogus_observations():
    """Validates that the Independent Differential Oracle catches false self-reports."""
    specs = {
        "x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 100})
    }

    def dummy_prop(x: int) -> bool:
        return x < 50

    # Bogus observation: claims FAIL, but gives passing counterexample x=10
    bogus_obs = ObservationRecord(
        engine_name="BogusEngine",
        verdict="FAIL",
        cases_executed=10,
        initial_counterexample={"x": 10},
        shrunk_counterexample={"x": 10},
        exception_class="AssertionError"
    )

    valid, violations = IndependentDifferentialOracle.validate_observation(bogus_obs, dummy_prop, specs)
    assert valid is False
    assert any("actually PASSES property" in v for v in violations)
