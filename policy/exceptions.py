"""D3 Policy Engine Domain Exceptions."""

class PolicyEngineError(Exception):
    """Base exception for all D3 Policy Engine errors."""
    pass


class PolicyValidationError(PolicyEngineError):
    """Raised when a policy or policy exception fails Draft-2020-12 schema validation or anti-pollution checks."""
    pass


class PolicyWeakeningError(PolicyEngineError):
    """Raised when a child/lower-scope policy attempts to weaken or relax an ancestor/higher-scope constraint."""
    pass


class InvalidExceptionError(PolicyEngineError):
    """Raised when a PolicyException record is malformed, unsigned, or forged."""
    pass


class ExpiredExceptionError(PolicyEngineError):
    """Raised when a PolicyException has expired relative to the evaluation context timestamp."""
    pass
