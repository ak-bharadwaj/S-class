"""
S-Class Telemetry: Tracing and local observability.
"""

from sclass.telemetry.tracing import (
    LocalTracer,
    Span,
    get_local_tracer,
    read_recent_traces,
    SPAN_SESSION_TURN,
    SPAN_ACTION_AUTHORIZE,
    SPAN_ACTION_EXECUTE,
    SPAN_OBSERVATION_RECORD,
    SPAN_VERIFICATION_VERIFY,
    SPAN_PLATFORM_ADAPT,
)

__all__ = [
    "LocalTracer",
    "Span",
    "get_local_tracer",
    "read_recent_traces",
    "SPAN_SESSION_TURN",
    "SPAN_ACTION_AUTHORIZE",
    "SPAN_ACTION_EXECUTE",
    "SPAN_OBSERVATION_RECORD",
    "SPAN_VERIFICATION_VERIFY",
    "SPAN_PLATFORM_ADAPT",
]
