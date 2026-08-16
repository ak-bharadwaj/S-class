"""
S-Class EOS V11.2 - Gate 2 Phase 4: Adversarial Test Harness & Oracle Stress Suite.
Fuzzes, stresses, and attempts to break ReferenceHypothesisAdapter and IndependentDifferentialOracle
under adversarial boundary cases, pathological filters, IEEE-754 floats, malformed specs,
replay corruptions, and synthetic shrinking anomaly injections.
"""

import math
import pytest
from typing import List, Dict, Any, Tuple
from benchmark.hypothesis_parity.observation import StrategySpec, ObservationRecord, ReplayOutcome, compute_size
from benchmark.hypothesis_parity.reference_adapter import ReferenceHypothesisAdapter
from benchmark.hypothesis_parity.differential_oracle import IndependentDifferentialOracle, _validate_value_against_spec


# =============================================================================
# 1. IEEE-754 Floating Point Extremes (NaN, Inf, -Inf, -0.0, Subnormal)
# =============================================================================

def test_adversarial_floats_nan_and_infinities():
    """Adversarial Test: Verifies handling of NaN, +inf, -inf in floats strategy and size metrics."""
    specs = {
        "x": StrategySpec(
            strategy_type="floats",
            params={"min_value": None, "max_value": None, "allow_nan": True, "allow_infinity": True}
        )
    }

    # Invariant: x must not be NaN (Fails when NaN is sampled)
    def no_nan_invariant(x: float) -> bool:
        assert not math.isnan(x), f"Disallowed NaN value encountered: {x}"
        return True

    obs = ReferenceHypothesisAdapter.run_campaign(specs, no_nan_invariant, max_examples=100, seed=42, enable_shrinking=True)
    assert obs.verdict == "FAIL"
    assert obs.shrunk_counterexample is not None
    shrunk_val = obs.shrunk_counterexample["x"]
    assert math.isnan(shrunk_val)

    # Oracle must independently validate that math.isnan(x) actually violates the property
    valid, violations = IndependentDifferentialOracle.validate_observation(obs, no_nan_invariant, specs)
    assert valid is True
    assert len(violations) == 0


def test_adversarial_floats_size_metric_finite_vs_nan_inf():
    """Adversarial Test: compute_size handles NaN and infinity without crashing."""
    sz_nan = compute_size(float("nan"))
    sz_inf = compute_size(float("inf"))
    sz_ninf = compute_size(float("-inf"))
    sz_zero = compute_size(0.0)
    sz_normal = compute_size(42.5)

    assert sz_nan > sz_normal
    assert sz_inf > sz_normal
    assert sz_ninf > sz_normal
    assert sz_zero == 0.0
    assert sz_normal == 42.5


# =============================================================================
# 2. Empty and Singleton Domain Boundaries
# =============================================================================

def test_adversarial_singleton_integer_domain():
    """Adversarial Test: Singleton integer domain (min == max) must only generate exact value."""
    specs = {
        "val": StrategySpec(strategy_type="integers", params={"min_value": 777, "max_value": 777})
    }

    generated_values = []

    def check_singleton(val: int) -> bool:
        generated_values.append(val)
        return val == 777

    obs = ReferenceHypothesisAdapter.run_campaign(specs, check_singleton, max_examples=25)
    assert obs.verdict == "PASS"
    assert len(generated_values) >= 1
    assert all(v == 777 for v in generated_values)

    valid, violations = IndependentDifferentialOracle.validate_observation(obs, check_singleton, specs)
    assert valid is True


def test_adversarial_empty_text_and_empty_list_domains():
    """Adversarial Test: Empty string and empty list domains (min_size=0, max_size=0)."""
    specs = {
        "s": StrategySpec(strategy_type="text", params={"min_size": 0, "max_size": 0}),
        "lst": StrategySpec(
            strategy_type="lists",
            params={
                "elements": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 10}),
                "min_size": 0,
                "max_size": 0
            }
        )
    }

    def check_empty(s: str, lst: list) -> bool:
        assert s == ""
        assert lst == []
        return True

    obs = ReferenceHypothesisAdapter.run_campaign(specs, check_empty, max_examples=20)
    assert obs.verdict == "PASS"

    valid, violations = IndependentDifferentialOracle.validate_observation(obs, check_empty, specs)
    assert valid is True


def test_adversarial_singleton_sampled_from():
    """Adversarial Test: Single-element sampled_from domain."""
    specs = {
        "choice": StrategySpec(strategy_type="sampled_from", params={"elements": ["sole_option"]})
    }

    def check_choice(choice: str) -> bool:
        return choice == "sole_option"

    obs = ReferenceHypothesisAdapter.run_campaign(specs, check_choice, max_examples=20)
    assert obs.verdict == "PASS"


# =============================================================================
# 3. Pathological & Extreme Predicate Filtering
# =============================================================================

def test_adversarial_pathological_filter_high_rejection():
    """Adversarial Test: Filter that rejects >98% of inputs (e.g. n % 50 == 0)."""
    specs = {
        "n": StrategySpec(
            strategy_type="integers",
            params={"min_value": 0, "max_value": 1000},
            filter_fn=lambda x: x % 50 == 0
        )
    }

    def check_divisible(n: int) -> bool:
        assert n % 50 == 0, f"Leaked non-divisible value: {n}"
        return True

    obs = ReferenceHypothesisAdapter.run_campaign(specs, check_divisible, max_examples=15)
    assert obs.verdict == "PASS"

    valid, violations = IndependentDifferentialOracle.validate_observation(obs, check_divisible, specs)
    assert valid is True


# =============================================================================
# 4. Complex Regex Grammars & Fullmatch Invariants
# =============================================================================

def test_adversarial_complex_regex_phone_and_email():
    """Adversarial Test: Regex strategies for phone numbers and structured tokens."""
    phone_pattern = r"^\(\d{3}\) \d{3}-\d{4}$"
    specs = {
        "phone": StrategySpec(strategy_type="from_regex", params={"pattern": phone_pattern, "fullmatch": True})
    }

    def no_area_code_999(phone: str) -> bool:
        assert not phone.startswith("(999)"), "Area code 999 is reserved"
        return True

    obs = ReferenceHypothesisAdapter.run_campaign(specs, no_area_code_999, max_examples=50, enable_shrinking=True)
    # Both PASS or FAIL must be validated by Oracle
    valid, violations = IndependentDifferentialOracle.validate_observation(obs, no_area_code_999, specs)
    assert valid is True
    assert len(violations) == 0


# =============================================================================
# 5. Synthetic Shrinking & Observation Anomaly Injections
# =============================================================================

def test_oracle_catches_shrunk_example_that_passes_property():
    """Adversarial Test: Oracle detects when an engine claims failure but provides a passing shrunk example."""
    specs = {
        "x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 100})
    }

    def property_failing_for_greater_than_10(x: int) -> bool:
        return x <= 10

    # Bogus observation: initial example is 20 (fails), but shrunk example is 5 (passes!)
    bogus_obs = ObservationRecord(
        engine_name="AnomalousEngine",
        verdict="FAIL",
        cases_executed=5,
        initial_counterexample={"x": 20},
        shrunk_counterexample={"x": 5},  # BUG: 5 passes property_failing_for_greater_than_10!
        exception_class="AssertionError"
    )

    valid, violations = IndependentDifferentialOracle.validate_observation(bogus_obs, property_failing_for_greater_than_10, specs)
    assert valid is False
    assert any("shrunk_counterexample actually PASSES property" in v for v in violations)


def test_oracle_catches_non_monotonic_shrinking_growth():
    """Adversarial Test: Oracle detects when shrunk counterexample is larger than initial counterexample."""
    specs = {
        "s": StrategySpec(strategy_type="text", params={"min_size": 1, "max_size": 100})
    }

    def forbidden_substring(s: str) -> bool:
        return "CRASH" not in s

    # Bogus observation: initial example "CRASH" (len 5), shrunk example "VERY_LONG_STRING_CRASH" (len 22)
    bogus_obs = ObservationRecord(
        engine_name="AnomalousEngine",
        verdict="FAIL",
        cases_executed=10,
        initial_counterexample={"s": "CRASH"},
        shrunk_counterexample={"s": "VERY_LONG_STRING_CRASH"},
        exception_class="AssertionError"
    )

    valid, violations = IndependentDifferentialOracle.validate_observation(bogus_obs, forbidden_substring, specs)
    assert valid is False
    assert any("Shrunk size" in v and "greater than initial size" in v for v in violations)


def test_oracle_catches_domain_constraint_violation_in_shrunk_output():
    """Adversarial Test: Oracle detects when shrunk output violates strategy parameter bounds."""
    specs = {
        "x": StrategySpec(strategy_type="integers", params={"min_value": 10, "max_value": 50})
    }

    def must_be_even(x: int) -> bool:
        return x % 2 == 0

    # Bogus observation: shrunk x=1 violates min_value=10
    bogus_obs = ObservationRecord(
        engine_name="AnomalousEngine",
        verdict="FAIL",
        cases_executed=5,
        initial_counterexample={"x": 25},
        shrunk_counterexample={"x": 1},  # BUG: 1 < min_value (10)
        exception_class="AssertionError"
    )

    valid, violations = IndependentDifferentialOracle.validate_observation(bogus_obs, must_be_even, specs)
    assert valid is False
    assert any("violates domain strategy spec" in v for v in violations)


# =============================================================================
# 6. Replay Corruption & Unexpected Error Differentiation
# =============================================================================

def test_replay_with_corrupted_counterexample():
    """Adversarial Test: Replaying on mutated/corrupted input that passes yields reproduced_failure=False."""
    def must_be_negative(x: int) -> bool:
        assert x < 0, "x >= 0"
        return True

    # Real counterexample
    real_failing_case = {"x": 10}
    outcome_real = ReferenceHypothesisAdapter.replay_case(must_be_negative, real_failing_case, expected_exception_class="AssertionError")
    assert outcome_real.reproduced_failure is True
    assert outcome_real.unexpected_error is False

    # Corrupted counterexample (mutated to passing input)
    corrupted_case = {"x": -5}
    outcome_corrupt = ReferenceHypothesisAdapter.replay_case(must_be_negative, corrupted_case, expected_exception_class="AssertionError")
    assert outcome_corrupt.reproduced_failure is False
    assert outcome_corrupt.unexpected_error is False


def test_replay_with_unexpected_runtime_exception():
    """Adversarial Test: Replay distinguishes expected failure from unexpected ZeroDivisionError."""
    def division_bug_prop(x: int) -> bool:
        val = 100 // x  # Raises ZeroDivisionError if x == 0
        assert val < 50
        return True

    outcome = ReferenceHypothesisAdapter.replay_case(division_bug_prop, {"x": 0}, expected_exception_class="AssertionError")
    assert outcome.reproduced_failure is False
    assert outcome.unexpected_error is True
    assert outcome.exception_class == "ZeroDivisionError"


# =============================================================================
# 7. Nested Composite & Multi-Parameter Verification
# =============================================================================

def test_adversarial_nested_tuples_and_lists():
    """Adversarial Test: Multi-layer nested tuple containing lists of floats and strings."""
    specs = {
        "payload": StrategySpec(
            strategy_type="tuples",
            params={
                "elements": [
                    StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 100}),
                    StrategySpec(
                        strategy_type="lists",
                        params={
                            "elements": StrategySpec(strategy_type="text", params={"min_size": 1, "max_size": 5}),
                            "min_size": 1,
                            "max_size": 4
                        }
                    )
                ]
            }
        )
    }

    def check_nested(payload: Tuple[int, List[str]]) -> bool:
        num, words = payload
        assert isinstance(num, int)
        assert isinstance(words, list)
        assert len(words) >= 1
        return True

    obs = ReferenceHypothesisAdapter.run_campaign(specs, check_nested, max_examples=30)
    assert obs.verdict == "PASS"

    valid, violations = IndependentDifferentialOracle.validate_observation(obs, check_nested, specs)
    assert valid is True
    assert len(violations) == 0
