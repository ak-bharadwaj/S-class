"""Stage S1 Exit Gate: Persistence & Durability Engine Verification.

Authoritative requirements:
- CAS appends under single, batch, and concurrent contention.
- Hash chain integrity: verify_chain() handles VALID, BROKEN_HASH, GAP, UNREADABLE.
- Replay equivalence: genesis replay == incremental reduction == checkpoint+suffix replay == projection.
- Checkpoint creation, verification, and corruption detection.
- Crash consistency / atomic restart simulation under fault injection.
"""
from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

_conformance_dir = Path(__file__).resolve().parents[2] / "10-CONFORMANCE"
_runtime_dir = Path(__file__).resolve().parents[2] / "20-RUNTIME"
if str(_conformance_dir) not in sys.path:
    sys.path.insert(0, str(_conformance_dir))
if str(_runtime_dir) not in sys.path:
    sys.path.insert(0, str(_runtime_dir))

from sclass_runtime_v6_0_1 import (
    AppendResult,
    CrashHarness,
    SQLiteEventStore,
)
from sclass_semantics_v6_0_1 import (
    COMMIT_SCHEMA_VERSION,
    GENESIS_EVENT_HASH,
    REFERENCE_REDUCER,
    ActorIdentity,
    ActorKind,
    CanonicalEvent,
    ChainStatus,
    CheckpointRef,
    CommitRecord,
    CommitState,
    Digest,
    EngineeringState,
    EventType,
    FrozenMap,
    UtcInstant,
    commit_record_digest,
    engineering_state_digest,
    genesis_engineering_state,
)


def fmap(items=()):
    return FrozenMap.from_items(items)


def _test_actor() -> ActorIdentity:

    return ActorIdentity("s1-verifier", ActorKind.SYSTEM, None)


def _make_event(
    seq: int,
    prev_hash: Digest,
    commit_id: str,
    event_type: EventType = EventType.SHUTDOWN_REQUESTED,
    payload: dict | None = None,
    ws: str = "w",
) -> CanonicalEvent:
    if payload is None:
        payload = {"reason": f"stage-s1-step-{seq}"}
    return CanonicalEvent.create(
        f"evt-{seq}",
        commit_id,
        ws,
        seq,
        event_type,
        1,
        "system",
        _test_actor(),
        f"causation-{seq}",
        f"correlation-{seq}",
        fmap(payload.items()),
        prev_hash,
        "pol-s1",
        "6.0.1",
        UtcInstant(1_000_000 * seq),
    )


def _make_commit(
    events: tuple[CanonicalEvent, ...],
    derived_state: EngineeringState,
    commit_id: str,
    ws: str = "w",
) -> CommitRecord:
    sd = engineering_state_digest(derived_state)
    event_participants = tuple(e.event_id for e in events) + (f"state:{ws}",)
    event_hashes = tuple(e.event_hash for e in events) + (sd,)
    event_types = tuple("event" for _ in events) + ("state",)
    provisional = CommitRecord(
        commit_id,
        ws,
        event_participants,
        event_hashes,
        event_types,
        events[0].previous_event_hash,
        events[-1].event_hash,
        derived_state.state_revision,
        events[0].event_sequence,
        events[-1].event_sequence,
        COMMIT_SCHEMA_VERSION,
        Digest("sha256:" + "0" * 64),
        CommitState.COMMITTED,
        1,
        1_000_000_000,
        sd,
    )
    return replace(provisional, commit_digest=commit_record_digest(provisional))


# -----------------------------------------------------------------------------
# 1. CAS appends under single, batch, and concurrent contention
# -----------------------------------------------------------------------------
def test_cas_appends_single_batch_and_contention(tmp_path):
    """S1 CAS: Single append, batch atomic append, and concurrent writer contention."""
    db_path = str(tmp_path / "cas_s1.sqlite")
    store = SQLiteEventStore(db_path)
    state = genesis_engineering_state("w")

    # 1. Single append succeeds with expected_head_hash = GENESIS_EVENT_HASH
    e1 = _make_event(1, GENESIS_EVENT_HASH, "commit-1")
    s1 = REFERENCE_REDUCER.reduce(state, e1)
    c1 = _make_commit((e1,), s1, "commit-1")
    res1, head1 = store.append(e1, c1, GENESIS_EVENT_HASH)
    assert res1 is AppendResult.APPENDED
    assert head1.sequence == 1
    assert head1.hash == e1.event_hash

    # Stale CAS attempt fails with HEAD_MISMATCH
    e1_stale = _make_event(2, e1.event_hash, "commit-stale")
    s1_stale = REFERENCE_REDUCER.reduce(s1, e1_stale)
    c1_stale = _make_commit((e1_stale,), s1_stale, "commit-stale")
    res_stale, head_stale = store.append(e1_stale, c1_stale, GENESIS_EVENT_HASH)  # Using GENESIS instead of e1.event_hash
    assert res_stale is AppendResult.HEAD_MISMATCH
    assert head_stale is None
    assert store.head("w").sequence == 1

    # 2. Batch append: 3 events in sequence (seq 2, 3, 4) in one atomic transaction
    e2 = _make_event(2, e1.event_hash, "commit-batch")
    e3 = _make_event(3, e2.event_hash, "commit-batch")
    e4 = _make_event(4, e3.event_hash, "commit-batch")
    s4 = REFERENCE_REDUCER.replay(s1, (e2, e3, e4))
    c_batch = _make_commit((e2, e3, e4), s4, "commit-batch")

    # Batch append with wrong head fails
    res_bad_batch, _ = store.append_batch((e2, e3, e4), c_batch, GENESIS_EVENT_HASH)
    assert res_bad_batch is AppendResult.HEAD_MISMATCH
    assert store.head("w").sequence == 1

    # Batch append with correct head succeeds
    res_batch, head_batch = store.append_batch((e2, e3, e4), c_batch, e1.event_hash)
    assert res_batch is AppendResult.APPENDED
    assert head_batch.sequence == 4
    assert head_batch.hash == e4.event_hash
    assert store.head("w").sequence == 4

    store.close()

    # 3. Concurrent contention: 8 threads concurrently attempt to append event seq 5
    # with expected_head_hash = e4.event_hash. Exactly 1 thread must win; 7 must receive HEAD_MISMATCH.
    e5_candidates = [
        _make_event(5, e4.event_hash, f"commit-race-{i}")
        for i in range(8)
    ]
    commits = [
        _make_commit((e5_candidates[i],), REFERENCE_REDUCER.reduce(s4, e5_candidates[i]), f"commit-race-{i}")
        for i in range(8)
    ]

    def try_append(worker_idx: int):
        local_store = SQLiteEventStore(db_path)
        try:
            return local_store.append(e5_candidates[worker_idx], commits[worker_idx], e4.event_hash)
        finally:
            local_store.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(try_append, i) for i in range(8)]
        results = [f.result() for f in futures]

    successes = [r for r in results if r[0] is AppendResult.APPENDED]
    mismatches = [r for r in results if r[0] is AppendResult.HEAD_MISMATCH]
    assert len(successes) == 1, f"Expected exactly 1 CAS winner, got {len(successes)}"
    assert len(mismatches) == 7, f"Expected 7 CAS losers, got {len(mismatches)}"

    # Verify database state integrity
    final_store = SQLiteEventStore(db_path)
    assert final_store.head("w").sequence == 5
    assert final_store.verify_chain("w", 1, 5) is ChainStatus.VALID
    final_store.close()


def test_cas_appends_multiprocess_contention(tmp_path):
    """S1 CAS: Separate OS process writer contention via subprocesses."""
    import json
    import subprocess

    db_path = str(tmp_path / "cas_mp.sqlite")
    store = SQLiteEventStore(db_path, busy_timeout=5000)
    state = genesis_engineering_state("w")
    e1 = _make_event(1, GENESIS_EVENT_HASH, "commit-init")
    s1 = REFERENCE_REDUCER.reduce(state, e1)
    c1 = _make_commit((e1,), s1, "commit-init")
    assert store.append(e1, c1, GENESIS_EVENT_HASH)[0] is AppendResult.APPENDED
    store.close()

    worker_script = tmp_path / "mp_worker.py"
    worker_script.write_text(
        "import sys, dataclasses, json\n"
        "from pathlib import Path\n"
        f"root = Path(r'{_conformance_dir.parent}').resolve()\n"
        "sys.path.extend([str(root / '10-CONFORMANCE'), str(root / '20-RUNTIME')])\n"
        "from sclass_semantics_v6_0_1 import *\n"
        "from sclass_runtime_v6_0_1 import SQLiteEventStore, AppendResult\n\n"
        "db_p, wid, head_h = sys.argv[1], sys.argv[2], Digest(sys.argv[3])\n"
        "store = SQLiteEventStore(db_p, busy_timeout=5000)\n"
        "actor = ActorIdentity('mp-verifier', ActorKind.SYSTEM, None)\n"
        "e2 = CanonicalEvent.create(\n"
        "    f'evt-2-p{wid}', f'c2-p{wid}', 'w', 2, EventType.SHUTDOWN_REQUESTED, 1,\n"
        "    'system', actor, f'cause-{wid}', f'corr-{wid}',\n"
        "    FrozenMap.from_items((('reason', f'mp-{wid}'),)),\n"
        "    head_h, 'pol-s1', '6.0.1', UtcInstant(2000000)\n"
        ")\n"
        "s0 = genesis_engineering_state('w')\n"
        "e_first = store._read_all_committed('w')[0]\n"
        "s_first = REFERENCE_REDUCER.reduce(s0, e_first)\n"
        "s2 = REFERENCE_REDUCER.reduce(s_first, e2)\n"
        "sd = engineering_state_digest(s2)\n"
        "c2 = CommitRecord(\n"
        "    f'c2-p{wid}', 'w', (f'evt-2-p{wid}', 'state:w'), (e2.event_hash, sd),\n"
        "    ('event', 'state'), head_h, e2.event_hash, s2.state_revision, 2, 2,\n"
        "    COMMIT_SCHEMA_VERSION, Digest('sha256:' + '0'*64), CommitState.COMMITTED, 1, 1000000000, sd\n"
        ")\n"
        "c2 = dataclasses.replace(c2, commit_digest=commit_record_digest(c2))\n"
        "res, _ = store.append(e2, c2, head_h)\n"
        "store.close()\n"
        "print(json.dumps({'worker': wid, 'result': res.name}))\n",
        encoding="utf-8",
    )

    procs = [
        subprocess.Popen(
            [sys.executable, str(worker_script), db_path, str(i), str(e1.event_hash)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(4)
    ]
    results = []
    for p in procs:
        out, err = p.communicate(timeout=15)
        assert p.returncode == 0, f"Worker process failed: {err}"
        results.append(json.loads(out.strip())["result"])

    assert results.count("APPENDED") == 1, f"Expected 1 winner, got {results}"
    assert results.count("HEAD_MISMATCH") == 3, f"Expected 3 losers, got {results}"

    final_store = SQLiteEventStore(db_path)
    assert final_store.head("w").sequence == 2
    assert final_store.verify_chain("w", 1, 2) is ChainStatus.VALID
    final_store.close()


# -----------------------------------------------------------------------------
# 2. Hash chain integrity: verify_chain() handles VALID, BROKEN_HASH, GAP
# -----------------------------------------------------------------------------
def test_hash_chain_integrity_validation(tmp_path):
    """S1 Chain Integrity: verify_chain() handles VALID, BROKEN_HASH, GAP, UNREADABLE."""
    db_path = str(tmp_path / "chain.sqlite")
    store = SQLiteEventStore(db_path)
    state = genesis_engineering_state("w")

    # Empty store -> UNREADABLE
    assert store.verify_chain("w", 1, 1) is ChainStatus.UNREADABLE

    # Populate 5 valid sequential events
    events = []
    prev_hash = GENESIS_EVENT_HASH
    for seq in range(1, 6):
        ev = _make_event(seq, prev_hash, f"c-{seq}")
        state = REFERENCE_REDUCER.reduce(state, ev)
        commit = _make_commit((ev,), state, f"c-{seq}")
        assert store.append(ev, commit, prev_hash)[0] is AppendResult.APPENDED
        events.append(ev)
        prev_hash = ev.event_hash

    # 1. VALID: full range and subranges
    assert store.verify_chain("w", 1, 5) is ChainStatus.VALID
    assert store.verify_chain("w", 1, 3) is ChainStatus.VALID
    assert store.verify_chain("w", 3, 5) is ChainStatus.VALID
    store.close()

    # 2. BROKEN_HASH: tamper event_hash of event 3 in database
    import shutil
    tamper_db_path = str(tmp_path / "chain_tamper.sqlite")
    shutil.copyfile(db_path, tamper_db_path)
    tamper_store = SQLiteEventStore(tamper_db_path)
    # Corrupt the event_hash in canonical_events table
    tamper_store._db.execute(
        "UPDATE canonical_events SET event_hash=? WHERE event_sequence=3",
        ("sha256:" + "f" * 64,),
    )
    assert tamper_store.verify_chain("w", 1, 5) is ChainStatus.BROKEN_HASH

    # Tamper event 1 alone in subrange [1, 1]
    tamper_store._db.execute(
        "UPDATE canonical_events SET event_hash=? WHERE event_sequence=1",
        ("sha256:" + "e" * 64,),
    )
    assert tamper_store.verify_chain("w", 1, 1) is ChainStatus.BROKEN_HASH
    tamper_store.close()

    # 3. GAP: delete event 3 in database creating a sequence gap (1, 2, 4, 5)
    gap_db_path = str(tmp_path / "chain_gap.sqlite")
    shutil.copyfile(db_path, gap_db_path)
    gap_store = SQLiteEventStore(gap_db_path)
    gap_store._db.execute("DELETE FROM canonical_events WHERE event_sequence=3")
    gap_store._db.execute("DELETE FROM canonical_commits WHERE event_sequence_start=3")
    # Verifying range [1, 5] across the gap must return ChainStatus.GAP
    assert gap_store.verify_chain("w", 1, 5) is ChainStatus.GAP
    # Verifying range [2, 4] with missing 3 must return ChainStatus.GAP
    assert gap_store.verify_chain("w", 2, 4) is ChainStatus.GAP
    gap_store.close()

    # Gap at genesis sequence: missing event 1 (2, 3, 4, 5 present)
    gap_genesis_path = str(tmp_path / "chain_gap_genesis.sqlite")
    shutil.copyfile(db_path, gap_genesis_path)
    gap_gen_store = SQLiteEventStore(gap_genesis_path)
    gap_gen_store._db.execute("DELETE FROM canonical_events WHERE event_sequence=1")
    gap_gen_store._db.execute("DELETE FROM canonical_commits WHERE event_sequence_start=1")
    assert gap_gen_store.verify_chain("w", 2, 5) is ChainStatus.GAP
    gap_gen_store.close()


# -----------------------------------------------------------------------------
# 3. Replay equivalence: genesis replay == incremental reduction == checkpoint+suffix replay
# -----------------------------------------------------------------------------
def test_replay_equivalence_genesis_incremental_checkpoint(tmp_path):
    """S1 Replay: Genesis replay produces identical state_digest to incremental and checkpoint suffix."""
    db_path = str(tmp_path / "replay_equiv.sqlite")
    store = SQLiteEventStore(db_path)
    state = genesis_engineering_state("w")

    # Build 6 sequential events across 3 commits
    # Commit 1: seq 1, 2
    e1 = _make_event(1, GENESIS_EVENT_HASH, "commit-A")
    e2 = _make_event(2, e1.event_hash, "commit-A")
    s2 = REFERENCE_REDUCER.replay(state, (e1, e2))
    cA = _make_commit((e1, e2), s2, "commit-A")
    store.append_batch((e1, e2), cA, GENESIS_EVENT_HASH)

    # Commit 2: seq 3, 4
    e3 = _make_event(3, e2.event_hash, "commit-B")
    e4 = _make_event(4, e3.event_hash, "commit-B")
    s4 = REFERENCE_REDUCER.replay(s2, (e3, e4))
    cB = _make_commit((e3, e4), s4, "commit-B")
    store.append_batch((e3, e4), cB, e2.event_hash)

    # Create a checkpoint at commit 2 (seq 4)
    ref_cp4 = CheckpointRef("cp-4", 4, s4.state_digest, "commit-B")
    store.checkpoint(ref_cp4, s4)

    # Commit 3: seq 5, 6
    e5 = _make_event(5, e4.event_hash, "commit-C")
    e6 = _make_event(6, e5.event_hash, "commit-C")
    s6 = REFERENCE_REDUCER.replay(s4, (e5, e6))
    cC = _make_commit((e5, e6), s6, "commit-C")
    store.append_batch((e5, e6), cC, e4.event_hash)

    # Equivalence:
    # 1. Incremental step-by-step state
    incremental_digest = engineering_state_digest(s6)

    # 2. Durable projection state loaded directly
    projection_state = store._load_canonical_state("w")
    projection_digest = engineering_state_digest(projection_state)

    # 3. Full genesis replay (replay from seq 1)
    genesis_replay_state = store.replay("w")
    genesis_replay_digest = engineering_state_digest(genesis_replay_state)

    # 4. Checkpoint + suffix replay (restore cp-4 + replay seq 5, 6)
    cp_replay_state = store.replay("w", from_checkpoint=ref_cp4)
    cp_replay_digest = engineering_state_digest(cp_replay_state)

    assert incremental_digest == projection_digest
    assert genesis_replay_digest == projection_digest
    assert cp_replay_digest == projection_digest

    store.close()


# -----------------------------------------------------------------------------
# 4. Checkpoint creation, verification, and corruption detection
# -----------------------------------------------------------------------------
def test_checkpoint_creation_restoration_and_corruption_detection(tmp_path):
    """S1 Checkpoint: Creation, verified restore, and tamper/corruption rejection."""
    db_path = str(tmp_path / "checkpoint_s1.sqlite")
    store = SQLiteEventStore(db_path)
    state = genesis_engineering_state("w")

    # Cannot checkpoint genesis state (seq 0)
    ref_genesis = CheckpointRef("cp-0", 0, state.state_digest, "c-0")
    with pytest.raises(ValueError, match="genesis"):
        store.checkpoint(ref_genesis, state)

    # Append 2 events
    e1 = _make_event(1, GENESIS_EVENT_HASH, "c1")
    e2 = _make_event(2, e1.event_hash, "c1")
    s2 = REFERENCE_REDUCER.replay(state, (e1, e2))
    c1 = _make_commit((e1, e2), s2, "c1")
    store.append_batch((e1, e2), c1, GENESIS_EVENT_HASH)

    # Create valid checkpoint
    ref = CheckpointRef("cp-1", 2, s2.state_digest, "c1")
    store.checkpoint(ref, s2)

    # Restore checkpoint and verify bit-for-bit equivalence
    restored = store.restore("cp-1")
    assert restored.workspace_id == "w"
    assert restored.event_sequence == 2
    assert restored.state_digest == s2.state_digest
    assert engineering_state_digest(restored) == engineering_state_digest(s2)

    # Non-existent checkpoint raises KeyError
    with pytest.raises(KeyError):
        store.restore("cp-nonexistent")

    # Corruption detection 1: Tampered state_blob in checkpoints table
    store._db.execute(
        "UPDATE checkpoints SET state_blob=substr(state_blob, 1, length(state_blob)-2) WHERE checkpoint_id='cp-1'"
    )
    with pytest.raises(ValueError):
        store.restore("cp-1")

    # Restore valid blob and tamper state_digest
    store._db.execute("DELETE FROM checkpoints WHERE checkpoint_id='cp-1'")
    store.checkpoint(ref, s2)
    store._db.execute(
        "UPDATE checkpoints SET state_digest=? WHERE checkpoint_id='cp-1'",
        ("sha256:" + "d" * 64,),
    )
    with pytest.raises(ValueError, match="integrity mismatch"):
        store.restore("cp-1")

    # Tampering event_sequence in checkpoint
    store._db.execute("DELETE FROM checkpoints WHERE checkpoint_id='cp-1'")
    store.checkpoint(ref, s2)
    store._db.execute(
        "UPDATE checkpoints SET event_sequence=99 WHERE checkpoint_id='cp-1'"
    )
    with pytest.raises(ValueError, match="mismatch"):
        store.restore("cp-1")

    store.close()


# -----------------------------------------------------------------------------
# 5. Authoritative Real-Process CrashHarness covering K1–K6
# -----------------------------------------------------------------------------
def _spawn_s1_crash_child(
    db_path: str,
    stage: str,
    events_code: str,
    tmp_path: Path,
) -> subprocess.CompletedProcess:
    child_py = tmp_path / f"child_{stage}.py"
    child_py.write_text(
        f"""import os, sys
sys.path.insert(0, {str(_conformance_dir)!r})
sys.path.insert(0, {str(_runtime_dir)!r})
from sclass_runtime_v6_0_1 import SQLiteEventStore
import sclass_semantics_v6_0_1 as S

def kill(s):
    if s == {stage!r}:
        os._exit(137)

store = SQLiteEventStore({str(db_path)!r}, fault_injector=kill)
{events_code}
store.close()
""",
        encoding="utf-8",
    )
    return subprocess.run([sys.executable, str(child_py)], capture_output=True, text=True, check=False)


@pytest.mark.parametrize("stage", CrashHarness.STAGES)
def test_s1_exit_crash_consistency_k1_to_k6_real_process_death(tmp_path, stage):
    """S1 Crash Consistency: Real OS process death at all K1-K6 points leaves exact prefix predicted by oracle."""
    db_path = str(tmp_path / f"crash_real_{stage}.sqlite")
    state0 = genesis_engineering_state("w")
    e1 = _make_event(1, GENESIS_EVENT_HASH, "commit-crash")
    s1 = REFERENCE_REDUCER.reduce(state0, e1)
    s1_digest = engineering_state_digest(s1)

    # Single-event append script executed in child process
    child_script = """
st0 = S.genesis_engineering_state("w")
ev = S.CanonicalEvent.create(
    "evt-1", "commit-crash", "w", 1, S.EventType.SHUTDOWN_REQUESTED, 1,
    "system", S.ActorIdentity("s1-verifier", S.ActorKind.SYSTEM, None),
    "causation-1", "correlation-1", S.FrozenMap.from_items((("reason", "stage-s1-step-1"),)),
    S.GENESIS_EVENT_HASH, "pol-s1", "6.0.1", S.UtcInstant(1000000)
)
s1 = S.REFERENCE_REDUCER.reduce(st0, ev)
sd = S.engineering_state_digest(s1)
cm = S.CommitRecord(
    "commit-crash", "w", ("evt-1", "state:w"), (ev.event_hash, sd),
    ("event", "state"), S.GENESIS_EVENT_HASH, ev.event_hash, s1.state_revision,
    1, 1, S.COMMIT_SCHEMA_VERSION, S.Digest("sha256:" + "0" * 64),
    S.CommitState.COMMITTED, 1, 1000000000, sd
)
cm = S.replace(cm, commit_digest=S.commit_record_digest(cm))
store.append(ev, cm, S.GENESIS_EVENT_HASH)
"""

    # 1. Real subprocess execution
    proc = _spawn_s1_crash_child(db_path, stage, child_script, tmp_path)
    assert proc.returncode == 137, f"Process did not terminate with 137 at {stage}: {proc.stderr}"

    # 2. Executable Expected Durable-Prefix Oracle
    oracle = CrashHarness.expected_durable_prefix_oracle(
        stage=stage,
        previous_head_sequence=0,
        previous_head_hash=GENESIS_EVENT_HASH,
        previous_state_digest=engineering_state_digest(state0),
        attempted_events_count=1,
        attempted_new_head_sequence=1,
        attempted_new_head_hash=e1.event_hash,
        attempted_new_state_digest=s1_digest,
        previous_commit_count=0,
        previous_event_count=0,
    )

    # 3. Post-crash reopen & verify atomic state against oracle
    reopened = SQLiteEventStore(db_path)
    head = reopened.head("w")
    assert head.sequence == oracle.expected_sequence
    assert head.hash == oracle.expected_head_hash

    # Table row counts: zero partial leakage on K1-K5, exact commit on K6
    commits_count = reopened._db.execute("SELECT count(*) FROM canonical_commits WHERE workspace_id='w'").fetchone()[0]
    events_count = reopened._db.execute("SELECT count(*) FROM canonical_events WHERE workspace_id='w'").fetchone()[0]
    proj_count = reopened._db.execute("SELECT count(*) FROM canonical_projection WHERE workspace_id='w'").fetchone()[0]
    assert commits_count == oracle.expected_commit_count
    assert events_count == oracle.expected_event_count
    assert proj_count == (1 if oracle.committed else 0)

    # State digest equivalence
    loaded_state = reopened._load_canonical_state("w")
    assert loaded_state.event_sequence == oracle.expected_sequence
    assert loaded_state.event_head_hash == oracle.expected_head_hash
    assert engineering_state_digest(loaded_state) == oracle.expected_state_digest

    # 4. Prove Replay Equivalence: replay(genesis, history) == _load_canonical_state() == oracle
    replayed_state = reopened.replay("w")
    assert replayed_state.event_sequence == oracle.expected_sequence
    assert replayed_state.event_head_hash == oracle.expected_head_hash
    assert engineering_state_digest(replayed_state) == oracle.expected_state_digest

    if oracle.committed:
        assert reopened.verify_chain("w", 1, 1) is ChainStatus.VALID

    # 5. Operational Continuity: subsequent clean append must succeed without corruption
    next_seq = head.sequence + 1
    next_prev_hash = head.hash
    e_next = _make_event(next_seq, next_prev_hash, "commit-continuity")
    s_next = REFERENCE_REDUCER.reduce(loaded_state, e_next)
    c_next = _make_commit((e_next,), s_next, "commit-continuity")

    res, new_head = reopened.append(e_next, c_next, next_prev_hash)
    assert res is AppendResult.APPENDED
    assert new_head.sequence == next_seq
    assert new_head.hash == e_next.event_hash
    assert reopened.verify_chain("w", 1, next_seq) is ChainStatus.VALID
    reopened.close()


@pytest.mark.parametrize("stage", CrashHarness.STAGES)
def test_s1_exit_k1_to_k6_batch_append_crash_and_replay_equivalence(tmp_path, stage):
    """S1 Crash Consistency: Real OS process death during multi-event atomic batch append."""
    db_path = str(tmp_path / f"crash_batch_{stage}.sqlite")
    state0 = genesis_engineering_state("w")
    e1 = _make_event(1, GENESIS_EVENT_HASH, "commit-b")
    e2 = _make_event(2, e1.event_hash, "commit-b")
    e3 = _make_event(3, e2.event_hash, "commit-b")
    batch = (e1, e2, e3)
    s3 = REFERENCE_REDUCER.replay(state0, batch)
    s3_digest = engineering_state_digest(s3)

    child_script = """
st0 = S.genesis_engineering_state("w")
ev1 = S.CanonicalEvent.create(
    "evt-1", "commit-b", "w", 1, S.EventType.SHUTDOWN_REQUESTED, 1,
    "system", S.ActorIdentity("s1-verifier", S.ActorKind.SYSTEM, None),
    "causation-1", "correlation-1", S.FrozenMap.from_items((("reason", "stage-s1-step-1"),)),
    S.GENESIS_EVENT_HASH, "pol-s1", "6.0.1", S.UtcInstant(1000000)
)
ev2 = S.CanonicalEvent.create(
    "evt-2", "commit-b", "w", 2, S.EventType.SHUTDOWN_REQUESTED, 1,
    "system", S.ActorIdentity("s1-verifier", S.ActorKind.SYSTEM, None),
    "causation-2", "correlation-2", S.FrozenMap.from_items((("reason", "stage-s1-step-2"),)),
    ev1.event_hash, "pol-s1", "6.0.1", S.UtcInstant(2000000)
)
ev3 = S.CanonicalEvent.create(
    "evt-3", "commit-b", "w", 3, S.EventType.SHUTDOWN_REQUESTED, 1,
    "system", S.ActorIdentity("s1-verifier", S.ActorKind.SYSTEM, None),
    "causation-3", "correlation-3", S.FrozenMap.from_items((("reason", "stage-s1-step-3"),)),
    ev2.event_hash, "pol-s1", "6.0.1", S.UtcInstant(3000000)
)
batch = (ev1, ev2, ev3)
s3 = S.REFERENCE_REDUCER.replay(st0, batch)
sd = S.engineering_state_digest(s3)
participants = tuple(e.event_id for e in batch) + ("state:w",)
hashes = tuple(e.event_hash for e in batch) + (sd,)
types = ("event", "event", "event", "state")
cm = S.CommitRecord(
    "commit-b", "w", participants, hashes, types,
    S.GENESIS_EVENT_HASH, ev3.event_hash, s3.state_revision,
    1, 3, S.COMMIT_SCHEMA_VERSION, S.Digest("sha256:" + "0" * 64),
    S.CommitState.COMMITTED, 1, 1000000000, sd
)
cm = S.replace(cm, commit_digest=S.commit_record_digest(cm))
store.append_batch(batch, cm, S.GENESIS_EVENT_HASH)
"""

    # 1. Real subprocess execution
    proc = _spawn_s1_crash_child(db_path, stage, child_script, tmp_path)
    assert proc.returncode == 137, f"Process did not terminate with 137 at {stage}: {proc.stderr}"

    # 2. Executable Oracle
    oracle = CrashHarness.expected_durable_prefix_oracle(
        stage=stage,
        previous_head_sequence=0,
        previous_head_hash=GENESIS_EVENT_HASH,
        previous_state_digest=engineering_state_digest(state0),
        attempted_events_count=3,
        attempted_new_head_sequence=3,
        attempted_new_head_hash=e3.event_hash,
        attempted_new_state_digest=s3_digest,
        previous_commit_count=0,
        previous_event_count=0,
    )

    # 3. Post-crash validation
    reopened = SQLiteEventStore(db_path)
    head = reopened.head("w")
    assert head.sequence == oracle.expected_sequence
    assert head.hash == oracle.expected_head_hash

    # Atomic batch invariant: zero events leaked on pre-commit crash
    commits_count = reopened._db.execute("SELECT count(*) FROM canonical_commits WHERE workspace_id='w'").fetchone()[0]
    events_count = reopened._db.execute("SELECT count(*) FROM canonical_events WHERE workspace_id='w'").fetchone()[0]
    assert commits_count == oracle.expected_commit_count
    assert events_count == oracle.expected_event_count

    loaded_state = reopened._load_canonical_state("w")
    assert engineering_state_digest(loaded_state) == oracle.expected_state_digest

    # 4. Replay Equivalence
    replayed_state = reopened.replay("w")
    assert engineering_state_digest(replayed_state) == oracle.expected_state_digest
    assert replayed_state.event_sequence == oracle.expected_sequence

    if oracle.committed:
        assert reopened.verify_chain("w", 1, 3) is ChainStatus.VALID

    # 5. Subsequent append continuity
    next_seq = head.sequence + 1
    e_next = _make_event(next_seq, head.hash, "commit-b-next")
    s_next = REFERENCE_REDUCER.reduce(loaded_state, e_next)
    c_next = _make_commit((e_next,), s_next, "commit-b-next")
    res, new_head = reopened.append(e_next, c_next, head.hash)
    assert res is AppendResult.APPENDED
    assert new_head.sequence == next_seq
    assert reopened.verify_chain("w", 1, next_seq) is ChainStatus.VALID
    reopened.close()


def test_crash_consistency_atomic_restart_simulation(tmp_path):
    """Backward compatibility alias verifying atomic restart under real process death."""
    for stage in CrashHarness.STAGES:
        sub_tmp = tmp_path / f"alias_{stage}"
        sub_tmp.mkdir(parents=True, exist_ok=True)
        test_s1_exit_crash_consistency_k1_to_k6_real_process_death(sub_tmp, stage)

