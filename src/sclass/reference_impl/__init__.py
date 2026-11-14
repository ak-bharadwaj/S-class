"""Non-authoritative reference scaffold implementations for S-Class components.

This package contains reference implementations relocated from 10-CONFORMANCE
under Directive A6.1:
  - ReferenceWorker (relocated CanonicalWorker)
  - ReferenceHandoffCompiler (relocated CanonicalHandoffCompiler)
  - ReferenceVerificationProvider (relocated CanonicalVerificationProvider)
  - ReferenceOperatingLoop (relocated CanonicalOperatingLoop)
  - ReferenceCoordinatedRecovery (relocated CanonicalCoordinatedRecovery)
  - ReferenceSQLiteStore (relocated SQLite URI, migration, and fault injection extensions)

These reference classes provide non-authoritative scaffold implementations for testing,
development, and conformance verification. They cannot manufacture authority or write
directly to canonical storage.
"""
from __future__ import annotations

from sclass.reference_impl.handoff import (
    CanonicalHandoffCompiler,
    ReferenceHandoffCompiler,
)
from sclass.reference_impl.operating_loop import (
    CanonicalOperatingLoop,
    ReferenceOperatingLoop,
)
from sclass.reference_impl.recovery import (
    CanonicalCoordinatedRecovery,
    ReferenceCoordinatedRecovery,
)
from sclass.reference_impl.store import (
    ReferenceEventStore,
    ReferenceSQLiteStore,
    SQLiteCanonicalStore,
    SQLiteEventStore,
)
from sclass.reference_impl.verification import (
    CanonicalVerificationProvider,
    ReferenceVerificationProvider,
)
from sclass.reference_impl.worker import (
    CanonicalWorker,
    ReferenceWorker,
)

__all__ = [
    "ReferenceWorker",
    "CanonicalWorker",
    "ReferenceHandoffCompiler",
    "CanonicalHandoffCompiler",
    "ReferenceVerificationProvider",
    "CanonicalVerificationProvider",
    "ReferenceOperatingLoop",
    "CanonicalOperatingLoop",
    "ReferenceCoordinatedRecovery",
    "CanonicalCoordinatedRecovery",
    "ReferenceSQLiteStore",
    "ReferenceEventStore",
    "SQLiteCanonicalStore",
    "SQLiteEventStore",
]
