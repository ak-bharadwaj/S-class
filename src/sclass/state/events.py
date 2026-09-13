"""
S-Class State: CloudEvents Event Journal.
Adopts CNCF CloudEvents v1.0.2 standard for normalized lifecycle and trust event journaling.
"""

from __future__ import annotations
import os
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Iterator

from sclass.storage.paths import WorkspacePaths
from sclass.storage.locks import WorkspaceLock


@dataclass(frozen=True)
class CloudEvent:
    """CNCF CloudEvents v1.0.2 normalized event envelope."""
    id: str
    source: str
    type: str
    time: str
    subject: str
    data: Dict[str, Any]
    specversion: str = "1.0.2"
    datacontenttype: str = "application/json"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "specversion": self.specversion,
            "id": self.id,
            "source": self.source,
            "type": self.type,
            "subject": self.subject,
            "time": self.time,
            "datacontenttype": self.datacontenttype,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CloudEvent:
        return cls(
            id=data["id"],
            source=data.get("source", "sclass.control_plane"),
            type=data["type"],
            subject=data.get("subject", ""),
            time=data.get("time", datetime.now(timezone.utc).isoformat()),
            specversion=data.get("specversion", "1.0.2"),
            datacontenttype=data.get("datacontenttype", "application/json"),
            data=data.get("data", {}),
        )

    @classmethod
    def create(
        cls,
        event_type: str,
        subject: str,
        data: Dict[str, Any],
        source: str = "sclass.control_plane",
    ) -> CloudEvent:
        """Factory method to emit standard CloudEvents."""
        return cls(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            source=source,
            type=event_type,
            subject=subject,
            time=datetime.now(timezone.utc).isoformat(),
            data=data,
        )


class EventJournal:
    """Append-only CloudEvents journal persisted in .sclass/events/journal.jsonl."""

    def __init__(self, workspace_dir: str):
        self.paths = WorkspacePaths(workspace_dir)
        self.paths.ensure_directories()
        self.journal_file = os.path.join(self.paths.events_dir, "journal.jsonl")

    def append(self, event_type: str, subject: str, data: Dict[str, Any], source: str = "sclass.control_plane") -> CloudEvent:
        """Atomically appends a CloudEvent to the journal."""
        event = CloudEvent.create(event_type=event_type, subject=subject, data=data, source=source)
        line = json.dumps(event.to_dict(), ensure_ascii=False) + "\n"

        with WorkspaceLock(self.paths.root, lock_name="journal"):
            with open(self.journal_file, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

        return event

    def read_all(self) -> List[CloudEvent]:
        """Reads all events from the journal."""
        if not os.path.exists(self.journal_file):
            return []
        events = []
        with open(self.journal_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(CloudEvent.from_dict(json.loads(line)))
        return events
