"""
S-Class Telemetry: Structured Local Tracing (OpenTelemetry Schema Compatible).
Provides zero-cloud distributed tracing spans persisted to .sclass/events/traces.jsonl.
"""

from __future__ import annotations
import os
import json
import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from contextlib import contextmanager

from sclass.storage.paths import WorkspacePaths


@dataclass
class Span:
    """Represents an execution span compatible with OTel trace models."""
    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: Optional[str] = None
    duration_ms: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "OK"
    error_message: Optional[str] = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def finish(self, status: str = "OK", error_message: Optional[str] = None) -> None:
        self.end_time = datetime.now(timezone.utc).isoformat()
        self.status = status
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "status": self.status,
            "error_message": self.error_message,
        }


class LocalTracer:
    """Emits trace spans to .sclass/events/traces.jsonl with zero cloud dependencies."""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.paths = WorkspacePaths(workspace_dir)
        self.traces_file = os.path.join(self.paths.events_dir, "traces.jsonl")

    @contextmanager
    def span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
    ):
        tid = trace_id or uuid.uuid4().hex
        sid = uuid.uuid4().hex[:16]
        current_span = Span(
            name=name,
            trace_id=tid,
            span_id=sid,
            parent_span_id=parent_span_id,
            attributes=attributes or {},
        )
        t0 = time.monotonic()
        try:
            yield current_span
            current_span.finish(status="OK")
        except Exception as exc:
            current_span.finish(status="ERROR", error_message=str(exc))
            raise
        finally:
            current_span.duration_ms = round((time.monotonic() - t0) * 1000.0, 2)
            self._export_span(current_span)

    def _export_span(self, span: Span) -> None:
        try:
            os.makedirs(os.path.dirname(self.traces_file), exist_ok=True)
            with open(self.traces_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(span.to_dict()) + "\n")
        except Exception:
            pass
