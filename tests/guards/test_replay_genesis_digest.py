"""Guard Test Suite: Replay-from-genesis digest equality verification (B04).

Asserts:
1. Deterministic in-memory reduction from genesis across repeated replay runs.
2. Exact state digest and head hash equivalence to frozen golden vectors.
3. Deterministic SQLiteEventStore persistence replay from genesis.
4. CLI replay evidence generation and cross-run/cross-version report comparison.
5. Strict failure on mutated digest or header in comparison mode.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFORMANCE_DIR = _REPO_ROOT / "10-CONFORMANCE"
_RUNTIME_DIR = _REPO_ROOT / "20-RUNTIME"
_TOOLS_DIR = _REPO_ROOT / "tools"

if str(_CONFORMANCE_DIR) not in sys.path:
    sys.path.insert(0, str(_CONFORMANCE_DIR))
if str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import replay_genesis_digest as R


def test_replay_genesis_in_memory_determinism():
    golden = R.load_golden_vectors()
    event_history = golden["event_history"]

    dig1, head1, rev1 = R.replay_in_memory_from_genesis(event_history, "default")
    dig2, head2, rev2 = R.replay_in_memory_from_genesis(event_history, "default")

    assert dig1 == dig2, f"Dual replay digest mismatch: {dig1} != {dig2}"
    assert head1 == head2, f"Dual replay head hash mismatch: {head1} != {head2}"
    assert rev1 == rev2, f"Dual replay state revision mismatch: {rev1} != {rev2}"

    expected_final_vec = next(
        v for v in golden["state_digest_vectors"]
        if v["name"] == "after_10_events_default"
    )
    assert dig1 == expected_final_vec["state_digest"]
    assert head1 == expected_final_vec["final_head_hash"]


def test_replay_genesis_sqlite_store_determinism():
    golden = R.load_golden_vectors()
    event_history = golden["event_history"]

    store_dig, store_head = R.replay_sqlite_store_from_genesis(event_history, "default")

    expected_final_vec = next(
        v for v in golden["state_digest_vectors"]
        if v["name"] == "after_10_events_default"
    )
    assert store_dig == expected_final_vec["state_digest"]
    assert store_head == expected_final_vec["final_head_hash"]


def test_replay_genesis_tool_report(tmp_path):
    report_file = tmp_path / "replay_test.json"
    report = R.run_dual_replay(workspace_id="default")
    assert report["status"] == "PASS"
    assert report["dual_replay_digest_match"] is True
    assert report["expected_golden_digest_match"] is True
    assert report["sqlite_store_replay_digest_match"] is True

    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    loaded = json.loads(report_file.read_text(encoding="utf-8"))
    assert loaded["schema"] == "sclass/replay-genesis-digest/v1"
    assert loaded["event_count"] == 10


def test_replay_genesis_cli_compare(tmp_path):
    report1 = R.run_dual_replay(workspace_id="default")
    report2 = dict(report1)
    report2["python_version"] = "3.99.0"

    p1 = tmp_path / "rep1.json"
    p2 = tmp_path / "rep2.json"
    p1.write_text(json.dumps(report1), encoding="utf-8")
    p2.write_text(json.dumps(report2), encoding="utf-8")

    # Matching reports should exit 0
    ret = R.compare_reports(p1, p2)
    assert ret == 0

    # Mutated digest report should fail with non-zero exit code
    mutated = dict(report2)
    mutated["run1"] = dict(mutated["run1"])
    mutated["run1"]["final_state_digest"] = "sha256:" + "0" * 64
    p_mut = tmp_path / "rep_mut.json"
    p_mut.write_text(json.dumps(mutated), encoding="utf-8")

    ret_fail = R.compare_reports(p1, p_mut)
    assert ret_fail != 0
