"""Domain-specific typed exceptions for S-Class D1 Domain Kernel."""


class DomainError(Exception):
    """Base exception for all S-Class domain kernel errors."""
    pass


class DomainValidationError(DomainError):
    """Raised when a domain model invariant or schema validation fails."""
    pass


class DuplicateObligationError(DomainError):
    """Raised when attempting to add an obligation with an existing ID to the DAG."""
    pass


class MissingDependencyError(DomainError):
    """Raised when an obligation references a prerequisite ID not present in the graph."""
    pass


class CyclicDependencyError(DomainError):
    """Raised when an obligation dependency cycle is detected in the graph."""
    pass


class CrossTaskContaminationError(DomainError):
    """Raised when obligations from different tasks are mixed in the same task DAG."""
    pass


class ImmutabilityViolationError(DomainError):
    """Raised when mutation is attempted on a frozen domain object."""
    pass
