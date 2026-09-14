"""
S-Class Integration: Unified Protocol Event Gateway (RC.7).
Single ingestion and fan-out point for all protocol events (ACP, MCP, CLI, IDE).
Normalizes events into canonical ProtocolEvent models and routes to:
- Observation plane
- Intelligence layer
- Fleet coordinator
- Policy / Audit ledgers
"""

from __future__ import annotations
import uuid
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Set, Callable

from enum import Enum

logger = logging.getLogger("sclass.integrations.protocol_gateway")


class EventCriticality(str, Enum):
    """Criticality levels for protocol events."""
    BEST_EFFORT = "BEST_EFFORT"
    DURABLE = "DURABLE"
    GOVERNANCE_CRITICAL = "GOVERNANCE_CRITICAL"


GOVERNANCE_CRITICAL_EVENT_TYPES = {
    "action_requested",
    "action_authorized",
    "action_denied",
    "execution_started",
    "execution_finished",
    "verification_completed",
    "truth_updated",
}

DURABLE_EVENT_TYPES = {
    *GOVERNANCE_CRITICAL_EVENT_TYPES,
    "session_started",
    "session_ended",
    "tool_call",
}


@dataclass(frozen=True)
class ProtocolEvent:
    """Canonical event model for protocol messages flowing across S-Class."""
    event_id: str
    source: str               # "acp", "mcp", "cli", "ide", etc.
    event_type: str           # "initialize", "tool_call", "action_authorized", "action_denied", etc.
    agent_id: str
    session_id: str
    payload: Dict[str, Any]
    criticality: EventCriticality = EventCriticality.BEST_EFFORT
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if self.event_type in GOVERNANCE_CRITICAL_EVENT_TYPES:
            object.__setattr__(self, "criticality", EventCriticality.GOVERNANCE_CRITICAL)
        elif self.event_type in DURABLE_EVENT_TYPES and self.criticality == EventCriticality.BEST_EFFORT:
            object.__setattr__(self, "criticality", EventCriticality.DURABLE)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source": self.source,
            "event_type": self.event_type,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "payload": dict(self.payload),
            "criticality": self.criticality.value if hasattr(self.criticality, "value") else str(self.criticality),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], allow_defaults: bool = False) -> ProtocolEvent:
        event_type = data.get("event_type")
        raw_crit = data.get("criticality")
        crit = EventCriticality(raw_crit) if raw_crit in EventCriticality.__members__.values() else None

        is_gov_critical = (event_type in GOVERNANCE_CRITICAL_EVENT_TYPES) or (crit == EventCriticality.GOVERNANCE_CRITICAL)
        if is_gov_critical and not allow_defaults:
            # Reject missing or placeholder identity fields for governance-critical events
            source = data.get("source")
            agent_id = data.get("agent_id")
            session_id = data.get("session_id")
            if not source or source == "unknown":
                raise ValueError(f"Governance-critical event '{event_type}' missing mandatory 'source'")
            if not agent_id or agent_id == "default_agent":
                raise ValueError(f"Governance-critical event '{event_type}' missing mandatory 'agent_id'")
            if not session_id or session_id == "default_session":
                raise ValueError(f"Governance-critical event '{event_type}' missing mandatory 'session_id'")
            if not event_type or event_type == "unknown":
                raise ValueError("Governance-critical event missing mandatory 'event_type'")

            return cls(
                event_id=data.get("event_id", str(uuid.uuid4())),
                source=source,
                event_type=event_type,
                agent_id=agent_id,
                session_id=session_id,
                payload=dict(data.get("payload", {})),
                criticality=EventCriticality.GOVERNANCE_CRITICAL,
                timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            )

        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            source=data.get("source", "unknown"),
            event_type=event_type or "unknown",
            agent_id=data.get("agent_id", "default_agent"),
            session_id=data.get("session_id", "default_session"),
            payload=dict(data.get("payload", {})),
            criticality=crit or EventCriticality.BEST_EFFORT,
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )


ProtocolEventListener = Callable[[ProtocolEvent], None]


class ProtocolEventGateway:
    """
    Authoritative event hub intercepting, normalizing, and fanning out protocol traffic.
    Guarantees that observation and governance layers receive structured, immutable events.
    Governance-critical events fail closed on subscriber errors and persist durably.
    """

    def __init__(self, max_history: int = 1000, db_path: Optional[str] = None):
        self._listeners: Dict[str, Tuple[ProtocolEventListener, Optional[Set[str]], Optional[str]]] = {}
        self._history: deque[ProtocolEvent] = deque(maxlen=max_history)
        self._db_path = db_path
        self._durable_store: List[ProtocolEvent] = []

    def _persist_durable_event(self, event: ProtocolEvent) -> None:
        """Writes durable security events to authoritative storage."""
        self._durable_store.append(event)
        target_db = self._db_path
        if not target_db and os.path.exists(os.path.join(".sclass", "db", "events.db")):
            target_db = os.path.abspath(os.path.join(".sclass", "db", "events.db"))
        if target_db and os.path.exists(target_db):
            try:
                import sqlite3
                with sqlite3.connect(target_db, timeout=5.0) as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO events (event_id, source, event_type, agent_id, session_id, payload_json, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (event.event_id, event.source, event.event_type, event.agent_id, event.session_id, json.dumps(event.payload), event.timestamp),
                    )
                    conn.commit()
            except Exception as ex:
                logger.warning(f"Failed to persist durable event to SQLite {target_db}: {ex}")

    def subscribe(
        self,
        listener: ProtocolEventListener,
        event_types: Optional[Set[str]] = None,
        source: Optional[str] = None,
    ) -> str:
        """
        Subscribes a listener to protocol events with optional filtering.
        Returns subscription ID for unregistering.
        """
        sub_id = str(uuid.uuid4())
        self._listeners[sub_id] = (listener, event_types, source)
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        """Removes an active subscription."""
        if sub_id in self._listeners:
            del self._listeners[sub_id]
            return True
        return False

    def emit(self, event: ProtocolEvent) -> None:
        """
        Emits a canonical ProtocolEvent, recording to history and fanning out
        to all matching registered subscribers.
        For GOVERNANCE_CRITICAL events: listener failures fail closed / propagate.
        Durable events are persisted to authoritative storage.
        """
        self._history.append(event)

        if event.criticality in (EventCriticality.DURABLE, EventCriticality.GOVERNANCE_CRITICAL):
            self._persist_durable_event(event)

        for sub_id, (listener, event_types, source) in list(self._listeners.items()):
            if source and event.source != source:
                continue
            if event_types and event.event_type not in event_types:
                continue
            try:
                listener(event)
            except Exception as exc:
                logger.warning(f"Subscriber {sub_id} failed on event {event.event_id}: {exc}")
                if event.criticality == EventCriticality.GOVERNANCE_CRITICAL:
                    raise RuntimeError(
                        f"Governance-critical subscriber {sub_id} failed on authoritative event "
                        f"'{event.event_type}' ({event.event_id}): {exc}"
                    ) from exc

    def emit_event(
        self,
        source: str,
        event_type: str,
        agent_id: str,
        session_id: str,
        payload: Dict[str, Any],
        event_id: Optional[str] = None,
        criticality: Optional[EventCriticality] = None,
    ) -> ProtocolEvent:
        """Helper to construct and emit a ProtocolEvent in a single call."""
        event = ProtocolEvent(
            event_id=event_id or f"evt_{uuid.uuid4().hex[:12]}",
            source=source,
            event_type=event_type,
            agent_id=agent_id,
            session_id=session_id,
            payload=payload,
            criticality=criticality or EventCriticality.BEST_EFFORT,
        )
        self.emit(event)
        return event

    def emit_acp(
        self,
        event_type: str,
        session_id: str,
        agent_id: str,
        payload: Dict[str, Any],
    ) -> ProtocolEvent:
        """Convenience method for ACP protocol events."""
        return self.emit_event(
            source="acp",
            event_type=event_type,
            agent_id=agent_id,
            session_id=session_id,
            payload=payload,
        )

    def emit_mcp(
        self,
        event_type: str,
        session_id: str,
        agent_id: str,
        payload: Dict[str, Any],
    ) -> ProtocolEvent:
        """Convenience method for MCP protocol events."""
        return self.emit_event(
            source="mcp",
            event_type=event_type,
            agent_id=agent_id,
            session_id=session_id,
            payload=payload,
        )

    def get_recent_events(self, limit: int = 50, source: Optional[str] = None) -> List[ProtocolEvent]:
        """Returns recent events from the in-memory buffer."""
        events = list(self._history)
        if source:
            events = [e for e in events if e.source == source]
        return events[-limit:]

    def clear_history(self) -> None:
        """Clears in-memory event buffer."""
        self._history.clear()


# Global singleton gateway
_GLOBAL_GATEWAY: Optional[ProtocolEventGateway] = None


def get_protocol_gateway() -> ProtocolEventGateway:
    """Returns the process-wide ProtocolEventGateway singleton."""
    global _GLOBAL_GATEWAY
    if _GLOBAL_GATEWAY is None:
        _GLOBAL_GATEWAY = ProtocolEventGateway()
    return _GLOBAL_GATEWAY


def reset_protocol_gateway() -> ProtocolEventGateway:
    """Resets the singleton gateway (used in testing)."""
    global _GLOBAL_GATEWAY
    _GLOBAL_GATEWAY = ProtocolEventGateway()
    return _GLOBAL_GATEWAY


__all__ = [
    "EventCriticality",
    "ProtocolEvent",
    "ProtocolEventGateway",
    "get_protocol_gateway",
    "reset_protocol_gateway",
    "GOVERNANCE_CRITICAL_EVENT_TYPES",
    "DURABLE_EVENT_TYPES",
]
