"""
S-Class V12: Promise Protocol & Completion Handshake (promise_protocol.py)

Parses structured <promise> tags from host agent outputs, validating completion
contracts before granting transition approvals.
- <promise>TASK-ID:DONE</promise>
- <promise>TASK-ID:BLOCKED:reason</promise>
- <promise>TASK-ID:DECIDE:question</promise>
"""

import re
import hmac
import hashlib
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger("sclass_promise_protocol")


class PromiseProtocol:
    """
    Parses and verifies agent <promise> contracts.
    """

    PROMISE_PATTERN = re.compile(r"<promise>(.*?)</promise>", re.DOTALL | re.IGNORECASE)

    @classmethod
    def parse_promise_tags(cls, text: str) -> List[Dict[str, Any]]:
        """Extracts all <promise> tags from a text stream."""
        results = []
        for match in cls.PROMISE_PATTERN.finditer(text):
            inner = match.group(1).strip()
            parts = inner.split(":", 2)

            if len(parts) == 1 and parts[0].upper() in ["DONE", "ALL_TASKS_COMPLETED"]:
                results.append({
                    "task_id": "GLOBAL",
                    "status": parts[0].upper(),
                    "payload": "",
                    "raw": inner,
                })
            elif len(parts) == 2:
                task_id, status = parts
                results.append({
                    "task_id": task_id.strip(),
                    "status": status.strip().upper(),
                    "payload": "",
                    "raw": inner,
                })
            elif len(parts) >= 3:
                task_id, status, payload = parts
                results.append({
                    "task_id": task_id.strip(),
                    "status": status.strip().upper(),
                    "payload": payload.strip(),
                    "raw": inner,
                })

        return results

    @classmethod
    def format_promise(cls, task_id: str, status: str = "DONE", payload: Optional[str] = None) -> str:
        """Helper to format a valid promise tag."""
        if payload:
            return f"<promise>{task_id}:{status.upper()}:{payload}</promise>"
        return f"<promise>{task_id}:{status.upper()}</promise>"

    @classmethod
    def sign_promise_receipt(cls, task_id: str, secret_key: bytes = b"sclass_v12_governance") -> str:
        """Signs an HMAC receipt for a satisfied promise."""
        ts = datetime.now(timezone.utc).isoformat()
        msg = f"{task_id}:{ts}".encode("utf-8")
        sig = hmac.new(secret_key, msg, hashlib.sha256).hexdigest()
        return f"RECEIPT:{task_id}:{ts}:{sig[:16]}"
