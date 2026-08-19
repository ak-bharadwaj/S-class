"""D2 State & Event Engine Exceptions."""

class EventEngineError(Exception):
    """Base exception for all D2 event engine errors."""
    pass


class CanonicalSerializationError(TypeError, EventEngineError):
    """Raised when an object, mapping key, or field cannot be canonicalized under RFC 8785."""
    pass


class DigestMismatchError(EventEngineError):
    """Raised when an event digest does not match its canonical hash."""
    pass


class InvalidParentDigestError(EventEngineError):
    """Raised when an event's parent_digest does not match the preceding event digest."""
    pass


class SequenceGapError(EventEngineError):
    """Raised when an appended event has a sequence number greater than expected."""
    pass


class DuplicateSequenceError(EventEngineError):
    """Raised when an appended event has a sequence number <= current head."""
    pass


class ConcurrencyConflictError(EventEngineError):
    """Raised when a concurrent append attempt encounters a sequence/hash collision."""
    pass


class CorruptEventLogError(EventEngineError):
    """Raised when an event log file contains unparseable or corrupted data."""
    pass
