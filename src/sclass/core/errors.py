"""
S-Class Core Exceptions.
"""

from __future__ import annotations
from typing import Optional, Any, Dict


class SClassError(Exception):
    """Base exception for all S-Class control plane errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AuthorizationError(SClassError):
    """Raised when an operation is denied or authorization evaluation fails."""
    pass


class SecurityViolationError(AuthorizationError):
    """Raised when a security invariant (secret leakage, path escape, shell injection) is breached."""
    pass


class ObservationIntegrityError(SClassError):
    """Raised when execution observation or ledger provenance anchoring fails."""
    pass


class VerificationFailedError(SClassError):
    """Raised when independent verification of a claim fails."""
    pass


class ProvenanceError(SClassError):
    """Raised when cryptographic evidence receipt or ledger hash-chain integrity is compromised."""
    pass


class StalenessError(SClassError):
    """Raised when evidence is invalidated by subsequent repository mutations."""
    pass


class StateTransitionError(SClassError):
    """Raised when a task or project lifecycle state transition is invalid."""
    pass


class PolicyEvaluationError(SClassError):
    """Raised when OPA or internal policy evaluation encounters a syntax or runtime fault."""
    pass


class StorageError(SClassError):
    """Raised when SQLite, event journal, or content-addressed storage fails."""
    pass


class HandoffIntegrityError(SClassError):
    """Raised when handoff package or context assembly fails due to database or state integrity error."""
    pass


class EpistemicIntegrityError(SClassError):
    """Raised when epistemic invariants are breached (e.g. attempting to certify truth without observation)."""
    pass


class FleetIntegrityError(SClassError):
    """Raised when fleet swarm coordination, leasing, or multi-agent state integrity is compromised."""
    pass


class RecoveryError(SClassError):
    """Base exception for all recovery and convergence faults."""
    pass


class RecoveryStateTransitionError(RecoveryError, StateTransitionError):
    """Raised when an invalid or forbidden recovery state transition is attempted."""
    pass


class RecoveryExhaustedError(RecoveryError):
    """Raised when recovery attempt budget is exhausted without convergence."""
    pass


class RecoveryPersistenceError(RecoveryError, StorageError):
    """Raised when recovery state cannot be durably persisted or is corrupt."""
    pass


