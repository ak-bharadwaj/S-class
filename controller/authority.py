"""D5 Controller Authority Interfaces & Protocols (§8.1, §8.2, CORE-05).

Defines typed authority protocols for Planning Lease resolution and Materialized State resolution.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional, Protocol, Tuple, runtime_checkable

if TYPE_CHECKING:
    from planner.models import PlanningLease


@runtime_checkable
class LeaseAuthority(Protocol):
    """Explicit typed authority protocol for planning lease verification."""

    def get_active_lease(self, task_id: str) -> Optional[PlanningLease]:
        """Returns the active PlanningLease for task_id or raises LeaseCorruptionError if corrupted."""
        ...


@runtime_checkable
class StateAuthority(Protocol):
    """Explicit typed authority protocol for materialized state verification."""

    def get_authoritative_state(self) -> Tuple[int, str]:
        """Returns (state_version, state_digest) of the current authoritative state."""
        ...


class StaticLeaseAuthority:
    """Immutable in-memory LeaseAuthority for testing or deterministic fixtures."""

    def __init__(self, leases: Optional[dict[str, PlanningLease]] = None):
        self._leases = dict(leases or {})

    def set_lease(self, task_id: str, lease: PlanningLease):
        self._leases[task_id] = lease

    def get_active_lease(self, task_id: str) -> Optional[PlanningLease]:
        return self._leases.get(task_id)


class StaticStateAuthority:
    """Immutable in-memory StateAuthority for testing or deterministic fixtures."""

    def __init__(self, state_version: int = 1, state_digest: str = "1" * 64):
        self._state_version = state_version
        self._state_digest = state_digest

    def set_state(self, state_version: int, state_digest: str):
        self._state_version = state_version
        self._state_digest = state_digest

    def get_authoritative_state(self) -> Tuple[int, str]:
        return (self._state_version, self._state_digest)
