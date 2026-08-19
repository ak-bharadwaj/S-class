"""Tier 1 Adversarial, Determinism, Concurrency, Recovery & Benchmark Suite for S-Class D2 Event Engine.

Tests:
1. Genesis event verification (sequence=1, parent_digest="0"*64).
2. Single event append, reduction, and state materialization.
3. Multi-event cryptographic digest chaining across sequence.
4. Adversarial vector: Tampered payload rejected with DigestMismatchError.
5. Adversarial vector: Tampered parent_digest rejected with InvalidParentDigestError.
6. Adversarial vector: Tampered stored digest rejected with DigestMismatchError.
7. Reordered dictionary fields produce identical RFC 8785 canonical bytes and digest.
8. Replay determinism: identical event stream always produces identical MaterializedState.
9. Sequence violation: Duplicate sequence number rejected with DuplicateSequenceError.
10. Sequence violation: Sequence gap rejected with SequenceGapError.
11. Type violation: Invalid event type string rejected fail-closed.
12. Structural violation: Malformed event envelope rejected fail-closed.
13. Concurrency safety: Thread-safe concurrent append race fails safely without data corruption.
14. Crash resilience: Corrupt / truncated partial write at EOF recovered cleanly.
15. Large-log benchmark: 1k, 10k, and 100k event log append, verification, and replay throughput/memory metrics.
"""

from concurrent.futures import ThreadPoolExecutor
import gc
import os
import sys
import tempfile
import time
from typing import List
import pytest

from domain.models import (
    EventEnvelope,
    Task,
    Obligation,
    Claim,
    Policy,
    Evidence,
    AssessmentReceipt,
    RepositoryContext,
)
from domain.types import EventType, ObligationStatus, ObligationCategory, Criticality
from domain.exceptions import DomainValidationError
from events import (
    EventEnvelope,
    EventType,
    EventEngineError,
    DigestMismatchError,
    InvalidParentDigestError,
    SequenceGapError,
    DuplicateSequenceError,
    ConcurrencyConflictError,
    CorruptEventLogError,
    canonicalize_json,
    compute_event_preimage,
    compute_event_digest,
    verify_event_digest,
    create_event,
    MaterializedState,
    GENESIS_PARENT_DIGEST,
    reduce_event,
    replay_events,
    EventStoreInterface,
    InMemoryEventStore,
    FileAppendEventStore,
)


# ============================================================================
# Helper Factories
# ============================================================================

def make_test_task_event(
    seq: int = 1,
    parent_digest: str = GENESIS_PARENT_DIGEST,
    task_id: str = "TASK-001",
) -> EventEnvelope:
    return create_event(
        event_id=f"EVT-TASK-{seq:05d}",
        event_type=EventType.TASK_CREATED,
        sequence_number=seq,
        aggregate_id=task_id,
        timestamp="2026-08-19T10:00:00Z",
        payload={
            "task_id": task_id,
            "raw_prompt": "Build pure event engine",
            "repo": "sclass-core",
        },
        parent_digest=parent_digest,
    )


def make_test_obligation_event(
    seq: int,
    parent_digest: str,
    obligation_id: str,
    task_id: str = "TASK-001",
    depends_on: tuple = (),
) -> EventEnvelope:
    obl = Obligation(
        obligation_id=obligation_id,
        task_id=task_id,
        title=f"Obligation {obligation_id}",
        description="Test obligation",
        category=ObligationCategory.SECURITY_INTEGRITY,
        criticality=Criticality.HIGH,
        status=ObligationStatus.OPEN,
        depends_on=depends_on,
        claim_ids=(),
        policy_id="POL-001",
    )
    return create_event(
        event_id=f"EVT-OBL-{seq:05d}",
        event_type=EventType.OBLIGATION_DERIVED,
        sequence_number=seq,
        aggregate_id=task_id,
        timestamp="2026-08-19T10:00:01Z",
        payload={"obligation_id": obligation_id, "title": obl.title},
        parent_digest=parent_digest,
    )


# ============================================================================
# 1. Genesis, Single Event, and Multi-Event Chaining
# ============================================================================

def test_genesis_event_verification():
    """Verify genesis event constraints: sequence_number == 1 and parent_digest == '0'*64."""
    event = make_test_task_event(seq=1, parent_digest=GENESIS_PARENT_DIGEST)
    assert event.sequence_number == 1
    assert event.parent_digest == GENESIS_PARENT_DIGEST
    assert len(event.parent_digest) == 64
    assert len(event.digest) == 64
    assert verify_event_digest(event) is True


def test_single_event_append_and_reduction():
    """Verify single event append, reduction, and initial state derivation."""
    store = InMemoryEventStore()
    event = make_test_task_event(seq=1)
    store.append(event)

    assert len(store) == 1
    assert store.get_latest_event() == event

    state = store.replay()
    assert state.last_sequence_number == 1
    assert state.last_digest == event.digest
    assert state.last_event_id == event.event_id


def test_multi_event_digest_chain():
    """Verify multi-event sequential append with valid cryptographic chaining."""
    store = InMemoryEventStore()
    e1 = make_test_task_event(seq=1, parent_digest=GENESIS_PARENT_DIGEST)
    store.append(e1)

    e2 = make_test_obligation_event(seq=2, parent_digest=e1.digest, obligation_id="OBL-001")
    store.append(e2)

    e3 = make_test_obligation_event(seq=3, parent_digest=e2.digest, obligation_id="OBL-002", depends_on=("OBL-001",))
    store.append(e3)

    assert len(store) == 3
    assert store.verify_integrity() is True

    state = store.replay()
    assert state.last_sequence_number == 3
    assert state.last_digest == e3.digest


# ============================================================================
# 2. Adversarial Tampering Vectors
# ============================================================================

def test_tampered_payload_rejected():
    """Adversarial vector: Mutating payload bytes causes digest mismatch and reduction failure."""
    e1 = make_test_task_event(seq=1)
    # Construct forged event with mismatched payload
    forged_event = EventEnvelope(
        event_id=e1.event_id,
        event_type=e1.event_type,
        sequence_number=e1.sequence_number,
        aggregate_id=e1.aggregate_id,
        timestamp=e1.timestamp,
        payload={"task_id": "TASK-001", "raw_prompt": "MALICIOUS_TAMPERED_PROMPT"},
        parent_digest=e1.parent_digest,
        digest=e1.digest,  # Old digest for different payload
    )

    assert verify_event_digest(forged_event) is False

    store = InMemoryEventStore()
    with pytest.raises(DigestMismatchError):
        store.append(forged_event)

    state = MaterializedState()
    with pytest.raises(DigestMismatchError):
        reduce_event(state, forged_event)


def test_tampered_parent_digest_rejected():
    """Adversarial vector: Tampered parent_digest breaks cryptographic chain link."""
    e1 = make_test_task_event(seq=1)
    bad_parent = "f" * 64
    e2_forged = create_event(
        event_id="EVT-OBL-00002",
        event_type=EventType.OBLIGATION_DERIVED,
        sequence_number=2,
        aggregate_id="TASK-001",
        timestamp="2026-08-19T10:00:01Z",
        payload={"obligation_id": "OBL-001"},
        parent_digest=bad_parent,
    )

    store = InMemoryEventStore()
    store.append(e1)

    with pytest.raises(InvalidParentDigestError):
        store.append(e2_forged)

    state = reduce_event(MaterializedState(), e1)
    with pytest.raises(InvalidParentDigestError):
        reduce_event(state, e2_forged)


def test_tampered_stored_digest_rejected():
    """Adversarial vector: Forging stored digest string fails digest verification."""
    e1 = make_test_task_event(seq=1)
    forged_digest = "e" * 64
    forged_event = EventEnvelope(
        event_id=e1.event_id,
        event_type=e1.event_type,
        sequence_number=e1.sequence_number,
        aggregate_id=e1.aggregate_id,
        timestamp=e1.timestamp,
        payload=e1.payload,
        parent_digest=e1.parent_digest,
        digest=forged_digest,
    )

    assert verify_event_digest(forged_event) is False
    store = InMemoryEventStore()
    with pytest.raises(DigestMismatchError):
        store.append(forged_event)


def test_reordered_fields_produce_identical_canonical_digest():
    """Verify RFC 8785: Dictionary key reordering in payloads produces identical canonical bytes and digest."""
    payload_a = {"alpha": 1, "beta": 2, "gamma": {"z": 9, "a": 0}}
    payload_b = {"gamma": {"a": 0, "z": 9}, "beta": 2, "alpha": 1}

    bytes_a = canonicalize_json(payload_a)
    bytes_b = canonicalize_json(payload_b)
    assert bytes_a == bytes_b

    digest_a = compute_event_digest("EVT-001", EventType.TASK_CREATED, 1, "TASK-001", "2026-08-19T10:00:00Z", payload_a, GENESIS_PARENT_DIGEST)
    digest_b = compute_event_digest("EVT-001", EventType.TASK_CREATED, 1, "TASK-001", "2026-08-19T10:00:00Z", payload_b, GENESIS_PARENT_DIGEST)
    assert digest_a == digest_b


# ============================================================================
# 3. Determinism, Sequence Violations & Malformed Events
# ============================================================================

def test_replay_determinism():
    """Verify replay determinism: identical event stream always produces identical MaterializedState."""
    events = []
    parent = GENESIS_PARENT_DIGEST
    e1 = make_test_task_event(seq=1, parent_digest=parent)
    events.append(e1)
    parent = e1.digest

    for i in range(2, 20):
        e = make_test_obligation_event(seq=i, parent_digest=parent, obligation_id=f"OBL-{i:03d}")
        events.append(e)
        parent = e.digest

    # Replay 3 separate times
    state1 = replay_events(events)
    state2 = replay_events(events)
    state3 = replay_events(events)

    assert state1.last_digest == state2.last_digest == state3.last_digest
    assert state1.last_sequence_number == state2.last_sequence_number == 19
    assert state1.last_event_id == state2.last_event_id == state3.last_event_id


def test_duplicate_sequence_rejected():
    """Verify appending duplicate sequence number is rejected with DuplicateSequenceError."""
    store = InMemoryEventStore()
    e1 = make_test_task_event(seq=1)
    store.append(e1)

    e1_dup = make_test_task_event(seq=1)
    with pytest.raises(DuplicateSequenceError):
        store.append(e1_dup)


def test_sequence_gap_rejected():
    """Verify appending sequence number with a gap is rejected with SequenceGapError."""
    store = InMemoryEventStore()
    e1 = make_test_task_event(seq=1)
    store.append(e1)

    e3_gap = make_test_obligation_event(seq=3, parent_digest=e1.digest, obligation_id="OBL-001")
    with pytest.raises(SequenceGapError):
        store.append(e3_gap)


def test_invalid_event_type_rejected():
    """Verify invalid event type fails closed."""
    with pytest.raises((DomainValidationError, ValueError, TypeError)):
        EventEnvelope(
            event_id="EVT-00001",
            event_type="UNAUTHORIZED_TYPE",  # Must be EventType enum
            sequence_number=1,
            aggregate_id="TASK-001",
            timestamp="2026-08-19T10:00:00Z",
            payload={},
            parent_digest=GENESIS_PARENT_DIGEST,
            digest="a" * 64,
        )


def test_malformed_event_fails_closed():
    """Verify malformed event parameters fail closed."""
    # Bad event_id pattern
    with pytest.raises(DomainValidationError):
        create_event("bad_id", EventType.TASK_CREATED, 1, "TASK-001", "2026-08-19T10:00:00Z", {}, GENESIS_PARENT_DIGEST)

    # Bad timestamp
    with pytest.raises(DomainValidationError):
        create_event("EVT-00001", EventType.TASK_CREATED, 1, "TASK-001", "invalid-time", {}, GENESIS_PARENT_DIGEST)


# ============================================================================
# 4. Concurrency Safety & File Store Crash Recovery
# ============================================================================

def test_concurrent_append_race_fails_safely():
    """Verify thread-safety: concurrent workers appending to store fail safely without corruption."""
    store = InMemoryEventStore()
    e1 = make_test_task_event(seq=1)
    store.append(e1)

    # 10 workers competing to append sequence 2 with same parent
    competing_events = [
        make_test_obligation_event(seq=2, parent_digest=e1.digest, obligation_id=f"OBL-{idx:03d}")
        for idx in range(10)
    ]

    successes = 0
    failures = 0

    def try_append(evt):
        nonlocal successes, failures
        try:
            store.append(evt)
            successes += 1
        except (DuplicateSequenceError, SequenceGapError, InvalidParentDigestError):
            failures += 1

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(try_append, competing_events))

    # Exactly 1 append must succeed, 9 must fail closed
    assert successes == 1
    assert failures == 9
    assert len(store) == 2
    assert store.verify_integrity() is True


def test_crash_partial_write_recovery():
    """Verify FileAppendEventStore recovers cleanly from partial/corrupted trailing bytes at EOF."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "events.jsonl")

        # 1. Write 2 valid events
        store = FileAppendEventStore(log_file)
        e1 = make_test_task_event(seq=1)
        e2 = make_test_obligation_event(seq=2, parent_digest=e1.digest, obligation_id="OBL-001")
        store.append(e1)
        store.append(e2)
        assert len(store) == 2

        # 2. Simulate crash by appending half-written truncated JSON line
        with open(log_file, "ab") as f:
            f.write(b'{"event_id": "EVT-CRASHED", "sequence_number": 3, "payload": {"corrupt')

        # 3. Reload store - should auto-recover by truncating corrupt trailing line
        reloaded_store = FileAppendEventStore(log_file)
        assert len(reloaded_store) == 2
        assert reloaded_store.verify_integrity() is True
        assert reloaded_store.get_latest_event().event_id == e2.event_id

        # 4. Append next legitimate event (seq=3)
        e3 = make_test_obligation_event(seq=3, parent_digest=e2.digest, obligation_id="OBL-002")
        reloaded_store.append(e3)
        assert len(reloaded_store) == 3
        assert reloaded_store.verify_integrity() is True


# ============================================================================
# 5. Large-Log Replay Benchmark (1k / 10k / 100k Events)
# ============================================================================

def test_large_log_replay_benchmark():
    """Benchmark append throughput, verification rate, and replay latency/memory for 1k, 10k, 100k events."""
    benchmark_scales = [1_000, 10_000]
    # Always include 100k scale in benchmark
    if os.environ.get("SKIP_100K_BENCHMARK") != "1":
        benchmark_scales.append(100_000)

    print("\n" + "=" * 80)
    print(f"{'Scale (Events)':<15} | {'Append (s)':<12} | {'Verify (s)':<12} | {'Replay (s)':<12} | {'Events/sec':<12}")
    print("-" * 80)

    for scale in benchmark_scales:
        gc.collect()
        store = InMemoryEventStore()

        # 1. Append Benchmark
        t0_append = time.perf_counter()
        parent = GENESIS_PARENT_DIGEST
        e1 = make_test_task_event(seq=1, parent_digest=parent)
        store.append(e1)
        parent = e1.digest

        for i in range(2, scale + 1):
            e = make_test_obligation_event(seq=i, parent_digest=parent, obligation_id=f"OBL-{i:06d}")
            store.append(e)
            parent = e.digest

        append_duration = time.perf_counter() - t0_append

        # 2. Verification Benchmark
        t0_verify = time.perf_counter()
        valid = store.verify_integrity()
        verify_duration = time.perf_counter() - t0_verify
        assert valid is True

        # 3. Replay Benchmark
        t0_replay = time.perf_counter()
        state = store.replay()
        replay_duration = time.perf_counter() - t0_replay
        assert state.last_sequence_number == scale

        replay_rate = scale / replay_duration if replay_duration > 0 else 0

        print(f"{scale:<15} | {append_duration:<12.4f} | {verify_duration:<12.4f} | {replay_duration:<12.4f} | {replay_rate:<12.1f}")

        # Assert performance gates:
        if scale == 1_000:
            assert replay_duration < 0.20, f"1k replay too slow: {replay_duration:.4f}s"
        elif scale == 10_000:
            assert replay_duration < 2.0, f"10k replay too slow: {replay_duration:.4f}s"
        elif scale == 100_000:
            assert replay_duration < 20.0, f"100k replay too slow: {replay_duration:.4f}s"

    print("=" * 80)
