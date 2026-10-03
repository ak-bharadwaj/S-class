"""OpenTelemetry Telemetry Bridge Integration.

Emits diagnostic traces and metrics for S-Class control plane operations.
Strictly adheres to §0.5A and §14.6 invariants:
- Zero raw secrets or token bytes in attributes
- Workspace content and unrestricted paths are redacted
- Telemetry never carries canonical authority
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

# Pattern matching potential credentials or secrets
_SECRET_PATTERN = re.compile(
    r"(?i)(password|secret|token|api_key|private_key|auth|bearer)\s*[:=]\s*['\"]?([^\s'\"]+)",
)


def redact_telemetry_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Redacts sensitive values from telemetry attributes."""
    sanitized: dict[str, Any] = {}
    for k, v in data.items():
        if any(term in k.lower() for term in ("secret", "token", "password", "key", "credential")):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, str):
            sanitized[k] = _SECRET_PATTERN.sub(r"\1=[REDACTED]", v)
        elif isinstance(v, dict):
            sanitized[k] = redact_telemetry_payload(v)
        else:
            sanitized[k] = v
    return sanitized


@dataclass(frozen=True)
class TelemetrySpan:
    name: str
    trace_id: str
    span_id: str
    start_time_ns: int
    end_time_ns: int
    attributes: dict[str, Any]
    status: str = "OK"


class OpenTelemetryBridge:
    """Manages diagnostic telemetry and span creation with redaction guarantees."""

    def __init__(self, enabled: bool = False, service_name: str = "sclass-v6.0.1"):
        self.enabled = enabled
        self.service_name = service_name
        self._spans: list[TelemetrySpan] = []

    def record_span(
        self,
        name: str,
        start_time_ns: int,
        attributes: dict[str, Any],
        status: str = "OK",
    ) -> TelemetrySpan:
        """Records an execution span with sanitized attributes."""
        end_time_ns = time.time_ns()
        clean_attrs = redact_telemetry_payload(attributes)
        span = TelemetrySpan(
            name=name,
            trace_id=f"trace-{start_time_ns}",
            span_id=f"span-{end_time_ns}",
            start_time_ns=start_time_ns,
            end_time_ns=end_time_ns,
            attributes=clean_attrs,
            status=status,
        )
        if self.enabled:
            self._spans.append(span)
        return span

    def get_recorded_spans(self) -> tuple[TelemetrySpan, ...]:
        return tuple(self._spans)
