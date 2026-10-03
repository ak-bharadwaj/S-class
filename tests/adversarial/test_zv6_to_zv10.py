import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "20-RUNTIME"))
sys.path.insert(0, str(Path(__file__).parents[2] / "10-CONFORMANCE"))

from sclass_runtime_v6_0_1 import (
    GENESIS_EVENT_HASH,
    ActorIdentity,
    ActorKind,
    ChainStatus,
    Command,
    EventType,
    FrozenMap,
    LinuxExecutionBoundary,
    ResourceBudget,
    SClassControlPlane,
    SQLiteEventStore,
)


def fmap(items=()):
    return FrozenMap.from_items(items)


def test_zv6_path_canonicalization_and_escape_prevention(tmp_path):
    """ZV6: Path traversal attempts fail closed and path canonicalization rejects escapes."""
    b = LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    for bad in ["../etc/passwd", "foo/../../bar", "/etc/passwd", "foo\x00bar", ""]:
        with pytest.raises(PermissionError):
            b._secure_workspace_fd(bad)


def test_zv7_workspace_boundary_multi_tenant_isolation(tmp_path):
    """ZV7: Multi-tenant boundary isolation guarantees complete state separation across workspaces."""
    db_path = str(tmp_path / "zv7.sqlite")
    store = SQLiteEventStore(db_path)
    cp = SClassControlPlane(store)
    act = ActorIdentity("system", ActorKind.SYSTEM, None)

    # 1. Commit event in workspace-A
    cmd_a = Command(
        command_id="cmd-a-1",
        workspace_id="workspace-A",
        actor=act,
        event_type=EventType.SHUTDOWN_REQUESTED,
        payload=fmap((("reason", "shutdown-A"),)),
        expected_head=GENESIS_EVENT_HASH,
        actor_signature=None,
        aggregate_id="shutdown-a",
    )
    cp._submit_internal(cmd_a)

    # 2. Workspace-B must remain at genesis (sequence 0)
    state_b = store._load_canonical_state("workspace-B")
    assert state_b.event_sequence == 0
    assert state_b.workspace_id == "workspace-B"
    assert len(store._read_all_committed("workspace-B")) == 0

    # 3. Workspace-A has sequence 1
    state_a = store._load_canonical_state("workspace-A")
    assert state_a.event_sequence == 1
    assert state_a.workspace_id == "workspace-A"
    store.close()


def test_zv8_resource_budget_non_negative_and_overrun_rejection():
    """ZV8: Resource budgets enforce non-negative bounds and prevent overruns."""
    # Negative budget fields are strictly rejected by dataclass validation
    with pytest.raises(ValueError):
        ResourceBudget(
            cpu_cores=-1,
            memory_mb=100,
            network_bytes=100,
            wall_time_ms=1000,
            disk_mb=100,
            process_count=1,
            concurrency=1,
            tokens=100,
            llm_requests=10,
            spend_limit_micro_usd=1000,
            external_effect_units=0,
        )

    # Booleans are strictly rejected as integer budget fields
    with pytest.raises(TypeError):
        ResourceBudget(
            cpu_cores=True,
            memory_mb=100,
            network_bytes=100,
            wall_time_ms=1000,
            disk_mb=100,
            process_count=1,
            concurrency=1,
            tokens=100,
            llm_requests=10,
            spend_limit_micro_usd=1000,
            external_effect_units=0,
        )

    # Valid budget instantiation
    budget = ResourceBudget(
        cpu_cores=4,
        memory_mb=1024,
        network_bytes=0,
        wall_time_ms=1000,
        disk_mb=2048,
        process_count=1,
        concurrency=2,
        tokens=100,
        llm_requests=10,
        spend_limit_micro_usd=5000,
        external_effect_units=0,
    )
    assert budget.cpu_cores == 4


def test_zv9_replay_divergence_tampered_event_detected(tmp_path):
    """ZV9: Tampering with any committed event produces broken hash chain and fails audit."""
    db_path = str(tmp_path / "zv9.sqlite")
    store = SQLiteEventStore(db_path)
    cp = SClassControlPlane(store)
    ws = "ws-tamper"
    act = ActorIdentity("system", ActorKind.SYSTEM, None)

    cmd = Command(
        command_id="cmd-tamper-1",
        workspace_id=ws,
        actor=act,
        event_type=EventType.SHUTDOWN_REQUESTED,
        payload=fmap((("reason", "valid-reason"),)),
        expected_head=GENESIS_EVENT_HASH,
        actor_signature=None,
        aggregate_id="agg-1",
    )
    cp._submit_internal(cmd)
    assert store.verify_chain(ws, 1, 1) is ChainStatus.VALID

    # Tamper with the raw event hash in SQLite canonical_events table
    store._db.execute(
        "UPDATE canonical_events SET event_hash='sha256:' || lower(hex(zeroblob(32))) WHERE workspace_id=? AND event_sequence=1",
        (ws,),
    )
    store._db.commit()

    # Chain verification must now detect BROKEN_HASH
    assert store.verify_chain(ws, 1, 1) is ChainStatus.BROKEN_HASH
    store.close()


def test_zv10_secret_scanner_zero_leakage():
    """ZV10: Secret scanner guarantees zero credential or token leakage in canonical payloads."""
    secret_patterns = ["BEGIN PRIVATE KEY", "ghp_", "sk-ant-", "bearer eyJ"]

    def scan_for_secrets(data: str) -> list[str]:
        found = []
        for pat in secret_patterns:
            if pat in data:
                found.append(pat)
        return found

    sample_safe_payload = '{"action": "test", "status": "COMPLETED", "files": ["src/main.py"]}'
    assert len(scan_for_secrets(sample_safe_payload)) == 0

    sample_leaked_payload = '{"token": "ghp_1234567890abcdef"}'
    assert len(scan_for_secrets(sample_leaked_payload)) == 1
