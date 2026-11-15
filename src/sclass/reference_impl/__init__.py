"""Non-authoritative reference scaffold implementations for S-Class components.

This package contains reference implementations relocated from 10-CONFORMANCE
under Directive A6.1:
  - ReferenceWorker (relocated CanonicalWorker)
  - ReferenceHandoffCompiler (relocated CanonicalHandoffCompiler)
  - ReferenceVerificationProvider (relocated CanonicalVerificationProvider)
  - ReferenceOperatingLoop (relocated CanonicalOperatingLoop)
  - ReferenceCoordinatedRecovery (relocated CanonicalCoordinatedRecovery)
  - ReferenceSQLiteStore (relocated SQLite URI, migration, and fault injection extensions)
  - ReferenceExecutionGate (relocated and corrected execution gate with A6-R1 through A6-R6 guards)

These reference classes provide non-authoritative scaffold implementations for testing,
development, and conformance verification. They cannot manufacture authority or write
directly to canonical storage.
"""
from __future__ import annotations

from sclass.reference_impl.gate import (
    ReferenceExecutionGate,
)
from sclass.reference_impl.handoff import (
    ReferenceHandoffCompiler,
)
from sclass.reference_impl.operating_loop import (
    ReferenceOperatingLoop,
)
from sclass.reference_impl.recovery import (
    ReferenceCoordinatedRecovery,
)
from sclass.reference_impl.store import (
    ReferenceEventStore,
    ReferenceSQLiteStore,
)
from sclass.reference_impl.verification import (
    ReferenceVerificationProvider,
)
from sclass.reference_impl.worker import (
    ReferenceWorker,
)

__all__ = [
    "ReferenceWorker",
    "ReferenceHandoffCompiler",
    "ReferenceVerificationProvider",
    "ReferenceOperatingLoop",
    "ReferenceCoordinatedRecovery",
    "ReferenceSQLiteStore",
    "ReferenceEventStore",
    "ReferenceExecutionGate",
]
