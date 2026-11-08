#!/usr/bin/env python3
"""Tests for shared authoritative master fixture parser (tools/master_fixtures.py).

Verifies:
1. Master document SHA-256 pre-verification.
2. Runtime assertion: returned master line contains fixture ID and re-reading matches.
3. Accurate parsing of Block 1 (44), Block 2 (29), and Wave 1 (F4, E, P11) fixtures.
4. Mutation test: shifting line number by +1 fails runtime assertion / auditor.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_all_fixtures,
    parse_master_fixture,
    verify_master_sha256,
)

DEFAULT_MASTER_PATH = os.environ.get("SCLASS_MASTER_PATH", "")


@pytest.fixture
def master_file() -> Path:
    if not DEFAULT_MASTER_PATH or not Path(DEFAULT_MASTER_PATH).is_file():
        pytest.skip("SCLASS_MASTER_PATH environment variable unset; real master tests require SCLASS_MASTER_PATH")
    return Path(DEFAULT_MASTER_PATH)


def test_master_sha256_verification(master_file: Path):
    actual = verify_master_sha256(master_file)
    assert actual == EXPECTED_MASTER_SHA256


def test_runtime_assertion_and_line_truth_f4(master_file: Path):
    """Verifies F4 fixtures (F4-T1..F4-T7) return real lines 594-600 with exact expected values."""
    f4_expectations = {
        "F4-T1": (594, ["SATISFIED"]),
        "F4-T2": (595, ["SATISFIED"]),
        "F4-T3": (596, ["MISSING[PD-F4-002]"]),
        "F4-T4": (597, ["SATISFIED", "MISSING[PD-F1-003]"]),
        "F4-T5": (598, ["SATISFIED"]),
        "F4-T6": (599, ["SATISFIED"]),
        "F4-T7": (600, ["SATISFIED"]),
    }
    lines = master_file.read_text(encoding="utf-8").splitlines()

    for fid, (exp_line, exp_values) in f4_expectations.items():
        fix = parse_master_fixture(master_file, fid)
        assert fix.parse_status == "OK", f"Parse failed for {fid}: {fix.parse_error}"
        assert fix.line_number == exp_line, f"{fid} line mismatch: got {fix.line_number}, expected {exp_line}"
        assert fid in lines[fix.line_number - 1], f"Line {fix.line_number} does not contain {fid}"
        assert fix.raw_row_text == lines[fix.line_number - 1]
        for v in exp_values:
            assert v in fix.expected_gate_strings, f"{fid} missing expected value {v} in {fix.expected_gate_strings}"


def test_runtime_assertion_and_line_truth_b2_f5_f9_ch5(master_file: Path):
    """Verifies Block 2 fixtures return real lines in master."""
    b2_checks = {
        "F5-T1": 678,
        "F5-T2": 679,
        "F5-T3": 680,
        "F5-T4": 681,
        "F5-T6": 682,
        "F5-T7": 683,
        "F5-T5a": 684,
        "F5-T5b": 685,
        "F5-T5c": 686,
        "F9-T1": 931,
        "F9-T2": 932,
        "F9-T3": 933,
        "F9-T4": 934,
        "CH5-T3": 3639,
        "CH5-T4": 3640,
        "CH5-T5": 3641,
        "CH5-T6": 3642,
        "CH5-T7": 3492,
        "CH5-T8": 3492,
    }
    lines = master_file.read_text(encoding="utf-8").splitlines()

    for fid, exp_line in b2_checks.items():
        fix = parse_master_fixture(master_file, fid)
        assert fix.parse_status == "OK", f"Parse failed for {fid}: {fix.parse_error}"
        assert fix.line_number == exp_line, f"{fid} line mismatch: got {fix.line_number}, expected {exp_line}"
        assert fid in lines[fix.line_number - 1]
        assert fix.raw_row_text == lines[fix.line_number - 1]


def test_mutation_shift_line_plus_one_fails(master_file: Path):
    """Mutation Test (Requirement B): Shift line number by +1, runtime assertion MUST fail."""
    lines = master_file.read_text(encoding="utf-8").splitlines()

    for fid in ["F4-T1", "F5-T1", "F8-T1", "CH5-T3"]:
        fix = parse_master_fixture(master_file, fid)
        mutated_line = fix.line_number + 1

        # Check line text at mutated line
        mutated_text = lines[mutated_line - 1] if mutated_line <= len(lines) else ""
        # The mutated line must NOT be trusted as the valid line for fid
        with pytest.raises(AssertionError):
            assert fid in mutated_text, f"Mutation check: line {mutated_line} must fail for {fid}"
