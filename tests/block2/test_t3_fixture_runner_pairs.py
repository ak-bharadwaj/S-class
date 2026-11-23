"""Tests for T3: 66/66 pairs through registry.evaluate and no synthetic PD-CH4-010 injection."""
from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import fixture_runner  # type: ignore


def _assert_no_synthetic_injection(source_text: str) -> None:
    assert "8813" not in source_text, "Synthetic master_line 8813 found"
    assert "Ensure PD-CH4-010 pair is represented" not in source_text


def test_no_synthetic_ch4_010_injection_in_fixture_runner() -> None:
    src = (REPO_ROOT / "tools/fixture_runner.py").read_text(encoding="utf-8")
    _assert_no_synthetic_injection(src)


def test_fail_before_synthetic_injection_caught() -> None:
    fake_src = "# Ensure PD-CH4-010 pair is represented\nmaster_line = 8813\n"
    try:
        _assert_no_synthetic_injection(fake_src)
        raise AssertionError("Should fail on synthetic injection")
    except AssertionError:
        pass


def test_all_66_pairs_pass_through_registry() -> None:
    master = REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
    summary = fixture_runner.run_pairs_via_registry(str(master))
    assert summary["total_pairs"] == 66
    assert summary["total_vectors"] == 132
    assert summary["passed"] == 132
    assert summary["failed"] == 0
    ch4 = [r for r in summary["rows"] if r["must_id"] == "PD-CH4-010"]
    assert len(ch4) == 2
    assert {r["fixture_id"]: r["master_line"] for r in ch4} == {
        "CH4-T11": 10527,
        "CH4-T12": 10540,
    }
