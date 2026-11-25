"""Tests for TD-17 execution of all 129 FIXTURE-REF-NOT-RUN Master fixtures."""
from __future__ import annotations

import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOLS_DIR = str(REPO_ROOT / "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from master_fixtures import EXPECTED_MASTER_SHA256  # type: ignore
from run_td17_fixtures import run_td17_fixtures  # type: ignore


TD17_ARTIFACT = REPO_ROOT / "product/qualification/td17_fixture_results.json"


def test_td17_artifact_exists_lf_and_covers_all_129_rows() -> None:
    raw = TD17_ARTIFACT.read_bytes()
    assert b"\r" not in raw, "td17_fixture_results.json contains CRLF"
    data = json.loads(raw.decode("utf-8"))
    assert data["master_sha256"] == EXPECTED_MASTER_SHA256
    assert data["total_fnr_rows"] == 129
    assert data["executed_count"] + data["not_executable_count"] == 129
    assert data["executed_count"] == 129
    assert data["not_executable_count"] == 0
    assert data["mismatches"] == []
    assert len(data["results"]) == 129
    for entry in data["results"]:
        assert entry["execution_status"] == "EXECUTED"
        assert entry["all_matched"] is True
        assert entry["subcase_count"] >= 1
        assert entry["master_line"] > 0


def test_td17_deterministic_replay_byte_identical(tmp_path: pathlib.Path) -> None:
    out_file = tmp_path / "td17_replay.json"
    rep = run_td17_fixtures(out_path=out_file)
    assert rep["executed_count"] == 129
    assert rep["mismatches"] == []
    assert out_file.read_bytes() == TD17_ARTIFACT.read_bytes()
