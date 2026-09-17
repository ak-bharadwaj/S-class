"""Telemetry contracts for OpenTelemetry span generation."""
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass(frozen=True)
class SpanDefinition:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    start_time_ns: int
    end_time_ns: int
    attributes: Dict[str, Any]
    status_code: str
