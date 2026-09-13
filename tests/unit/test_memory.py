"""
Unit Tests for S-Class Memory Provider (Batch M).
"""

import pytest

from sclass.memory.provider import MemoryItem
from sclass.memory.local import LocalMemoryProvider


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "memory_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_local_memory_provider(workspace):
    provider = LocalMemoryProvider(workspace)

    item1 = MemoryItem(
        key="auth_convention",
        content="Use Argon2id for password hashing instead of bcrypt",
        category="convention",
    )
    provider.remember(item1)

    item2 = MemoryItem(
        key="db_retry",
        content="Always set SQLite timeout to 30.0s for WAL concurrency",
        category="insight",
    )
    provider.remember(item2)

    # Retrieval
    results = provider.retrieve("Argon2id")
    assert len(results) == 1
    assert results[0].key == "auth_convention"
    assert "password hashing" in results[0].content

    # Forget
    assert provider.forget("auth_convention") is True
    assert len(provider.retrieve("Argon2id")) == 0
