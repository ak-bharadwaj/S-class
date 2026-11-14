#!/usr/bin/env python3
"""Replay-from-genesis digest equality tool (B04).

Replays recorded canonical event log from genesis state twice in memory
and via SQLiteEventStore persistence replay, asserts deterministic digest equality,
and outputs structured JSON verification evidence.

Supports cross-version artifact comparison via:
    python tools/replay_genesis_digest.py --compare file1.json file2.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import sys
import tempfile
from pathlib import Path

# Ensure 10-CONFORMANCE and 20-RUNTIME are in sys.path
_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONFORMANCE_DIR = _REPO_ROOT / "10-CONFORMANCE"
_RUNTIME_DIR = _REPO_ROOT / "20-RUNTIME"

if str(_CONFORMANCE_DIR) not in sys.path:
    sys.path.insert(0, str(_CONFORMANCE_DIR))
if str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))

import sclass as S
from sclass_runtime_v6_0_1 import SQLiteEventStore
from sclass_semantics_v6_0_1 import (
    COMMIT_SCHEMA_VERSION,
    GENESIS_EVENT_HASH,
    REFERENCE_REDUCER,
    ActorIdentity,
    ActorKind,
    CanonicalEvent,
    CommitRecord,
    CommitState,
    Digest,
    EventType,
    FrozenMap,
    UtcInstant,
    commit_record_digest,
    engineering_state_digest,
    genesis_engineering_state,
)

GOLDEN_VECTORS_PATH = _REPO_ROOT / "tests" / "vectors" / "golden_kernel_vectors.v6.0.1.json"


def load_golden_vectors(path: Path = GOLDEN_VECTORS_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Golden vectors file missing: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def replay_in_memory_from_genesis(event_history: list[dict], workspace_id: str = "default") -> tuple[str, str, str]:
    """Replays event history from genesis using REFERENCE_REDUCER.

    Returns (final_state_digest, final_head_hash, final_state_revision).
    """
    state = genesis_engineering_state(workspace_id)
    actor = ActorIdentity("test-actor-1", ActorKind.HUMAN, None)
    prev_hash = GENESIS_EVENT_HASH

    for entry in event_history:
        seq = entry["sequence"]
        payload = FrozenMap.from_items((("reason", f"deterministic-shutdown-{seq}"),))
        evt = CanonicalEvent.create(
            entry["event_id"],
            entry["commit_id"],
            workspace_id,
            seq,
            EventType.SHUTDOWN_REQUESTED,
            1,
            f"agg-{seq}",
            actor,
            "caus-golden",
            "corr-golden",
            payload,
            prev_hash,
            "policy-v1",
            "sdk-v6.0.1",
            UtcInstant(1000 + seq),
        )
        state = REFERENCE_REDUCER.reduce(state, evt)
        prev_hash = evt.event_hash

    return (
        str(engineering_state_digest(state)),
        str(prev_hash),
        str(state.state_revision),
    )


def replay_sqlite_store_from_genesis(event_history: list[dict], workspace_id: str = "default") -> tuple[str, str]:
    """Appends event history to fresh SQLiteEventStore and replays from genesis.

    Returns (final_state_digest, final_head_hash).
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "replay_genesis.db"
        store = SQLiteEventStore(str(db_path))

        state = genesis_engineering_state(workspace_id)
        actor = ActorIdentity("test-actor-1", ActorKind.HUMAN, None)
        prev_hash = GENESIS_EVENT_HASH

        for entry in event_history:
            seq = entry["sequence"]
            payload = FrozenMap.from_items((("reason", f"deterministic-shutdown-{seq}"),))
            evt = CanonicalEvent.create(
                entry["event_id"],
                entry["commit_id"],
                workspace_id,
                seq,
                EventType.SHUTDOWN_REQUESTED,
                1,
                f"agg-{seq}",
                actor,
                "caus-golden",
                "corr-golden",
                payload,
                prev_hash,
                "policy-v1",
                "sdk-v6.0.1",
                UtcInstant(1000 + seq),
            )
            state = REFERENCE_REDUCER.reduce(state, evt)
            sd = engineering_state_digest(state)
            commit = CommitRecord(
                entry["commit_id"],
                workspace_id,
                (evt.event_id, f"state:{workspace_id}"),
                (evt.event_hash, sd),
                ("event", "state"),
                prev_hash,
                evt.event_hash,
                state.state_revision,
                seq,
                seq,
                COMMIT_SCHEMA_VERSION,
                Digest("sha256:" + "0" * 64),
                CommitState.COMMITTED,
                1,
                1000000000 + seq,
                sd,
            )
            commit = CommitRecord(
                entry["commit_id"],
                workspace_id,
                (evt.event_id, f"state:{workspace_id}"),
                (evt.event_hash, sd),
                ("event", "state"),
                prev_hash,
                evt.event_hash,
                state.state_revision,
                seq,
                seq,
                COMMIT_SCHEMA_VERSION,
                commit_record_digest(commit),
                CommitState.COMMITTED,
                1,
                1000000000 + seq,
                sd,
            )
            store.append_batch((evt,), commit, prev_hash)
            prev_hash = evt.event_hash

        replayed_state = store.replay(workspace_id)
        replayed_digest = str(engineering_state_digest(replayed_state))
        return replayed_digest, str(prev_hash)


def run_dual_replay(workspace_id: str = "default") -> dict:
    golden = load_golden_vectors()
    event_history = golden.get("event_history", [])
    if not event_history:
        raise ValueError("Golden vector event_history is empty")

    expected_final_vec = next(
        v for v in golden.get("state_digest_vectors", [])
        if v.get("name") == "after_10_events_default"
    )
    expected_digest = expected_final_vec["state_digest"]
    expected_head = expected_final_vec["final_head_hash"]

    genesis_state = genesis_engineering_state(workspace_id)
    genesis_digest = str(engineering_state_digest(genesis_state))

    # Run 1
    dig1, head1, rev1 = replay_in_memory_from_genesis(event_history, workspace_id)
    # Run 2
    dig2, head2, rev2 = replay_in_memory_from_genesis(event_history, workspace_id)

    dual_match = (dig1 == dig2) and (head1 == head2) and (rev1 == rev2)
    expected_match = (dig1 == expected_digest) and (head1 == expected_head)

    # SQLite Store Replay
    sqlite_dig, sqlite_head = replay_sqlite_store_from_genesis(event_history, workspace_id)
    sqlite_match = (sqlite_dig == expected_digest) and (sqlite_head == expected_head)

    status = "PASS" if (dual_match and expected_match and sqlite_match) else "FAIL"

    report = {
        "schema": "sclass/replay-genesis-digest/v1",
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "workspace_id": workspace_id,
        "recorded_event_log": str(GOLDEN_VECTORS_PATH.relative_to(_REPO_ROOT)),
        "event_count": len(event_history),
        "genesis_state_digest": genesis_digest,
        "expected_final_state_digest": expected_digest,
        "expected_final_head_hash": expected_head,
        "run1": {
            "final_state_revision": rev1,
            "final_state_digest": dig1,
            "final_head_hash": head1,
        },
        "run2": {
            "final_state_revision": rev2,
            "final_state_digest": dig2,
            "final_head_hash": head2,
        },
        "sqlite_store_replay": {
            "final_state_digest": sqlite_dig,
            "final_head_hash": sqlite_head,
        },
        "dual_replay_digest_match": dual_match,
        "expected_golden_digest_match": expected_match,
        "sqlite_store_replay_digest_match": sqlite_match,
        "status": status,
    }

    if status != "PASS":
        raise RuntimeError(f"Replay validation failed: {report}")

    return report


def compare_reports(path1: Path, path2: Path) -> int:
    """Compares two replay evidence reports across Python versions."""
    print(f"Comparing replay reports:")
    print(f"  Artifact 1: {path1}")
    print(f"  Artifact 2: {path2}")

    with open(path1, "r", encoding="utf-8") as f1, open(path2, "r", encoding="utf-8") as f2:
        r1 = json.load(f1)
        r2 = json.load(f2)

    py1 = f"{r1.get('python_implementation', 'Python')} {r1.get('python_version', '?')}"
    py2 = f"{r2.get('python_implementation', 'Python')} {r2.get('python_version', '?')}"

    dig1 = r1["run1"]["final_state_digest"]
    dig2 = r2["run1"]["final_state_digest"]
    head1 = r1["run1"]["final_head_hash"]
    head2 = r2["run1"]["final_head_hash"]

    status1 = r1.get("status")
    status2 = r2.get("status")

    print("\n" + "=" * 80)
    print("CROSS-PYTHON REPLAY-FROM-GENESIS DIGEST COMPARISON")
    print("=" * 80)
    print(f"{'Field':<28} | {'Artifact 1 (' + py1 + ')':<28} | {'Artifact 2 (' + py2 + ')'}")
    print("-" * 80)
    print(f"{'Status':<28} | {str(status1):<28} | {str(status2)}")
    print(f"{'Dual Run 1==2 Match':<28} | {str(r1.get('dual_replay_digest_match')):<28} | {str(r2.get('dual_replay_digest_match'))}")
    print(f"{'Golden Vector Match':<28} | {str(r1.get('expected_golden_digest_match')):<28} | {str(r2.get('expected_golden_digest_match'))}")
    print(f"{'SQLite Store Match':<28} | {str(r1.get('sqlite_store_replay_digest_match')):<28} | {str(r2.get('sqlite_store_replay_digest_match'))}")
    print(f"{'State Digest Run 1':<28} | {dig1:<28} | {dig2}")
    print(f"{'Head Hash Run 1':<28} | {head1:<28} | {head2}")
    print("-" * 80)

    mismatches = []
    if status1 != "PASS" or status2 != "PASS":
        mismatches.append(f"Status non-PASS: {status1} vs {status2}")
    if dig1 != dig2:
        mismatches.append(f"Final state digest mismatch: {dig1} != {dig2}")
    if head1 != head2:
        mismatches.append(f"Final head hash mismatch: {head1} != {head2}")
    if not r1.get("dual_replay_digest_match") or not r2.get("dual_replay_digest_match"):
        mismatches.append("Dual replay equality failed in one or both artifacts")

    if mismatches:
        print("\nFAIL: Replay artifacts mismatch or contain errors:")
        for m in mismatches:
            print(f"  - {m}")
        return 1

    print(f"\nPASS: Replay-from-genesis digest equality verified across {py1} and {py2}.")
    print(f"Identical state digest: {dig1}")
    print(f"Identical head hash:    {head1}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay-from-genesis digest equality tool (B04)")
    parser.add_argument("--output", "-o", type=Path, help="Path to write JSON replay report")
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("FILE1", "FILE2"), help="Compare two replay report JSON files")
    parser.add_argument("--workspace", default="default", help="Workspace ID for replay (default: 'default')")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode")

    args = parser.parse_args()

    if args.compare:
        return compare_reports(args.compare[0], args.compare[1])

    report = run_dual_replay(workspace_id=args.workspace)

    if not args.quiet:
        print("Replay-from-genesis completed successfully:")
        print(f"  Python:        {report['python_implementation']} {report['python_version']} ({report['platform']})")
        print(f"  Events:        {report['event_count']} canonical events replayed from genesis")
        print(f"  Genesis state: {report['genesis_state_digest']}")
        print(f"  Run 1 digest:  {report['run1']['final_state_digest']}")
        print(f"  Run 2 digest:  {report['run2']['final_state_digest']}")
        print(f"  Dual match:    {report['dual_replay_digest_match']}")
        print(f"  Golden match:  {report['expected_golden_digest_match']}")
        print(f"  Store match:   {report['sqlite_store_replay_digest_match']}")
        print(f"  Status:        {report['status']}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        if not args.quiet:
            print(f"Wrote report to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
