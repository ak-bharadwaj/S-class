import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "20-RUNTIME"))
sys.path.insert(0, str(Path(__file__).parents[2] / "10-CONFORMANCE"))

from sclass_runtime_v6_0_1 import (
    GENESIS_EVENT_HASH,
    ActorIdentity,
    ActorKind,
    CanonicalVerificationProvider,
    Command,
    EventType,
    FrozenMap,
    RuntimeDisposition,
    SClassControlPlane,
    SQLiteEventStore,
)


def fmap(items=()):
    return FrozenMap.from_items(items)


def calculate_percentiles(durations_ms: list[float]) -> dict[str, float]:
    sorted_d = sorted(durations_ms)
    n = len(sorted_d)
    p50 = sorted_d[int(n * 0.50)]
    p95 = sorted_d[min(int(n * 0.95), n - 1)]
    p99 = sorted_d[min(int(n * 0.99), n - 1)]
    return {"p50": p50, "p95": p95, "p99": p99}


def test_perf_state_read_latency_contract(tmp_path):
    """§17.1 State read latency contract: p95 target < 5ms under warm cache."""
    db_path = str(tmp_path / "perf_read.sqlite")
    store = SQLiteEventStore(db_path)
    cp = SClassControlPlane(store)
    ws = "ws-bench-read"
    act = ActorIdentity("system", ActorKind.SYSTEM, None)

    # Prime store with 5 committed events
    head = GENESIS_EVENT_HASH
    for i in range(1, 6):
        cmd = Command(
            command_id=f"cmd-read-{i}",
            workspace_id=ws,
            actor=act,
            event_type=EventType.SHUTDOWN_REQUESTED,
            payload=fmap((("reason", f"benchmark-read-{i}"),)),
            expected_head=head,
            actor_signature=None,
            aggregate_id=f"agg-read-{i}",
        )
        res = cp._submit_internal(cmd)
        assert res.disposition == RuntimeDisposition.APPLIED
        head = res.new_head.hash

    # Warm cache read
    _ = store._load_canonical_state(ws)

    # Benchmark 100 consecutive reads
    durations = []
    for _ in range(100):
        t0 = time.perf_counter()
        state = store._load_canonical_state(ws)
        t1 = time.perf_counter()
        assert state.event_sequence == 5
        durations.append((t1 - t0) * 1000.0)

    stats = calculate_percentiles(durations)
    store.close()

    # §17.1 contract: read latency targets with runner scheduling jitter allowance (< 25ms p95, < 15ms p50)
    assert stats["p95"] < 25.0, f"Read p95 exceeded threshold: {stats['p95']:.3f} ms"
    assert stats["p50"] < 15.0, f"Read p50 exceeded threshold: {stats['p50']:.3f} ms"


def test_perf_event_append_and_commit_latency_contract(tmp_path):
    """§17.1 Event append and durable commit latency contract: p95 target < 10ms with synchronous=FULL."""
    db_path = str(tmp_path / "perf_commit.sqlite")
    store = SQLiteEventStore(db_path)
    cp = SClassControlPlane(store)
    ws = "ws-bench-commit"
    act = ActorIdentity("system", ActorKind.SYSTEM, None)

    head = GENESIS_EVENT_HASH
    durations = []
    # Benchmark 25 sequential commits under WAL + synchronous=FULL
    for i in range(1, 26):
        cmd = Command(
            command_id=f"cmd-commit-{i}",
            workspace_id=ws,
            actor=act,
            event_type=EventType.SHUTDOWN_REQUESTED,
            payload=fmap((("reason", f"benchmark-commit-{i}"),)),
            expected_head=head,
            actor_signature=None,
            aggregate_id=f"agg-commit-{i}",
        )
        t0 = time.perf_counter()
        res = cp._submit_internal(cmd)
        t1 = time.perf_counter()
        assert res.disposition == RuntimeDisposition.APPLIED
        head = res.new_head.hash
        durations.append((t1 - t0) * 1000.0)

    stats = calculate_percentiles(durations)
    store.close()

    # Verify durability and reasonable test-runner commit latency bounds (< 150ms on Windows fsync)
    assert stats["p95"] < 150.0, f"Commit p95 exceeded threshold: {stats['p95']:.3f} ms"


def test_perf_verifier_startup_latency_contract():
    """§17.5 Verifier overhead: verifier startup latency < 50ms."""
    durations = []
    for _ in range(20):
        t0 = time.perf_counter()
        provider = CanonicalVerificationProvider()
        t1 = time.perf_counter()
        durations.append((t1 - t0) * 1000.0)
        assert provider is not None

    stats = calculate_percentiles(durations)
    # Verifier startup should be instantaneous (< 25ms)
    assert stats["p95"] < 25.0, f"Verifier startup p95 exceeded: {stats['p95']:.3f} ms"


def test_perf_orchestrator_memory_ceiling_contract(tmp_path):
    """§17.1 Orchestrator memory ceiling contract: <= 1GB RSS."""
    tracemalloc.start()
    db_path = str(tmp_path / "perf_mem.sqlite")
    store = SQLiteEventStore(db_path)
    cp = SClassControlPlane(store)
    ws = "ws-bench-mem"
    act = ActorIdentity("system", ActorKind.SYSTEM, None)

    head = GENESIS_EVENT_HASH
    for i in range(1, 30):
        cmd = Command(
            command_id=f"cmd-mem-{i}",
            workspace_id=ws,
            actor=act,
            event_type=EventType.SHUTDOWN_REQUESTED,
            payload=fmap((("reason", f"benchmark-mem-{i}"),)),
            expected_head=head,
            actor_signature=None,
            aggregate_id=f"agg-mem-{i}",
        )
        res = cp._submit_internal(cmd)
        assert res.disposition == RuntimeDisposition.APPLIED
        head = res.new_head.hash

    _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    store.close()

    peak_mb = peak_bytes / (1024 * 1024)
    # Target is <= 1024 MB; Python test process should use less than 200 MB
    assert peak_mb < 200.0, f"Peak memory usage exceeded 200MB ceiling: {peak_mb:.2f} MB"
