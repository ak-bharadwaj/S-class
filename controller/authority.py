"""D5 Controller Authority Interfaces & Protocols (§8.1, §8.2, CORE-05).

Defines typed authority protocols for Planning Lease resolution and Materialized State resolution.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional, Protocol, Tuple, runtime_checkable
from dataclasses import dataclass
import hashlib
from events.serializer import canonicalize_json

if TYPE_CHECKING:
    from planner.models import PlanningLease


@dataclass(frozen=True)
class ProposalAuthorityContext:
    """Immutable, typed authoritative boundary coordinates for D5 governance (§8.1, §8.2, CORE-05)."""
    task_id: str
    owner_id: str
    lease_epoch: int
    fencing_token: int
    state_version: int
    state_digest: str

    def __post_init__(self):
        if not self.task_id:
            raise ValueError("task_id cannot be empty in ProposalAuthorityContext.")
        if not self.owner_id:
            raise ValueError("owner_id cannot be empty in ProposalAuthorityContext.")
        if not isinstance(self.lease_epoch, int) or self.lease_epoch < 0:
            raise ValueError("lease_epoch must be an integer >= 0.")
        if not isinstance(self.fencing_token, int) or self.fencing_token < 0:
            raise ValueError("fencing_token must be an integer >= 0.")
        if not isinstance(self.state_version, int) or self.state_version < 0:
            raise ValueError("state_version must be an integer >= 0.")
        if not self.state_digest:
            raise ValueError("state_digest cannot be empty in ProposalAuthorityContext.")

    @property
    def authority_context_digest(self) -> str:
        """Deterministic SHA-256 canonical digest of this authority context."""
        payload = {
            "task_id": self.task_id,
            "owner_id": self.owner_id,
            "lease_epoch": self.lease_epoch,
            "fencing_token": self.fencing_token,
            "state_version": self.state_version,
            "state_digest": self.state_digest,
        }
        return hashlib.sha256(canonicalize_json(payload)).hexdigest()


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


def resolve_proposal_authority_context(
    lease_authority: Any,
    state_authority: Any,
    task_id: str,
) -> ProposalAuthorityContext:
    """Resolves ProposalAuthorityContext from typed authority providers or raises explicit exceptions."""
    if lease_authority is None:
        raise ValueError("MISSING_LEASE_AUTHORITY: Controller has no authoritative lease provider configured")
    if not isinstance(lease_authority, LeaseAuthority):
        raise TypeError("INVALID_LEASE_AUTHORITY: lease_authority does not implement LeaseAuthority protocol")
    if state_authority is None:
        raise ValueError("MISSING_STATE_AUTHORITY: Controller has no authoritative state provider configured")
    if not isinstance(state_authority, StateAuthority):
        raise TypeError("INVALID_STATE_AUTHORITY: state_authority does not implement StateAuthority protocol")

    active_lease = lease_authority.get_active_lease(task_id)
    if active_lease is None or not getattr(active_lease, "is_active", False):
        raise ValueError(f"NO_ACTIVE_LEASE: No active planning lease found for task '{task_id}'")

    state_coords = state_authority.get_authoritative_state()
    if not isinstance(state_coords, tuple) or len(state_coords) != 2:
        raise ValueError("State coordinates must be a Tuple[int, str]")
    state_version, state_digest = state_coords

    return ProposalAuthorityContext(
        task_id=task_id,
        owner_id=active_lease.owner_id,
        lease_epoch=active_lease.lease_epoch,
        fencing_token=active_lease.fencing_token,
        state_version=state_version,
        state_digest=state_digest,
    )


class StaticLeaseAuthority:
    """Immutable in-memory LeaseAuthority for testing or deterministic fixtures."""

    def __init__(self, leases: Optional[dict[str, Any]] = None):
        self._leases = dict(leases or {})

    def set_lease(self, task_id: str, lease: Any):
        self._leases[task_id] = lease

    def get_active_lease(self, task_id: str) -> Optional[Any]:
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
