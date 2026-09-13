"""
S-Class ACP Integration: Event Bridge.
Translates ACP notifications and events into internal S-Class event streams,
and formats internal S-Class execution events (streaming outputs, verifications)
into official ACP JSON-RPC 2.0 notifications.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field

from sclass.integrations.acp.schema import ACPNotification


@dataclass(frozen=True)
class ACPInternalEvent:
    """Normalized internal representation of an event in the ACP bridge."""
    event_type: str
    session_id: str
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "session_id": self.session_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class ACPEventBridge:
    """Bridges events between ACP client/agent and S-Class control plane."""

    def __init__(self):
        self._event_log: List[ACPInternalEvent] = []

    def record_incoming_event(
        self, event_type: str, session_id: str, payload: Dict[str, Any]
    ) -> ACPInternalEvent:
        event = ACPInternalEvent(
            event_type=event_type,
            session_id=session_id,
            payload=payload,
        )
        self._event_log.append(event)
        return event

    def create_notification(
        self, method: str, params: Dict[str, Any]
    ) -> ACPNotification:
        return ACPNotification(
            method=method,
            params=params,
        )

    def create_progress_notification(
        self, session_id: str, progress_token: str, percent: float, message: str
    ) -> ACPNotification:
        return ACPNotification(
            method="session/progress",
            params={
                "session_id": session_id,
                "progress_token": progress_token,
                "percent": percent,
                "message": message,
            },
        )

    def create_output_stream_notification(
        self, session_id: str, stream: str, chunk: str
    ) -> ACPNotification:
        return ACPNotification(
            method="terminal/output",
            params={
                "session_id": session_id,
                "stream": stream,
                "chunk": chunk,
            },
        )

    def get_events_for_session(self, session_id: str) -> List[ACPInternalEvent]:
        return [e for e in self._event_log if e.session_id == session_id]
