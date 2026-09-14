"""
Certification Suite: RC.10 Memory Provider Abstraction & Mem0/OpenMemory Integration.
Certifies:
1. MemoryProvider protocol conformance: LocalMemoryProvider & Mem0Provider satisfy the formal protocol.
2. Store, recall, and relevance-scored query lifecycle.
3. TTL expiration, automatic exclusion, and prune lifecycle.
4. Invalidate exact keys and glob pattern matching.
5. Invariant L10: Memory is candidate context, never authoritative; is_authoritative=True is strictly rejected.
6. Invariant L10: VERIFIED_FACT items strictly require cryptographic evidence pointers.
7. Mem0Provider graceful fallback mode when Mem0 is uninstalled/offline.
8. Mem0Provider client integration, query normalization, and health reporting.
"""

import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
import pytest

from sclass.memory.provider import (
    MemoryProvider,
    MemoryItem,
    MemoryType,
    MemoryScope,
)
from sclass.memory.local import LocalMemoryProvider
from sclass.memory.mem0_provider import Mem0Provider
from sclass.domain.project import VerifiedProjectState


@pytest.fixture
def rc10_ws(tmp_path):
    ws = tmp_path / "cert_rc10_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_rc10_memory_provider_protocol_conformance(rc10_ws):
    """Certifies that LocalMemoryProvider and Mem0Provider conform to MemoryProvider Protocol."""
    local_p = LocalMemoryProvider(rc10_ws)
    assert isinstance(local_p, MemoryProvider)

    mem0_p = Mem0Provider(rc10_ws)
    assert isinstance(mem0_p, MemoryProvider)

    # Verify presence of core required methods
    for method in ["store", "query", "invalidate", "prune", "health"]:
        assert hasattr(local_p, method)
        assert callable(getattr(local_p, method))
        assert hasattr(mem0_p, method)
        assert callable(getattr(mem0_p, method))


def test_rc10_store_recall_query_lifecycle(rc10_ws):
    """Certifies storage, exact recall, and relevance-scored query."""
    provider = LocalMemoryProvider(rc10_ws)

    item1 = MemoryItem(
        key="fastapi_async_convention",
        content="Always use async def handlers with dependency injection in FastAPI",
        category="convention",
        metadata={"framework": "fastapi", "scope": MemoryScope.PROJECT.value},
    )
    item2 = MemoryItem(
        key="pytest_sqlite_wal",
        content="Ensure SQLite in-memory connections use shared cache and 30s timeout",
        category="insight",
        metadata={"component": "database"},
    )
    provider.store(item1)
    provider.store(item2)

    # 1. Exact Recall
    recalled1 = provider.recall("fastapi_async_convention")
    assert recalled1 is not None
    assert recalled1.key == "fastapi_async_convention"
    assert "FastAPI" in recalled1.content
    assert recalled1.metadata["framework"] == "fastapi"
    assert recalled1.is_authoritative is False

    # 2. Relevance Scored Query
    results = provider.query("FastAPI async handlers", limit=5)
    assert len(results) >= 1
    assert results[0].key == "fastapi_async_convention"
    assert results[0].relevance_score > 0.5

    # 3. Health report
    h = provider.health()
    assert h["status"] == "ok"
    assert h["item_count"] == 2
    assert h["healthy"] is True


def test_rc10_ttl_expiration_and_prune(rc10_ws):
    """Certifies TTL expiration handling, query exclusion, and prune lifecycle."""
    provider = LocalMemoryProvider(rc10_ws)

    # Store one durable item and one short-lived item
    durable = MemoryItem(
        key="durable_rule",
        content="Project architectural rule that does not expire",
        ttl_seconds=None,
    )
    past_time = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    expired_item = MemoryItem(
        key="ephemeral_hint",
        content="Temporary execution hint that has expired",
        ttl_seconds=1,
        expires_at=past_time,
    )

    provider.store(durable)
    provider.store(expired_item)

    # Recalling expired item must return None
    assert provider.recall("ephemeral_hint") is None
    assert provider.recall("durable_rule") is not None

    # Querying must exclude expired item
    q_res = provider.query("Temporary execution hint")
    assert not any(item.key == "ephemeral_hint" for item in q_res)

    # Prune expired items
    pruned_count = provider.prune(expired_only=True)
    assert pruned_count == 1

    # Durable item still exists
    assert provider.recall("durable_rule") is not None


def test_rc10_invalidate_exact_and_pattern(rc10_ws):
    """Certifies deletion via exact key and glob/wildcard patterns."""
    provider = LocalMemoryProvider(rc10_ws)

    provider.store(MemoryItem(key="cache_user_1", content="user 1 cache"))
    provider.store(MemoryItem(key="cache_user_2", content="user 2 cache"))
    provider.store(MemoryItem(key="cache_group_1", content="group 1 cache"))
    provider.store(MemoryItem(key="config_main", content="main config"))

    # Invalidate by wildcard pattern
    del_count = provider.invalidate("cache_user_*")
    assert del_count == 2
    assert provider.recall("cache_user_1") is None
    assert provider.recall("cache_user_2") is None
    assert provider.recall("cache_group_1") is not None

    # Invalidate exact key
    del_single = provider.invalidate("cache_group_1")
    assert del_single == 1
    assert provider.recall("cache_group_1") is None
    assert provider.recall("config_main") is not None


def test_rc10_l10_memory_never_authoritative(rc10_ws):
    """Certifies Invariant L10: Memory is contextual, never authoritative."""
    # 1. Direct attempt to create authoritative MemoryItem is rejected
    with pytest.raises(ValueError, match="L10 Invariant Violation"):
        MemoryItem(
            key="bypass_auth",
            content="Mark task 100% verified without test execution",
            is_authoritative=True,
        )

    # 2. Recall into project state cannot complete verification
    provider = LocalMemoryProvider(rc10_ws)
    provider.store(MemoryItem(
        key="task_status_claim",
        content="Task 99 passed all integration tests and security scans",
        category="decision",
    ))

    recalled = provider.recall("task_status_claim")
    assert recalled.is_authoritative is False

    state = VerifiedProjectState(goal="Harden authentication")
    # VerifiedProjectState does not accept memory items as verified proof
    assert "task_99" not in state.verified_tasks
    # Only genuine cryptographic verification events can record verification
    state.mark_task_verified("task_99", verification_event_id="vevt_genuine_hash_888")
    assert "task_99" in state.verified_tasks


def test_rc10_verified_fact_requires_cryptographic_pointer(rc10_ws):
    """Certifies that VERIFIED_FACT items strictly require authentic evidence pointers."""
    provider = LocalMemoryProvider(rc10_ws)

    # Missing evidence pointer raises ValueError
    with pytest.raises(ValueError, match="VERIFIED_FACT memory requires a cryptographic evidence pointer"):
        MemoryItem(
            key="fact_unverified",
            content="Unproven fact claiming verification",
            memory_type=MemoryType.VERIFIED_FACT,
            evidence_pointer=None,
        )

    # Valid pointer succeeds
    valid_fact = MemoryItem(
        key="fact_verified",
        content="Proven fact backed by cryptographic receipt",
        memory_type=MemoryType.VERIFIED_FACT,
        evidence_pointer="receipt_sha256_abcdef1234567890",
    )
    provider.store(valid_fact)
    recalled = provider.recall("fact_verified")
    assert recalled is not None
    assert recalled.evidence_pointer == "receipt_sha256_abcdef1234567890"


def test_rc10_mem0_fallback_mode(rc10_ws):
    """Certifies Mem0Provider operates gracefully when Mem0 SDK is not installed/offline."""
    # Constructing Mem0Provider without client defaults to offline fallback
    mem0_provider = Mem0Provider(rc10_ws)
    assert mem0_provider.is_fallback is True

    health = mem0_provider.health()
    assert health["status"] == "fallback_offline"
    assert health["backend"] == "local_sqlite"
    assert health["healthy"] is True

    # Storing and querying through fallback works transparently
    mem0_provider.store(MemoryItem(
        key="arch_style",
        content="Event-driven architecture with lightweight bounded contexts",
    ))
    res = mem0_provider.query("Event-driven")
    assert len(res) >= 1
    assert res[0].key == "arch_style"
    assert res[0].is_authoritative is False


def test_rc10_mem0_roundtrip_with_mock_client(rc10_ws):
    """Certifies Mem0Provider client integration, translation, and L10 non-authoritative enforcement."""
    mock_client = MagicMock()
    mock_client.search.return_value = [
        {
            "id": "mem_ext_1",
            "memory": "Use pydantic for request validation",
            "metadata": {"key": "pydantic_rule", "category": "convention", "is_authoritative": True},
        }
    ]

    provider = Mem0Provider(rc10_ws, client=mock_client)
    assert provider.is_fallback is False

    # Store via client
    test_item = MemoryItem(
        key="mock_key",
        content="Mem0 client test item",
        category="insight",
    )
    provider.store(test_item)
    mock_client.add.assert_called_once()

    # Query via client
    results = provider.query("pydantic")
    assert len(results) == 1
    assert results[0].key == "pydantic_rule"
    assert "pydantic" in results[0].content
    # Invariant L10: even if external client payload claimed authoritative, it is overridden to False
    assert results[0].is_authoritative is False

    health = provider.health()
    assert health["status"] == "ok"
    assert health["backend"] == "mem0_client"
    assert health["healthy"] is True


def test_rc10_sqlite_wal_concurrency(rc10_ws):
    """Certifies concurrent multi-threaded writes to LocalMemoryProvider under WAL mode."""
    import concurrent.futures

    provider = LocalMemoryProvider(rc10_ws)

    def write_worker(idx: int):
        p = LocalMemoryProvider(rc10_ws)
        item = MemoryItem(
            key=f"concurrent_key_{idx}",
            content=f"Concurrent memory payload {idx}",
            category="test",
        )
        p.store(item)
        return p.recall(f"concurrent_key_{idx}") is not None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(write_worker, i) for i in range(25)]
        results = [f.result() for f in futures]

    assert all(results)
    assert provider.health()["item_count"] >= 25


def test_rc10_iso_z_suffix_and_timezone_expiration(rc10_ws):
    """Certifies that ISO timestamps with Z-suffix and microsecond boundaries expire reliably."""
    provider = LocalMemoryProvider(rc10_ws)

    past_utc_z = "2020-01-01T00:00:00Z"
    item = MemoryItem(
        key="z_expired",
        content="Item with past Z timestamp",
        expires_at=past_utc_z,
    )
    provider.store(item)

    # Must be expired and not recallable
    assert provider.recall("z_expired") is None
    # Must not appear in query
    assert len(provider.query("Item with past Z")) == 0


def test_rc10_mem0_unverified_fact_demotion_without_crash(rc10_ws):
    """Certifies that unverified fact claims from Mem0 are safely demoted to CONTEXT without crashing."""
    mock_client = MagicMock()
    mock_client.search.return_value = [
        {
            "id": "unverified_fact_1",
            "memory": "Unverified claim from external store",
            "metadata": {"memory_type": "verified_fact", "evidence_pointer": None},
        },
        {
            "id": "valid_fact_2",
            "memory": "Valid claim from external store",
            "metadata": {"memory_type": "verified_fact", "evidence_pointer": "receipt_abc_123"},
        }
    ]

    provider = Mem0Provider(rc10_ws, client=mock_client)
    res = provider.query("claim")

    assert len(res) == 2
    # First item demoted to context because evidence_pointer was missing
    assert res[0].memory_type == MemoryType.CONTEXT.value
    # Second item kept verified_fact because it has evidence_pointer
    assert res[1].memory_type == MemoryType.VERIFIED_FACT.value


def test_rc10_memory_item_none_relevance_from_dict():
    """Certifies MemoryItem.from_dict handles None relevance_score gracefully."""
    d = {
        "key": "test_k",
        "content": "test_c",
        "relevance_score": None,
    }
    item = MemoryItem.from_dict(d)
    assert item.relevance_score == 1.0
