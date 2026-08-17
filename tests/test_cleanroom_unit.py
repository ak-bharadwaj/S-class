"""
S-Class EOS V11.2 - Gate 2 Phase 5: Clean-Room Engine Unit Test Suite.
Verifies the independent CleanRoomPropertyEngine against the frozen contract.
Tests strategy generation, boundary bias, monotonic shrinking, determinism, filtering,
replay mechanics, and independent oracle validation.
"""

import pytest
import math
import random
from typing import List, Dict, Any, Tuple
from benchmark.hypothesis_parity.observation import StrategySpec, ObservationRecord, ReplayOutcome, compute_size
from benchmark.hypothesis_parity.cleanroom_engine import CleanRoomPropertyEngine, _generate_random_value, _generate_boundary_candidates
from benchmark.hypothesis_parity.differential_oracle import IndependentDifferentialOracle, _validate_value_against_spec


# =============================================================================
# 1. Strategy Generation Conformance
# =============================================================================

def test_cleanroom_strategy_generation_all_primitives():
    """Validates that random value generation adheres to domain constraints for all strategy types."""
    rng = random.Random(42)

    specs = [
        StrategySpec(strategy_type="integers", params={"min_value": -50, "max_value": 50}),
        StrategySpec(strategy_type="floats", params={"min_value": 0.0, "max_value": 10.0, "allow_nan": False, "allow_infinity": False}),
        StrategySpec(strategy_type="text", params={"alphabet": "abcdef", "min_size": 2, "max_size": 10}),
        StrategySpec(strategy_type="characters", params={"min_codepoint": 65, "max_codepoint": 90}),
        StrategySpec(strategy_type="emails"),
        StrategySpec(strategy_type="from_regex", params={"pattern": r"\d{3}-\d{2}-\d{4}", "fullmatch": True}),
        StrategySpec(strategy_type="sampled_from", params={"elements": [10, 20, 30, 40]}),
        StrategySpec(
            strategy_type="lists",
            params={
                "elements": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 100}),
                "min_size": 1,
                "max_size": 5
            }
        ),
        StrategySpec(
            strategy_type="tuples",
            params={
                "elements": [
                    StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 10}),
                    StrategySpec(strategy_type="text", params={"min_size": 1, "max_size": 3})
                ]
            }
        )
    ]

    for spec in specs:
        for _ in range(25):
            val = _generate_random_value(spec, rng)
            assert _validate_value_against_spec(val, spec) is True, f"Generated value {val} failed spec {spec}"


# =============================================================================
# 2. Boundary Biasing in Initial Segment
# =============================================================================

def test_cleanroom_boundary_sampling_in_first_segment():
    """Validates that boundary values (0, min, max) are evaluated in initial segment."""
    specs = {
        "x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 1000})
    }

    seen_values = []

    def observe_inputs(x: int) -> bool:
        seen_values.append(x)
        return True

    obs = CleanRoomPropertyEngine.run_campaign(specs, observe_inputs, max_examples=40, seed=42)
    assert obs.verdict == "PASS"
    assert obs.cases_executed == 40

    # Initial segment (first 4 values) should contain domain boundaries like 0 or 1000
    initial_segment = seen_values[:4]
    assert any(v in (0, 1000, 1, 999) for v in initial_segment)


# =============================================================================
# 3. Shrinking Monotonicity & Failure Preservation
# =============================================================================

def test_cleanroom_shrinking_integers():
    """Validates that a failing integer property shrinks monotonically to the exact falsifying boundary."""
    specs = {
        "x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 1000})
    }

    def bound_check(x: int) -> bool:
        assert x <= 15, f"Violated: {x} > 15"
        return True

    obs = CleanRoomPropertyEngine.run_campaign(specs, bound_check, max_examples=50, seed=42, enable_shrinking=True)
    assert obs.verdict == "FAIL"
    assert obs.initial_counterexample is not None
    assert obs.shrunk_counterexample is not None
    # Boundary value > 15 is 16
    assert obs.shrunk_counterexample["x"] == 16
    assert obs.shrink_evaluations is not None
    assert obs.shrink_evaluations <= 500

    valid, violations = IndependentDifferentialOracle.validate_observation(obs, bound_check, specs)
    assert valid is True
    assert len(violations) == 0


def test_cleanroom_shrinking_strings():
    """Validates that a failing string property shrinks to minimal substring."""
    specs = {
        "s": StrategySpec(strategy_type="text", params={"alphabet": "abcdefghijklmnopqrstuvwxyz", "min_size": 1, "max_size": 40})
    }

    def no_z_char(s: str) -> bool:
        assert "z" not in s, f"Found 'z' in {s}"
        return True

    obs = CleanRoomPropertyEngine.run_campaign(specs, no_z_char, max_examples=50, seed=42, enable_shrinking=True)
    assert obs.verdict == "FAIL"
    assert obs.shrunk_counterexample is not None
    assert "z" in obs.shrunk_counterexample["s"]
    # Shrunk string should be minimal
    assert len(obs.shrunk_counterexample["s"]) <= len(obs.initial_counterexample["s"])

    valid, violations = IndependentDifferentialOracle.validate_observation(obs, no_z_char, specs)
    assert valid is True
    assert len(violations) == 0


def test_cleanroom_shrinking_lists():
    """Validates list shrinking (reduction of both list length and element values)."""
    specs = {
        "items": StrategySpec(
            strategy_type="lists",
            params={
                "elements": StrategySpec(strategy_type="integers", params={"min_value": 1, "max_value": 50}),
                "min_size": 1,
                "max_size": 15
            }
        )
    }

    def max_sum_under_25(items: List[int]) -> bool:
        assert sum(items) < 25, f"Sum {sum(items)} exceeds 25"
        return True

    obs = CleanRoomPropertyEngine.run_campaign(specs, max_sum_under_25, max_examples=50, seed=42, enable_shrinking=True)
    assert obs.verdict == "FAIL"
    assert obs.shrunk_counterexample is not None
    shrunk_lst = obs.shrunk_counterexample["items"]
    assert sum(shrunk_lst) >= 25
    assert compute_size(obs.shrunk_counterexample) <= compute_size(obs.initial_counterexample)

    valid, violations = IndependentDifferentialOracle.validate_observation(obs, max_sum_under_25, specs)
    assert valid is True
    assert len(violations) == 0


# =============================================================================
# 4. Deterministic Replay Under Fixed Seed
# =============================================================================

def test_cleanroom_deterministic_seed_replay():
    """Validates that fixed seed produces identical input sequence and reproducible counterexample."""
    specs = {
        "x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 500})
    }

    def failing_prop(x: int) -> bool:
        assert x < 30, "x >= 30"
        return True

    obs1 = CleanRoomPropertyEngine.run_campaign(specs, failing_prop, max_examples=40, seed=999)
    obs2 = CleanRoomPropertyEngine.run_campaign(specs, failing_prop, max_examples=40, seed=999)

    assert obs1.verdict == "FAIL"
    assert obs2.verdict == "FAIL"
    assert obs1.cases_executed == obs2.cases_executed
    assert obs1.initial_counterexample == obs2.initial_counterexample
    assert obs1.shrunk_counterexample == obs2.shrunk_counterexample


# =============================================================================
# 5. Filter Exclusion Correctness
# =============================================================================

def test_cleanroom_filter_exclusion():
    """Validates that strategy filter_fn strictly prevents invalid values from reaching the property."""
    specs = {
        "even_val": StrategySpec(
            strategy_type="integers",
            params={"min_value": 0, "max_value": 100},
            filter_fn=lambda x: x % 2 == 0
        )
    }

    leaked_odds = []

    def check_evens(even_val: int) -> bool:
        if even_val % 2 != 0:
            leaked_odds.append(even_val)
        return even_val % 2 == 0

    obs = CleanRoomPropertyEngine.run_campaign(specs, check_evens, max_examples=30, seed=42)
    assert obs.verdict == "PASS"
    assert len(leaked_odds) == 0

    valid, violations = IndependentDifferentialOracle.validate_observation(obs, check_evens, specs)
    assert valid is True
    assert len(violations) == 0


# =============================================================================
# 6. Structured Replay Outcome
# =============================================================================

def test_cleanroom_replay_outcome_integrity():
    """Validates structured replay outcomes for reproduced, corrupted, and error cases."""
    def target_prop(x: int) -> bool:
        assert x < 5, "x >= 5"
        return True

    # 1. Clean failure reproduction
    outcome_clean = CleanRoomPropertyEngine.replay_case(target_prop, {"x": 10}, expected_exception_class="AssertionError")
    assert outcome_clean.reproduced_failure is True
    assert outcome_clean.unexpected_error is False

    # 2. Corrupted counterexample (passes)
    outcome_pass = CleanRoomPropertyEngine.replay_case(target_prop, {"x": 2}, expected_exception_class="AssertionError")
    assert outcome_pass.reproduced_failure is False
    assert outcome_pass.unexpected_error is False

    # 3. Unexpected error
    def buggy_prop(x: int) -> bool:
        return x / "invalid_str"

    outcome_err = CleanRoomPropertyEngine.replay_case(buggy_prop, {"x": 10}, expected_exception_class="AssertionError")
    assert outcome_err.reproduced_failure is False
    assert outcome_err.unexpected_error is True
    assert outcome_err.exception_class == "TypeError"
