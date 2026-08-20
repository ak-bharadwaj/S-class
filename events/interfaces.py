"""Storage and Event Store Interfaces for S-Class D2."""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
from domain.models import EventEnvelope
from events.state import MaterializedState


class EventStoreInterface(ABC):
    """Abstract interface for append-only event stores."""

    @abstractmethod
    def append(self, event: EventEnvelope) -> None:
        """Appends a cryptographically verified event to the log.
        
        Raises:
            SequenceGapError: If sequence_number > expected_seq.
            DuplicateSequenceError: If sequence_number <= head_seq.
            InvalidParentDigestError: If parent_digest != head_digest.
            DigestMismatchError: If event digest does not verify.
            ConcurrencyConflictError: If concurrent append collision occurs.
        """
        pass

    @abstractmethod
    def get_events(self, after_sequence: int = 0, limit: Optional[int] = None) -> Tuple[EventEnvelope, ...]:
        """Retrieves events strictly ordered by sequence number."""
        pass

    @abstractmethod
    def get_latest_event(self) -> Optional[EventEnvelope]:
        """Returns the current head event, or None if empty."""
        pass

    @abstractmethod
    def replay(self, from_sequence: int = 0) -> MaterializedState:
        """Replays all events from genesis or specified checkpoint, returning MaterializedState."""
        pass

    @abstractmethod
    def verify_integrity(self) -> bool:
        """Validates the entire event chain from genesis: digests, sequence continuity, parent chaining."""
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Returns total number of events in the log."""
        pass


class NonceReservationInterface(ABC):
    """Abstract interface for atomic single-use nonce reservation."""

    @abstractmethod
    def reserve_nonce(self, nonce: str) -> bool:
        """Atomically reserves a single-use nonce (INSERT-if-absent).
        Returns True if reservation succeeded, False if already present.
        Raises CorruptEventLogError or StorageUnavailableError on failure.
        """
        pass

    @abstractmethod
    def is_nonce_consumed(self, nonce: str) -> bool:
        """Queries whether a nonce has been consumed.
        Returns True if consumed, False if not found.
        Raises CorruptEventLogError or StorageUnavailableError on failure.
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clears the nonce store for test fixtures."""
        pass
