"""
S-Class EOS Canonical Event Store & Event Sourcing Architecture
(event_store.py)

Defines:
1. EventRecord: Canonical event schema consumed uniformly by event writer and replay projector.
2. EventStore: Append-only persistence and snapshot checkpointing engine.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
import os
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("sclass_event_store")


@dataclass
class EventRecord:
    """Canonical event schema for S-Class deterministic event sourcing."""
    event_id: int
    event_name: str
    from_state: str
    to_state: str
    timestamp: str
    payload: Dict[str, Any] = field(default_factory=dict)
    event_type: str = "PHASE_MUTATED"
    workflow_profile: str = "full"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_name": self.event_name,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "event_type": self.event_type,
            "workflow_profile": self.workflow_profile
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EventRecord":
        if "event_id" not in d:
            raise ValueError("EventRecord missing mandatory 'event_id'")
        
        # Canonical extraction supporting uniform and legacy property names
        event_id = int(d["event_id"])
        event_name = str(d.get("event_name") or d.get("eventName") or d.get("eventFired") or "")
        from_state = str(d.get("from_state") or d.get("fromPhase") or d.get("fromState") or "")
        to_state = str(d.get("to_state") or d.get("toPhase") or d.get("toState") or "")
        timestamp = str(d.get("timestamp") or datetime.now(timezone.utc).isoformat() + "Z")
        payload = d.get("payload") if isinstance(d.get("payload"), dict) else {}
        event_type = str(d.get("event_type") or d.get("eventType") or "PHASE_MUTATED")
        workflow_profile = str(d.get("workflow_profile") or d.get("workflowProfile") or "full")

        return cls(
            event_id=event_id,
            event_name=event_name,
            from_state=from_state,
            to_state=to_state,
            timestamp=timestamp,
            payload=payload,
            event_type=event_type,
            workflow_profile=workflow_profile
        )

    def __getitem__(self, key: str) -> Any:
        if key in ("event_id", "event_name", "from_state", "to_state", "timestamp", "payload", "event_type", "workflow_profile"):
            return getattr(self, key)
        raise KeyError(f"'{key}' is not a canonical EventRecord attribute. Access payload properties via record.payload['{key}'].")

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


class EventStore:
    """Append-only canonical event log with Snapshot Checkpointing for O(delta) replay performance."""

    @staticmethod
    def get_store_file(workspace_dir: Optional[str] = None) -> str:
        cwd = workspace_dir if workspace_dir else os.getcwd()
        return os.path.join(cwd, ".agents", "event_store.jsonl")

    @staticmethod
    def get_snapshot_file(workspace_dir: Optional[str] = None) -> str:
        cwd = workspace_dir if workspace_dir else os.getcwd()
        return os.path.join(cwd, ".agents", "event_store_snapshot.json")

    @classmethod
    def append_event(cls, event_record: Any, workspace_dir: Optional[str] = None) -> EventRecord:
        """Appends a canonical EventRecord to the immutable event store."""
        if isinstance(event_record, dict):
            rec = EventRecord.from_dict(event_record)
        elif isinstance(event_record, EventRecord):
            rec = event_record
        else:
            raise TypeError(f"Expected EventRecord or dict, got {type(event_record)}")

        store_file = cls.get_store_file(workspace_dir)
        os.makedirs(os.path.dirname(store_file), exist_ok=True)
        with open(store_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec.to_dict()) + "\n")
        return rec

    @classmethod
    def create_checkpoint(cls, state: Dict[str, Any], event_offset: int, workspace_dir: Optional[str] = None) -> None:
        """Creates a state checkpoint snapshot at a given event offset."""
        snapshot_file = cls.get_snapshot_file(workspace_dir)
        os.makedirs(os.path.dirname(snapshot_file), exist_ok=True)
        snapshot = {
            "snapshot_at": datetime.now(timezone.utc).isoformat() + "Z",
            "event_offset": event_offset,
            "state_snapshot": state
        }
        temp_file = f"{snapshot_file}.tmp.{os.getpid()}"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        os.replace(temp_file, snapshot_file)

    @classmethod
    def read_all_events(cls, workspace_dir: Optional[str] = None) -> List[EventRecord]:
        """Reads all EventRecord entries from the event store."""
        store_file = cls.get_store_file(workspace_dir)
        snapshot_file = cls.get_snapshot_file(workspace_dir)
        events: List[EventRecord] = []
        offset = 0

        if os.path.exists(snapshot_file):
            try:
                with open(snapshot_file, "r", encoding="utf-8") as sf:
                    snap_data = json.load(sf)
                    offset = snap_data.get("event_offset", 0)
            except Exception as ex:
                logger.warning(f"[EventStore] Snapshot read exception: {ex}")
                offset = 0

        if not os.path.exists(store_file):
            return events

        with open(store_file, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                line_str = line.strip()
                if line_str and idx >= offset:
                    d = json.loads(line_str)
                    rec = EventRecord.from_dict(d)
                    events.append(rec)
        return events
