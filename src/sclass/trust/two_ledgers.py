"""
S-Class Trust: Separation of Execution Ledger and Assurance Ledger.
Enforces the fundamental architectural boundary:
Step-Code execution state != S-Class project truth.

Execution Ledger:
- Owned by the runtime harness.
- Records: operation lifecycles, tool states, provider states, sessions, subagents,
  retries, cancellation, replay states, execution results, raw telemetry.

Assurance Ledger:
- Owned by S-Class.
- Records: tasks, requirements, obligations, claims, verified evidence receipts,
  independent observations, verification assessments, invalidations, frontiers,
  recovery records, regression states, assurance receipts.

Absolute Invariant:
Execution Ledger -> directly mutates Assurance Truth is STRICTLY FORBIDDEN.
All truth promotions must proceed through independent observation and verification.
"""

from __future__ import annotations
import os
import json
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union

from sclass.storage.paths import WorkspacePaths
from sclass.storage.locks import WorkspaceLock
from sclass.execution.operations import DurableOperation
from sclass.execution.events import RuntimeEvent
from sclass.core.errors import SecurityViolationError


class ExecutionLedger:
    """
    Runtime-owned ledger recording execution facts, tool calls, and lifecycle events.
    Execution state represents what the runtime believes happened, NOT project truth.
    """

    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.paths = WorkspacePaths(self.workspace_dir)
        self.paths.ensure_directories()
        self.ledger_path = os.path.join(self.paths.trust_dir, "execution_ledger.jsonl")
        self._entries: List[Dict[str, Any]] = []

    def append_entry(self, entry_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with WorkspaceLock(self.workspace_dir, lock_name="execution_ledger"):
            now_iso = datetime.now(timezone.utc).isoformat()
            entry_id = f"exec_{uuid.uuid4().hex[:12]}"
            entry = {
                "entry_id": entry_id,
                "entry_type": entry_type,
                "timestamp": now_iso,
                "payload": payload,
            }
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            self._entries.append(entry)
            return entry

    def record_operation(self, op: DurableOperation) -> Dict[str, Any]:
        return self.append_entry("operation_lifecycle", op.to_dict())

    def record_tool_call(self, tool: str, action: str, target: str, result: Dict[str, Any]) -> Dict[str, Any]:
        return self.append_entry("tool_call", {
            "tool": tool,
            "action": action,
            "target": target,
            "result": result,
        })

    def record_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        return self.append_entry("session_state", session)

    def record_runtime_event(self, event: RuntimeEvent) -> Dict[str, Any]:
        return self.append_entry("runtime_event", event.to_dict())

    def get_entries(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.ledger_path):
            return list(self._entries)
        entries: List[Dict[str, Any]] = []
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line.strip()))
        return entries


class AssuranceLedger:
    """
    S-Class-owned ledger recording verified technical obligations, claims,
    authoritative evidence, independent observations, and canonical truth state.
    """

    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.paths = WorkspacePaths(self.workspace_dir)
        self.paths.ensure_directories()
        self.ledger_path = os.path.join(self.paths.trust_dir, "assurance_ledger.jsonl")
        self._entries: List[Dict[str, Any]] = []

    def append_entry(self, entry_type: str, payload: Dict[str, Any], evidence_ref: Optional[str] = None) -> Dict[str, Any]:
        with WorkspaceLock(self.workspace_dir, lock_name="assurance_ledger"):
            now_iso = datetime.now(timezone.utc).isoformat()
            entry_id = f"assure_{uuid.uuid4().hex[:12]}"

            if os.path.exists(self.ledger_path):
                self._entries = self.get_entries()
            else:
                self._entries = []

            prev_entry = self._entries[-1] if self._entries else None
            sequence = (prev_entry.get("sequence", 0) + 1) if prev_entry else 1
            previous_record_hash = prev_entry.get("record_hash", "0" * 64) if prev_entry else ("0" * 64)

            payload_str = json.dumps(payload, sort_keys=True)
            hash_input = f"{sequence}|{entry_id}|{entry_type}|{now_iso}|{previous_record_hash}|{payload_str}"
            record_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

            import hmac
            from sclass.policy.authorization_service import get_authorization_secret
            secret = get_authorization_secret()
            writer_id = "sclass_assurance_writer"
            schema_version = "1.0.0"
            auth_input = f"{record_hash}|{writer_id}|{schema_version}"
            authenticator = hmac.new(secret, auth_input.encode("utf-8"), hashlib.sha256).hexdigest()

            entry = {
                "entry_id": entry_id,
                "entry_type": entry_type,
                "sequence": sequence,
                "previous_record_hash": previous_record_hash,
                "record_hash": record_hash,
                "authenticator": authenticator,
                "writer_id": writer_id,
                "schema_version": schema_version,
                "timestamp": now_iso,
                "evidence_ref": evidence_ref,
                "payload": payload,
            }
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            self._entries.append(entry)
            return entry

    def record_obligation(self, obligation: Dict[str, Any]) -> Dict[str, Any]:
        return self.append_entry("obligation", obligation)

    def record_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        return self.append_entry("claim", claim)

    def record_observation(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        return self.append_entry("observation", observation)

    def record_evidence(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        rcpt_id = receipt.get("receipt_id") or receipt.get("id")
        return self.append_entry("evidence_receipt", receipt, evidence_ref=rcpt_id)

    def record_verification(self, verification_result: Dict[str, Any]) -> Dict[str, Any]:
        rcpt_id = verification_result.get("evidence_id")
        return self.append_entry("verification_decision", verification_result, evidence_ref=rcpt_id)

    def record_invalidation(self, invalidation: Dict[str, Any]) -> Dict[str, Any]:
        return self.append_entry("invalidation", invalidation)

    def record_frontier(self, frontier: Dict[str, Any]) -> Dict[str, Any]:
        return self.append_entry("frontier_update", frontier)

    def record_assurance_receipt(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        return self.append_entry("assurance_receipt", receipt)

    def direct_mutate_from_execution_ledger(self, raw_execution_payload: Dict[str, Any]) -> None:
        """
        ENFORCES ARCHITECTURAL LAW:
        Execution Ledger -> directly mutates Assurance Truth is strictly forbidden.
        """
        raise SecurityViolationError(
            "ARCHITECTURAL INVARIANT VIOLATION: Execution Ledger cannot directly mutate Assurance Truth. "
            "Execution records represent untrusted candidate signals. All truth state mutations must pass "
            "through independent observation and authoritative verifier assessment."
        )

    def get_entries(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.ledger_path):
            return list(self._entries)
        entries: List[Dict[str, Any]] = []
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line.strip()))
        return entries
