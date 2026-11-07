"""Unit tests for fixture_runner.py.

Verifies:
1. Master SHA-256 pre-verification (mismatch fails closed).
2. Parsing master yields exactly 66 PAIR fixtures and 17 SINGLE rows.
3. Missing evaluator results in NOT_RUN (never PASS).
4. FAKE_ mock evaluator results in MOCK status (never RAN).
5. Block 2 registered evaluators execute and produce RAN-MATCH.
"""
import os
import tempfile
import pytest

from sclass.product.fixture_runner import (
    DEFAULT_MASTER_SHA256,
    EvaluatorRegistry,
    FixtureRecord,
    FixtureRunner,
    parse_master_fixtures,
    verify_master_sha256,
)
from sclass.product.gate import GateOutput, GateState

MASTER_PATH = "/mnt/c/Users/dorni/Downloads/S-CLASS-R32-PACKAGE/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"


def test_master_sha256_verification_and_mismatch():
    """Verify master SHA256 matches expected digest and fails closed on tampering."""
    # Valid check against package copy
    verified = verify_master_sha256(MASTER_PATH, DEFAULT_MASTER_SHA256)
    assert verified == DEFAULT_MASTER_SHA256

    # Tampered expected hash fails closed
    with pytest.raises(ValueError, match="Master hash mismatch"):
        verify_master_sha256(MASTER_PATH, "0000000000000000000000000000000000000000000000000000000000000000")


def test_master_fixture_inventory_counts():
    """Verifies that exactly 66 PAIR fixtures and 17 SINGLE rows are discovered."""
    pairs, singles = parse_master_fixtures(MASTER_PATH, DEFAULT_MASTER_SHA256)

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


def test_missing_evaluator_reports_not_run():
    """Absent evaluator reports NOT_RUN with explicit reason, never PASS."""
    # Empty registry with no evaluators
    empty_reg = EvaluatorRegistry()
    runner = FixtureRunner(registry=empty_reg)

    manifest = runner.run(MASTER_PATH, DEFAULT_MASTER_SHA256)
    counts = manifest["counts"]
    assert counts["ran_match"] == 0
    assert counts["ran_mismatch"] == 0
    assert counts["not_run"] == 132 + 17  # all fixtures unexecuted
    assert counts["not_run"] > 0

    first_res = manifest["results"][0]
    assert first_res["status"] == "NOT_RUN"
    assert "not available on this branch" in first_res["reason"]


def test_mock_evaluator_never_reports_ran():
    """Evaluators prefixed with FAKE_ must report status MOCK, never RAN."""
    reg = EvaluatorRegistry()
    # Register mock with FAKE_ prefix
    reg.register(
        "PD-CH5-007",
        lambda rec: GateOutput(state=GateState.SATISFIED),
        name="FAKE_evaluator_ch5_007",
    )
    runner = FixtureRunner(registry=reg)

    manifest = runner.run(MASTER_PATH, DEFAULT_MASTER_SHA256)
    mock_results = [r for r in manifest["results"] if r["must_id"] == "PD-CH5-007"]
    assert len(mock_results) > 0
    for r in mock_results:
        assert r["status"] == "MOCK"
        assert r["status"] != "RAN-MATCH"
        assert r["status"] != "RAN"


def test_block2_registered_evaluators_execute():
    """Validates that Block 2 evaluators on this branch produce RAN-MATCH."""
    runner = FixtureRunner()  # uses default registry containing CH5 evaluators
    manifest = runner.run(MASTER_PATH, DEFAULT_MASTER_SHA256)

    counts = manifest["counts"]
    assert counts["ran_match"] >= 10  # CH5-T3, T6, T7..T14 etc.
    assert counts["error"] == 0
    assert counts["ran_mismatch"] == 0

    # Specifically check CH5-T7 (gaming) and CH5-T8 (happy)
    ch5_t7 = next(r for r in manifest["results"] if r["fixture_id"] == "CH5-T7")
    ch5_t8 = next(r for r in manifest["results"] if r["fixture_id"] == "CH5-T8")

    assert ch5_t7["status"] == "RAN-MATCH"
    assert ch5_t7["actual_gate_output"] == "MISSING[PD-CH5-007]"

    assert ch5_t8["status"] == "RAN-MATCH"
    assert ch5_t8["actual_gate_output"] == "SATISFIED"
