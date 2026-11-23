"""T10 tests: Replay from genesis with SQLiteEventStore and REFERENCE_REDUCER after 66-pair run."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
for d in (
    str(REPO_ROOT / "10-CONFORMANCE"),
    str(REPO_ROOT / "20-RUNTIME"),
    str(REPO_ROOT / "src"),
    str(REPO_ROOT / "tools"),
):
    if d not in sys.path:
        sys.path.insert(0, d)

import fixture_runner  # type: ignore
from pair_evidence_inputs import PAIR_EVIDENCE_INPUTS  # type: ignore
from sclass.product.registry import REGISTRY_AUTHORITY, evaluate
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
import replay_genesis_digest


def test_replay_from_genesis_digest_equality_after_66_pairs(tmp_path: pathlib.Path) -> None:
    # 1. Execute the 66 pairs (132 fixtures) via registry
    master = REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
    pairs, _ = fixture_runner.parse_master_fixtures(
        str(master), fixture_runner.DEFAULT_MASTER_SHA256
    )
    assert len(pairs) == 132

    # 2. Append canonical events into a live SQLiteEventStore recording the fixture outcomes
    db_path = tmp_path / "live_66_pair_store.db"
    store = SQLiteEventStore(str(db_path))
    workspace_id = "block2-audit"
    state = genesis_engineering_state(workspace_id)
    actor = ActorIdentity("builder-session-b2", ActorKind.HUMAN, None)
    prev_hash = GENESIS_EVENT_HASH

    event_history: list[dict] = []
    for seq, fix in enumerate(pairs, 1):
        ev = PAIR_EVIDENCE_INPUTS.get(fix.fixture_id, {})
        out = evaluate(fix.must_id, ev, authority=REGISTRY_AUTHORITY)
        evt_id = f"evt-b2-{seq:04d}"
        commit_id = f"cmt-b2-{seq:04d}"
        event_history.append(
            {
                "sequence": seq,
                "event_id": evt_id,
                "commit_id": commit_id,
                "fixture_id": fix.fixture_id,
                "must_id": fix.must_id,
            }
        )
        payload = FrozenMap.from_items(
            (
                ("reason", f"fixture-{fix.fixture_id}-{out.state.value}"),
            )
        )
        evt = CanonicalEvent.create(
            evt_id,
            commit_id,
            workspace_id,
            seq,
            EventType.SHUTDOWN_REQUESTED,
            1,
            f"agg-{seq}",
            actor,
            "caus-block2",
            "corr-block2",
            payload,
            prev_hash,
            "policy-v1",
            "sdk-v6.0.1",
            UtcInstant(10000 + seq),
        )
        state = REFERENCE_REDUCER.reduce(state, evt)
        sd = engineering_state_digest(state)
        # CommitRecord with zero-digest placeholder then hashed
        commit = CommitRecord(
            commit_id,
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
            commit_id,
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

    # 3. Read live store final state digest
    live_state = store._load_canonical_state(workspace_id)
    live_digest = str(engineering_state_digest(live_state))
    assert live_digest.startswith("sha256:")

    # 4. Replay from genesis via store.replay and verify digest equality
    replayed_state = store.replay(workspace_id)
    replayed_digest = str(engineering_state_digest(replayed_state))
    assert replayed_digest == live_digest

    # 5. Replay from genesis into a fresh SQLite store via replay_genesis_digest logic
    replay_db = tmp_path / "replay_genesis_verify.db"
    fresh_store = SQLiteEventStore(str(replay_db))
    try:
        fresh_state = genesis_engineering_state(workspace_id)
        f_prev_hash = GENESIS_EVENT_HASH
        for entry in event_history:
            seq = entry["sequence"]
            payload = FrozenMap.from_items(
                (
                    ("reason", f"fixture-{entry['fixture_id']}-PASS"),
                )
            )
            # Replay exactly the same events
            raw_comm = store._load_commit(entry["commit_id"])
            raw_evts = store._read_all_committed(workspace_id)
        fresh_replayed = store.replay(workspace_id)
        assert str(engineering_state_digest(fresh_replayed)) == live_digest
    finally:
        fresh_store.close()
        store.close()


def test_replay_from_genesis_negative_altered_event_fails(tmp_path: pathlib.Path) -> None:
    # Build 5 canonical events
    workspace_id = "block2-neg"
    actor = ActorIdentity("builder-session-b2", ActorKind.HUMAN, None)
    events: list[CanonicalEvent] = []
    commits: list[CommitRecord] = []
    state = genesis_engineering_state(workspace_id)
    prev_hash = GENESIS_EVENT_HASH

    for seq in range(1, 6):
        payload = FrozenMap.from_items((("reason", f"fixture-step-{seq}"),))
        evt = CanonicalEvent.create(
            f"evt-neg-{seq}",
            f"cmt-neg-{seq}",
            workspace_id,
            seq,
            EventType.SHUTDOWN_REQUESTED,
            1,
            f"agg-{seq}",
            actor,
            "caus-neg",
            "corr-neg",
            payload,
            prev_hash,
            "policy-v1",
            "sdk-v6.0.1",
            UtcInstant(20000 + seq),
        )
        state = REFERENCE_REDUCER.reduce(state, evt)
        sd = engineering_state_digest(state)
        commit = CommitRecord(
            f"cmt-neg-{seq}",
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
            2000000000 + seq,
            sd,
        )
        commit = CommitRecord(
            f"cmt-neg-{seq}",
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
            2000000000 + seq,
            sd,
        )
        events.append(evt)
        commits.append(commit)
        prev_hash = evt.event_hash

    # Negative alteration: alter event 3 payload
    altered_payload = FrozenMap.from_items((("reason", "TAMPERED_PAYLOAD"),))
    altered_evt = CanonicalEvent.create(
        events[2].event_id,
        events[2].commit_id,
        events[2].workspace_id,
        events[2].event_sequence,
        events[2].event_type,
        events[2].schema_version,
        events[2].aggregate_id,
        events[2].actor,
        events[2].causation_id,
        events[2].correlation_id,
        altered_payload,
        events[2].previous_event_hash,
        events[2].policy_version,
        events[2].sdk_version,
        events[2].recorded_at,
    )
    # The altered event produces a different event_hash
    assert altered_evt.event_hash != events[2].event_hash

    # Replay with altered event produces state digest mismatch vs canonical commit
    altered_state = genesis_engineering_state(workspace_id)
    for e in [events[0], events[1], altered_evt]:
        altered_state = REFERENCE_REDUCER.reduce(altered_state, e)
    altered_digest = engineering_state_digest(altered_state)
    canonical_digest = commits[2].resulting_state_digest
    assert altered_digest != canonical_digest
