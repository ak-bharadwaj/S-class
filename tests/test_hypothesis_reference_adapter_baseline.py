"""
S-Class EOS V11.2 - Hypothesis Reference Adapter & Differential Oracle Baseline Tests.
Certifies the ReferenceHypothesisAdapter and IndependentDifferentialOracle against the frozen behavioral contract.
"""

import pytest
import re
from typing import List
from benchmark.hypothesis_parity.observation import StrategySpec, ObservationRecord, ReplayOutcome, compute_size
from benchmark.hypothesis_parity.reference_adapter import ReferenceHypothesisAdapter
from benchmark.hypothesis_parity.differential_oracle import IndependentDifferentialOracle, _validate_value_against_spec


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
    """Validates deterministic execution with fixed seed and structured counterexample replay."""
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

    # Verify direct structured replay
    outcome = ReferenceHypothesisAdapter.replay_case(failing_prop, obs1.shrunk_counterexample, expected_exception_class="AssertionError")
    assert isinstance(outcome, ReplayOutcome)
    assert outcome.reproduced_failure is True
    assert outcome.unexpected_error is False
    assert outcome.exception_class == "AssertionError"


def test_regex_fullmatch_true_vs_false():
    """Fail-Closed Test: Validates exact regex fullmatch=True vs fullmatch=False in adapter and oracle."""
    spec_full = StrategySpec(
        strategy_type="from_regex",
        params={"pattern": r"\d{3}-\d{2}-\d{4}", "fullmatch": True}
    )
    spec_partial = StrategySpec(
        strategy_type="from_regex",
        params={"pattern": r"\d{3}-\d{2}-\d{4}", "fullmatch": False}
    )

    valid_full = "123-45-6789"
    invalid_surrounded = "prefix 123-45-6789 suffix"

    # fullmatch=True checks
    assert _validate_value_against_spec(valid_full, spec_full) is True
    assert _validate_value_against_spec(invalid_surrounded, spec_full) is False

    # fullmatch=False checks
    assert _validate_value_against_spec(valid_full, spec_partial) is True
    assert _validate_value_against_spec(invalid_surrounded, spec_partial) is True


def test_replay_error_classification_type_error_vs_assertion_error():
    """Fail-Closed Test: Replay outcome distinguishes expected AssertionError from unexpected TypeError."""
    def assertion_failing_prop(x: int) -> bool:
        assert x < 0, "x >= 0"
        return True

    def type_error_failing_prop(x: int) -> bool:
        # Invalid operation simulating unexpected runtime error
        return "prefix" + x  # TypeError: can only concatenate str (not "int") to str

    # 1. Expected AssertionError reproduced cleanly
    outcome1 = ReferenceHypothesisAdapter.replay_case(assertion_failing_prop, {"x": 10}, expected_exception_class="AssertionError")
    assert outcome1.reproduced_failure is True
    assert outcome1.unexpected_error is False
    assert outcome1.exception_class == "AssertionError"

    # 2. Unexpected TypeError when expecting AssertionError
    outcome2 = ReferenceHypothesisAdapter.replay_case(type_error_failing_prop, {"x": 10}, expected_exception_class="AssertionError")
    assert outcome2.reproduced_failure is False
    assert outcome2.unexpected_error is True
    assert outcome2.exception_class == "TypeError"


def test_characters_and_emails_strategies():
    """Validates characters() and emails() strategy specs in reference adapter and oracle."""
    specs = {
        "c": StrategySpec(strategy_type="characters", params={"blacklist_categories": ["Cs"], "min_codepoint": 32, "max_codepoint": 126}),
        "em": StrategySpec(strategy_type="emails")
    }

    def verify_types(c: str, em: str) -> bool:
        assert len(c) == 1
        assert "@" in em and "." in em
        return True

    obs = ReferenceHypothesisAdapter.run_campaign(specs, verify_types, max_examples=30)
    assert obs.verdict == "PASS"
    assert obs.cases_executed >= 30

    valid, violations = IndependentDifferentialOracle.validate_observation(obs, verify_types, specs)
    assert valid is True
    assert len(violations) == 0


def test_unsupported_strategy_fails_closed():
    """Fail-Closed Test: Unsupported strategy types raise ValueError and fail oracle validation."""
    bogus_spec = StrategySpec(strategy_type="bogus_ast_strategy", params={})

    with pytest.raises(ValueError, match="Unsupported strategy type"):
        ReferenceHypothesisAdapter.run_campaign({"x": bogus_spec}, lambda x: True, max_examples=10)

    # Oracle must return False for unsupported strategy type
    assert _validate_value_against_spec("some_value", bogus_spec) is False


def test_shrink_evaluation_accounting_unconfounded():
    """Validates that shrink_evaluations is None on reference without speculative heuristic counts."""
    specs = {
        "x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 100})
    }

    def failing_prop(x: int) -> bool:
        assert x < 5, "x >= 5"
        return True

    obs = ReferenceHypothesisAdapter.run_campaign(specs, failing_prop, max_examples=30, enable_shrinking=True)
    assert obs.verdict == "FAIL"
    # shrink_evaluations must be None on reference (not an unverified heuristic)
    assert obs.shrink_evaluations is None
    # total property calls tracked in metadata
    assert obs.metadata.get("total_property_calls", 0) > 0


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
