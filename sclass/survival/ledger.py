"""
S-Class Survival v0: Tamper-Resistant Local Ledger (sclass/survival/ledger.py)

Implements Phase 7: Local append-only cryptographic ledger.
Minimum chain:
  event N: hash(event N)
  event N+1: hash(event N+1 + hash(event N))

Stored under .agents/ledger/audit_ledger.jsonl (SCLASS_ONLY authority).
"""

from __future__ import annotations
import os
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List


GENESIS_PREVIOUS_HASH = "0" * 64


class LocalLedger:
    """
    Cryptographic append-only local ledger.
    """

    def __init__(self, workspace_dir: Optional[str] = None, ledger_path: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        if ledger_path:
            self.ledger_file = ledger_path
        else:
            ledger_dir = os.path.join(self.workspace_dir, ".agents", "ledger")
            os.makedirs(ledger_dir, exist_ok=True)
            self.ledger_file = os.path.join(ledger_dir, "audit_ledger.jsonl")

    def _get_last_entry(self) -> Optional[Dict[str, Any]]:
        if not os.path.exists(self.ledger_file):
            return None
        last_line = ""
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if line_str:
                        last_line = line_str
            if last_line:
                return json.loads(last_line)
        except Exception:
            return None
        return None

    def append(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Appends a new cryptographically chained event to the local ledger."""
        last_entry = self._get_last_entry()
        if last_entry:
            seq = last_entry["sequence"] + 1
            prev_hash = last_entry["signature"]
        else:
            seq = 1
            prev_hash = GENESIS_PREVIOUS_HASH

        ts = datetime.now(timezone.utc).isoformat()
        payload_serialized = json.dumps(payload, sort_keys=True)
        payload_hash = hashlib.sha256(payload_serialized.encode("utf-8")).hexdigest()

        sig_content = f"{seq}:{event_type}:{prev_hash}:{payload_hash}:{ts}"
        sig = hashlib.sha256(sig_content.encode("utf-8")).hexdigest()

        entry = {
            "sequence": seq,
            "event": event_type,
            "previous_hash": prev_hash,
            "payload_hash": payload_hash,
            "timestamp": ts,
            "signature": sig,
            "payload": payload,
        }

        os.makedirs(os.path.dirname(os.path.abspath(self.ledger_file)), exist_ok=True)
        with open(self.ledger_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            f.flush()

        return entry

    def read_all_entries(self) -> List[Dict[str, Any]]:
        entries = []
        if not os.path.exists(self.ledger_file):
            return entries
        with open(self.ledger_file, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    entries.append(json.loads(line_str))
        return entries

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """
        Scans all ledger records from genesis and verifies the cryptographic chain.
        Returns (True, None) if valid, or (False, failure_reason) if tampered.
        """
        if not os.path.exists(self.ledger_file):
            return (True, None)

        expected_seq = 1
        expected_prev_hash = GENESIS_PREVIOUS_HASH

        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    line_str = line.strip()
                    if not line_str:
                        continue
                    entry = json.loads(line_str)

                    seq = entry.get("sequence")
                    event_type = entry.get("event")
                    prev_hash = entry.get("previous_hash")
                    p_hash = entry.get("payload_hash")
                    ts = entry.get("timestamp")
                    sig = entry.get("signature")
                    payload = entry.get("payload", {})

                    if seq != expected_seq:
                        return (False, f"Sequence discontinuity at line {line_no}: expected {expected_seq}, found {seq}")

                    if prev_hash != expected_prev_hash:
                        return (False, f"Chain break at sequence {seq}: previous_hash mismatch (expected {expected_prev_hash[:12]}..., got {prev_hash[:12]}...)")

                    computed_p_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
                    if computed_p_hash != p_hash:
                        return (False, f"Payload tampering at sequence {seq}: computed payload hash {computed_p_hash[:12]}... != recorded {p_hash[:12]}...")

                    sig_content = f"{seq}:{event_type}:{prev_hash}:{p_hash}:{ts}"
                    computed_sig = hashlib.sha256(sig_content.encode("utf-8")).hexdigest()
                    if computed_sig != sig:
                        return (False, f"Signature invalid at sequence {seq}: computed {computed_sig[:12]}... != recorded {sig[:12]}...")

                    expected_seq += 1
                    expected_prev_hash = sig

            return (True, None)

        except Exception as e:
            return (False, f"Ledger verification parse exception: {str(e)}")

