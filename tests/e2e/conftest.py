"""Pytest configuration and common fixtures for S-Class v6.0.1 E2E tests."""

import pytest
from sclass_runtime_v6_0_1 import (
    SClassControlPlane,
    SQLiteEventStore,
)

from tests.e2e.helpers import (
    make_minimal_policy,
    make_minimal_state,
    sample_keypair,
)


@pytest.fixture
def tmp_store(tmp_path):
    """Provides a fresh, isolated SQLiteEventStore with WAL + FULL synchronous durability."""
    db_file = tmp_path / "e2e_events.sqlite"
    store = SQLiteEventStore(str(db_file))
    yield store
    store.close()


@pytest.fixture
def tmp_control_plane(tmp_store):
    """Provides a single-authority SClassControlPlane backed by tmp_store."""
    cp = SClassControlPlane(tmp_store)
    return cp


@pytest.fixture
def initial_state():
    """Provides an immutable minimal engineering state."""
    return make_minimal_state("w")


@pytest.fixture
def minimal_policy():
    """Provides an immutable minimal policy."""
    return make_minimal_policy()


@pytest.fixture
def keypair():
    """Provides a fresh Ed25519 private key and raw public key bytes."""
    return sample_keypair()
