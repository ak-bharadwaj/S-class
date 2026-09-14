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

# Standard S-Class OpenTelemetry-aligned Span Names
SPAN_SESSION_TURN = "sclass.session.turn"
SPAN_ACTION_AUTHORIZE = "sclass.action.authorize"
SPAN_ACTION_EXECUTE = "sclass.action.execute"
SPAN_OBSERVATION_RECORD = "sclass.observation.record"
SPAN_VERIFICATION_VERIFY = "sclass.verification.verify"
SPAN_PLATFORM_ADAPT = "sclass.platform.adapt"


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
        if isinstance(value, str):
            try:
                from sclass.execution.provenance import redact_secrets
                value = redact_secrets(value)
            except Exception:
                pass
        self.attributes[key] = value

    def set_attributes(self, attrs: Dict[str, Any]) -> None:
        for k, v in attrs.items():
            self.set_attribute(k, v)

    def finish(self, status: str = "OK", error_message: Optional[str] = None) -> None:
        self.end_time = datetime.now(timezone.utc).isoformat()
        self.status = status
        if error_message:
            try:
                from sclass.execution.provenance import redact_secrets
                self.error_message = redact_secrets(error_message)
            except Exception:
                self.error_message = error_message
        else:
            self.error_message = None

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
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.paths = WorkspacePaths(self.workspace_dir)
        self.traces_file = os.path.join(self.paths.events_dir, "traces.jsonl")
        self._active_spans: List[Span] = []

    @property
    def current_span(self) -> Optional[Span]:
        return self._active_spans[-1] if self._active_spans else None

    @contextmanager
    def span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
    ):
        parent = self.current_span
        tid = trace_id or (parent.trace_id if parent else uuid.uuid4().hex)
        pid = parent_span_id or (parent.span_id if parent else None)
        sid = uuid.uuid4().hex[:16]

        current_span = Span(
            name=name,
            trace_id=tid,
            span_id=sid,
            parent_span_id=pid,
            attributes=attributes or {},
        )
        self._active_spans.append(current_span)
        t0 = time.monotonic()
        try:
            yield current_span
            current_span.finish(status="OK")
        except Exception as exc:
            current_span.finish(status="ERROR", error_message=str(exc))
            raise
        finally:
            current_span.duration_ms = round((time.monotonic() - t0) * 1000.0, 2)
            if self._active_spans and self._active_spans[-1] is current_span:
                self._active_spans.pop()
            self._export_span(current_span)

    def _export_span(self, span: Span) -> None:
        try:
            os.makedirs(os.path.dirname(self.traces_file), exist_ok=True)
            with open(self.traces_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(span.to_dict()) + "\n")
        except Exception:
            pass


_TRACERS: Dict[str, LocalTracer] = {}


def get_local_tracer(workspace_dir: str) -> LocalTracer:
    """Returns or creates LocalTracer singleton for a given workspace directory."""
    ws = os.path.abspath(workspace_dir)
    if ws not in _TRACERS:
        _TRACERS[ws] = LocalTracer(ws)
    return _TRACERS[ws]


def read_recent_traces(workspace_dir: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Reads recent spans from the local workspace trace log."""
    ws = os.path.abspath(workspace_dir)
    paths = WorkspacePaths(ws)
    traces_file = os.path.join(paths.events_dir, "traces.jsonl")
    if not os.path.exists(traces_file):
        return []

    results: List[Dict[str, Any]] = []
    try:
        with open(traces_file, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    try:
                        results.append(json.loads(line_str))
                    except Exception:
                        continue
    except Exception:
        return []

    return results[-limit:]
