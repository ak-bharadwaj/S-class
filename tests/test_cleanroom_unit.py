"""
S-Class EOS V11.2 - Gate 2 Phase 5: Clean-Room Engine Unit Test Suite.
Verifies the independent CleanRoomPropertyEngine against the frozen contract.
Tests strategy generation, boundary bias, monotonic shrinking, determinism, filtering,
replay mechanics, hard-capped shrink budget, AST regex generation, anchor semantics (^, $, \b),
exact Unicode category satisfiability (isolated single codepoints), and regex parser compat layer.
Supported Python Versions: 3.10-3.13.
"""

import pytest
import re
import math
import random
import unicodedata
from typing import List, Dict, Any, Tuple
from benchmark.hypothesis_parity.observation import StrategySpec, ObservationRecord, ReplayOutcome, compute_size
from benchmark.hypothesis_parity.cleanroom_engine import CleanRoomPropertyEngine, _generate_random_value, _generate_boundary_candidates
from benchmark.hypothesis_parity.differential_oracle import IndependentDifferentialOracle, _validate_value_against_spec
from benchmark.hypothesis_parity.regex_parser_compat import parse_regex_ast, inspect_regex_anchors
from benchmark.hypothesis_parity.unicode_indexer import sample_codepoint, find_valid_codepoint_intervals


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
# 4. Authoritative Shrink Budget Hard Cap (<= 500)
# =============================================================================

def test_cleanroom_shrink_evaluation_budget_hard_cap():
    """
    Regression test designed to trigger excessive shrinking steps.
    Verifies that the shrink budget halts evaluations authoritatively and strictly enforces <= 500 calls.
    """
    specs = {
        "huge_list": StrategySpec(
            strategy_type="lists",
            params={
                "elements": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 100000}),
                "min_size": 30,
                "max_size": 50
            }
        )
    }

    def complex_multistep_property(huge_list: List[int]) -> bool:
        assert len(huge_list) < 25 or sum(huge_list) < 1000, "Too long and too large"
        return True

    obs = CleanRoomPropertyEngine.run_campaign(specs, complex_multistep_property, max_examples=20, seed=42, enable_shrinking=True)
    assert obs.verdict == "FAIL"
    assert obs.shrink_evaluations is not None
    assert obs.shrink_evaluations <= 500, f"Budget limit violated: {obs.shrink_evaluations} > 500"

    valid, violations = IndependentDifferentialOracle.validate_observation(obs, complex_multistep_property, specs)
    assert valid is True
    assert len(violations) == 0


# =============================================================================
# 5. Filter Exhaustion Error Handling
# =============================================================================

def test_cleanroom_filter_exhaustion_returns_structured_error():
    """
    Pathological / impossible filter predicate.
    Verifies that filter exhaustion is caught and returned as structured ObservationRecord(verdict='ERROR', exception_class='FilterExhaustion').
    """
    specs = {
        "impossible_val": StrategySpec(
            strategy_type="integers",
            params={"min_value": 0, "max_value": 100},
            filter_fn=lambda x: x > 500 and x < -500
        )
    }

    obs = CleanRoomPropertyEngine.run_campaign(specs, lambda x: True, max_examples=10, seed=42)
    assert obs.verdict == "ERROR"
    assert obs.exception_class == "FilterExhaustion"
    assert obs.shrunk_counterexample is None


# =============================================================================
# 6. Regex AST Generation & Anchor Semantics (^, $, \b)
# =============================================================================

def test_cleanroom_regex_anchors_and_boundary_semantics():
    """
    Validates generic AST regex generation with strict start (^) and end ($) anchor handling under fullmatch=False.
    """
    rng = random.Random(42)
    test_patterns = [
        (r"^abc$", False),          # Exact start and end anchored
        (r"^foo", False),           # Start anchored only
        (r"bar$", False),           # End anchored only
        (r"\bword\b", False),       # Word boundary
        (r"[A-Z]{2,4}-\d{3,5}", True),
        (r"GET|POST|PUT|DELETE", True)
    ]

    for pat, fullmatch in test_patterns:
        spec = StrategySpec(strategy_type="from_regex", params={"pattern": pat, "fullmatch": fullmatch})
        for _ in range(15):
            val = _generate_random_value(spec, rng)
            assert isinstance(val, str)
            if fullmatch:
                assert re.fullmatch(pat, val), f"Fullmatch regex failed for {pat}: '{val}'"
            else:
                assert re.search(pat, val), f"Substring regex search failed for {pat}: '{val}'"
                if pat.startswith("^"):
                    assert val.startswith("foo") or val == "abc", f"Start anchor violated: {val}"
                if pat.endswith("$"):
                    assert val.endswith("bar") or val == "abc", f"End anchor violated: {val}"


# =============================================================================
# 7. Exact Unicode Category Satisfiability & Isolated Codepoint Tests
# =============================================================================

def test_cleanroom_isolated_single_codepoint_generation():
    """
    Validates that the exact interval indexer successfully finds and generates an isolated single valid codepoint
    even when it is the ONLY valid character in the entire requested range.
    """
    # 1. Greek Capital Omega (937, \u03A9) is the only uppercase letter in range [937, 937]
    spec_omega = StrategySpec(
        strategy_type="characters",
        params={"whitelist_categories": ["Lu"], "min_codepoint": 937, "max_codepoint": 937}
    )
    rng = random.Random(42)
    val_omega = _generate_random_value(spec_omega, rng)
    assert ord(val_omega) == 937
    assert unicodedata.category(val_omega) == "Lu"

    # 2. Euro Sign (0x20AC, 8364, category 'Sc') in range [8364, 8364]
    spec_euro = StrategySpec(
        strategy_type="characters",
        params={"whitelist_categories": ["Sc"], "min_codepoint": 8364, "max_codepoint": 8364}
    )
    val_euro = _generate_random_value(spec_euro, rng)
    assert ord(val_euro) == 8364
    assert unicodedata.category(val_euro) == "Sc"


def test_cleanroom_character_fail_closed_on_impossible_constraints():
    """
    Validates that impossible Unicode category/bounds combinations fail closed with FilterExhaustion
    and NEVER emit invalid fallback values outside StrategySpec.
    """
    # 1. Lu (Uppercase) within lowercase ASCII range [97, 122]
    impossible_lu = {
        "c": StrategySpec(strategy_type="characters", params={"whitelist_categories": ["Lu"], "min_codepoint": 97, "max_codepoint": 122})
    }
    obs1 = CleanRoomPropertyEngine.run_campaign(impossible_lu, lambda c: True, max_examples=10, seed=42)
    assert obs1.verdict == "ERROR"
    assert obs1.exception_class == "FilterExhaustion"

    # 2. Empty intersection: whitelist and blacklist same category
    empty_intersection = {
        "c": StrategySpec(strategy_type="characters", params={"whitelist_categories": ["Nd"], "blacklist_categories": ["Nd"]})
    }
    obs2 = CleanRoomPropertyEngine.run_campaign(empty_intersection, lambda c: True, max_examples=10, seed=42)
    assert obs2.verdict == "ERROR"
    assert obs2.exception_class == "FilterExhaustion"


# =============================================================================
# 8. Regex Parser Compatibility Layer Tests
# =============================================================================

def test_regex_parser_compat_layer():
    """
    Explicitly verifies that regex_parser_compat accurately parses grammar ASTs
    and extracts anchors across all supported patterns on Python 3.10-3.13.
    """
    # 1. Literal & Range
    ast1 = parse_regex_ast(r"[a-z0-9]+")
    assert len(ast1) > 0

    # 2. Anchors
    ast_anchored = parse_regex_ast(r"^test$")
    has_start, has_end, has_sb, has_eb = inspect_regex_anchors(ast_anchored)
    assert has_start is True
    assert has_end is True

    # 3. Word Boundaries
    ast_boundary = parse_regex_ast(r"\btoken\b")
    has_start, has_end, has_sb, has_eb = inspect_regex_anchors(ast_boundary)
    assert has_sb is True
    assert has_eb is True

    # 4. Branching anchors
    ast_branch = parse_regex_ast(r"^(GET|POST)$")
    has_start, has_end, _, _ = inspect_regex_anchors(ast_branch)
    assert has_start is True
    assert has_end is True

    # 5. Invalid regex raises ValueError
    with pytest.raises(ValueError):
        parse_regex_ast(r"[unclosed_bracket")


# =============================================================================
# 9. Email Contract & Deterministic Replay
# =============================================================================

def test_cleanroom_email_validity_contract():
    """Validates email contract format."""
    rng = random.Random(42)
    spec_email = StrategySpec(strategy_type="emails")

    email_regex = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    for _ in range(30):
        email = _generate_random_value(spec_email, rng)
        assert email_regex.match(email), f"Invalid email generated: {email}"
        user, domain = email.split("@")
        assert len(user) >= 1
        assert "." in domain


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


def test_cleanroom_replay_outcome_integrity():
    """Validates structured replay outcomes for reproduced, corrupted, and error cases."""
    def target_prop(x: int) -> bool:
        assert x < 5, "x >= 5"
        return True

    outcome_clean = CleanRoomPropertyEngine.replay_case(target_prop, {"x": 10}, expected_exception_class="AssertionError")
    assert outcome_clean.reproduced_failure is True
    assert outcome_clean.unexpected_error is False

    outcome_pass = CleanRoomPropertyEngine.replay_case(target_prop, {"x": 2}, expected_exception_class="AssertionError")
    assert outcome_pass.reproduced_failure is False
    assert outcome_pass.unexpected_error is False

    def buggy_prop(x: int) -> bool:
        return x / "invalid_str"

    outcome_err = CleanRoomPropertyEngine.replay_case(buggy_prop, {"x": 10}, expected_exception_class="AssertionError")
    assert outcome_err.reproduced_failure is False
    assert outcome_err.unexpected_error is True
    assert outcome_err.exception_class == "TypeError"
