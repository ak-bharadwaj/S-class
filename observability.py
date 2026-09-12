"""
S-Class V12: Structured Observability & Audit Trace Engine (observability.py)

Zero-cloud structured JSON logging. Records append-only audit traces to
.agents/audit_trace.jsonl for complete epistemic provenance and post-mortem analysis.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger("sclass_observability")


class LocalAuditLogger:
    """
    Append-only JSONL audit tracer for S-Class control plane operations.
    """

    DEFAULT_TRACE_FILE = os.path.join(".agents", "audit_trace.jsonl")

    @classmethod
    def log_event(
        cls,
        event_type: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
        workspace_dir: Optional[str] = None,
        level: str = "INFO",
    ) -> Dict[str, Any]:
        """Appends a structured event entry to the JSONL trace log."""
        cwd = workspace_dir or os.getcwd()
        trace_path = os.path.join(cwd, cls.DEFAULT_TRACE_FILE)
        os.makedirs(os.path.dirname(trace_path), exist_ok=True)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.upper(),
            "event_type": event_type,
            "message": message,
            "payload": payload or {},
        }

        try:
            with open(trace_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning(f"Failed to append to audit trace: {e}")

        return entry

    @classmethod
    def get_recent_traces(
        cls,
        limit: int = 50,
        workspace_dir: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Reads the most recent audit trace entries."""
        cwd = workspace_dir or os.getcwd()
        trace_path = os.path.join(cwd, cls.DEFAULT_TRACE_FILE)
        if not os.path.exists(trace_path):
            return []

        entries = []
        try:
            with open(trace_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line_str = line.strip()
                    if line_str:
                        try:
                            entries.append(json.loads(line_str))
                        except json.JSONDecodeError:
                            continue
        except Exception:
            return []

        return entries[-limit:]
