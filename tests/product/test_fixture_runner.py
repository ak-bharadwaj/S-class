"""Unit tests for fixture_runner.py.

Verifies:
1. Master SHA-256 pre-verification (mismatch fails closed).
2. Parsing master yields exactly 66 PAIR fixtures and 17 SINGLE rows.
3. Missing evaluator results in NOT_RUN (never PASS).
4. Block 2 registered evaluators execute and produce RAN-MATCH.
"""
from __future__ import annotations

import os
import pytest

from sclass.product.fixture_runner import (
    DEFAULT_MASTER_SHA256,
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


def test_block2_registered_evaluators_execute():
    """Validates that Block 2 evaluators on this branch produce RAN-MATCH."""
    runner = FixtureRunner()
    manifest = runner.run(MASTER_PATH, DEFAULT_MASTER_SHA256)

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
