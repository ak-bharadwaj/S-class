"""S-Class D2 State & Event Engine Package."""

from domain.models import EventEnvelope
from domain.types import EventType

from events.exceptions import (
    EventEngineError,
    DigestMismatchError,
    InvalidParentDigestError,
    SequenceGapError,
    DuplicateSequenceError,
    ConcurrencyConflictError,
    CorruptEventLogError,
)
from events.serializer import (
    canonicalize_json,
    compute_event_preimage,
    compute_event_digest,
    verify_event_digest,
    create_event,
)
from events.state import (
    MaterializedState,
    GENESIS_PARENT_DIGEST,
)
from events.reducer import (
    reduce_event,
    replay_events,
)
from events.interfaces import EventStoreInterface
from events.store import (
    InMemoryEventStore,
    FileAppendEventStore,
)

__all__ = [
    "EventEnvelope",
    "EventType",
    "EventEngineError",
    "DigestMismatchError",
    "InvalidParentDigestError",
    "SequenceGapError",
    "DuplicateSequenceError",
    "ConcurrencyConflictError",
    "CorruptEventLogError",
    "canonicalize_json",
    "compute_event_preimage",
    "compute_event_digest",
    "verify_event_digest",
    "create_event",
    "MaterializedState",
    "GENESIS_PARENT_DIGEST",
    "reduce_event",
    "replay_events",
    "EventStoreInterface",
    "InMemoryEventStore",
    "FileAppendEventStore",
]
