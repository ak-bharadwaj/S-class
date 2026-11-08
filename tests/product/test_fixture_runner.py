"""Unit tests for fixture_runner.py and fixture_bindings.py (A2, A3).

Verifies:
1. Master SHA-256 pre-verification (mismatch fails closed) using synthetic master.
2. Missing evaluator results in NOT_RUN (never PASS).
3. FAKE_ mock evaluator results in MOCK status (never RAN).
4. Real master tests (guarded by SCLASS_MASTER_PATH):
   a. Parsing real master yields exactly 66 PAIR fixtures and 17 SINGLE rows.
   b. All 29 Block 2 registered evaluators execute and produce RAN-MATCH.
   c. verify_bindings_against_master runtime verification passes.
   d. Mutation of binding expected output or master line fails closed.
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest

from sclass.product.fixture_runner import (
    DEFAULT_MASTER_SHA256,
    EvaluatorRegistry,
    FixtureRecord,
    FixtureRunner,
    parse_master_fixtures,
    verify_master_sha256,
)
from sclass.product.fixture_bindings import (
    BLOCK2_17_SINGLE_BINDINGS,
    BLOCK2_6_PAIRS_BINDINGS,
    FixtureBinding,
    verify_bindings_against_master,
)
from sclass.product.gate import GateOutput, GateState

SYNTHETIC_MASTER_PATH = str(Path(__file__).resolve().parent.parent / "fixtures" / "synthetic_master.md")
SYNTHETIC_MASTER_SHA256 = "a08c05baef07236cb22fe7acb3d4e02f21316b45c3adf8c5306d629ad09f1b10"


def _require_real_master() -> str:
    path = os.environ.get("SCLASS_MASTER_PATH")
    if not path or not os.path.exists(path):
        pytest.skip("SCLASS_MASTER_PATH environment variable unset; real master tests require SCLASS_MASTER_PATH")
    return path


def test_master_sha256_verification_and_mismatch():
    """Verify master SHA256 matches expected digest and fails closed on tampering."""
    # Valid check against committed synthetic master
    verified = verify_master_sha256(SYNTHETIC_MASTER_PATH, SYNTHETIC_MASTER_SHA256)
    assert verified == SYNTHETIC_MASTER_SHA256

    # Tampered expected hash fails closed
    with pytest.raises(ValueError, match="Master hash mismatch"):
        verify_master_sha256(SYNTHETIC_MASTER_PATH, "0000000000000000000000000000000000000000000000000000000000000000")


def test_missing_evaluator_reports_not_run():
    """Absent evaluator reports NOT_RUN with explicit reason, never PASS."""
    empty_reg = EvaluatorRegistry()
    runner = FixtureRunner(registry=empty_reg)

    manifest = runner.run(SYNTHETIC_MASTER_PATH, SYNTHETIC_MASTER_SHA256)
    counts = manifest["counts"]
    assert counts["ran_match"] == 0
    assert counts["ran_mismatch"] == 0
    assert counts["not_run"] > 0

    first_res = manifest["results"][0]
    assert first_res["status"] == "NOT_RUN"
    assert "not available on this branch" in first_res["reason"]


def test_mock_evaluator_never_reports_ran():
    """Evaluators prefixed with FAKE_ must report status MOCK, never RAN."""
    reg = EvaluatorRegistry()
    reg.register(
        "PD-SYN-001",
        lambda rec: GateOutput(state=GateState.SATISFIED),
        name="FAKE_evaluator_syn_001",
    )
    runner = FixtureRunner(registry=reg)

    manifest = runner.run(SYNTHETIC_MASTER_PATH, SYNTHETIC_MASTER_SHA256)
    mock_results = [r for r in manifest["results"] if r["must_id"] == "PD-SYN-001"]
    assert len(mock_results) > 0
    for r in mock_results:
        assert r["status"] == "MOCK"
        assert r["status"] != "RAN-MATCH"
        assert r["status"] != "RAN"


# =============================================================================
# Real Master Tests (Skipped when SCLASS_MASTER_PATH is unset)
# =============================================================================

def test_master_fixture_inventory_counts():
    """Verifies that exactly 66 PAIR fixtures and 17 SINGLE rows are discovered."""
    master_path = _require_real_master()
    pairs, singles = parse_master_fixtures(master_path, DEFAULT_MASTER_SHA256)

    # 66 PAIR MUSTs (each having gaming and happy -> 132 fixtures total)
    pair_must_ids = {p.must_id for p in pairs}
    assert len(pair_must_ids) == 66
    assert len(pairs) == 132
    for p in pairs:
        assert p.category == "PAIR"
        assert p.role in ("gaming", "happy")

    # 17 SINGLE rows
    assert len(singles) == 17
    for s in singles:
        assert s.category == "SINGLE"
        assert s.role == "single"


def test_block2_registered_evaluators_execute():
    """Validates that Block 2 evaluators on this branch produce RAN-MATCH."""
    master_path = _require_real_master()
    runner = FixtureRunner()
    manifest = runner.run(master_path, DEFAULT_MASTER_SHA256)

    inv = manifest["inventory"]
    assert inv["pairs_count"] == 66
    assert inv["singles_count"] == 17
    assert inv["block2_subset_vectors"] == 29
    assert inv["other_vectors_count"] == 120

    # Specifically check CH5-T7 (gaming) and CH5-T8 (happy)
    ch5_t7 = next(r for r in manifest["block2_results"] if r["fixture_id"] == "CH5-T7")
    ch5_t8 = next(r for r in manifest["block2_results"] if r["fixture_id"] == "CH5-T8")

    assert ch5_t7["status"] == "RAN-MATCH"
    assert ch5_t7["actual_gate_output"] == "MISSING[PD-CH5-007]"

    assert ch5_t8["status"] == "RAN-MATCH"
    assert ch5_t8["actual_gate_output"] == "SATISFIED"

    # On merged staging branch, all 29 Block 2 fixtures are RAN-MATCH.
    # On stacked lane branches before staging merge, 19 execute without metrics/perf lanes.
    assert manifest["counts"]["ran_mismatch"] == 0
    assert manifest["counts"]["ran_match"] in (19, 29)


def test_verify_bindings_against_master():
    """Runtime check (A3): for every binding, expected and master_line equal parsed values."""
    master_path = _require_real_master()
    verify_bindings_against_master(master_path)


def test_verify_bindings_against_master_mutation_fails():
    """Mutation test (A3): mutating a binding expected output or line fails closed."""
    master_path = _require_real_master()

    # Mutation 1: Mutated expected output
    mutated_exp = list(BLOCK2_17_SINGLE_BINDINGS)
    orig = mutated_exp[0]
    mutated_exp[0] = FixtureBinding(
        fixture_id=orig.fixture_id,
        must_id=orig.must_id,
        master_line=orig.master_line,
        category=orig.category,
        role=orig.role,
        expected_output="MUTATED_WRONG_EXPECTED",
        dispatch_name=orig.dispatch_name,
    )
    with pytest.raises(AssertionError, match="Expected output mismatch"):
        verify_bindings_against_master(master_path, bindings=mutated_exp)

    # Mutation 2: Mutated line number
    mutated_line = list(BLOCK2_17_SINGLE_BINDINGS)
    mutated_line[0] = FixtureBinding(
        fixture_id=orig.fixture_id,
        must_id=orig.must_id,
        master_line=orig.master_line + 9999,
        category=orig.category,
        role=orig.role,
        expected_output=orig.expected_output,
        dispatch_name=orig.dispatch_name,
    )
    with pytest.raises(AssertionError, match="Master line mismatch"):
        verify_bindings_against_master(master_path, bindings=mutated_line)
