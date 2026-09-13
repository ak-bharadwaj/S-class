"""
S-Class Trust: Append-Only Local Cryptographic Ledger.
Maintains tamper-evident SHA-256 hash chains for all observation facts and verification events.
"""

from __future__ import annotations
import os
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional

from sclass.storage.paths import WorkspacePaths
from sclass.storage.locks import WorkspaceLock
from sclass.control.secret_scanner import SecretScanner
from sclass.core.errors import ProvenanceError


class LocalLedger:
    """Tamper-evident append-only ledger with cryptographic hash chaining."""

    def __init__(self, workspace_dir: str):
        self.paths = WorkspacePaths(workspace_dir)
        self.paths.ensure_directories()
        # Primary ledger file inside .sclass/trust/ledger/
        self.ledger_file = os.path.join(self.paths.ledger_dir, "audit_ledger.jsonl")
        # Legacy compatibility path (.agents/ledger/audit_ledger.jsonl)
        self.legacy_ledger_file = os.path.join(self.paths.legacy_ledger_dir, "audit_ledger.jsonl")

    def _compute_entry_hash(self, sequence: int, event: str, prev_hash: str, payload_hash: str, timestamp: str) -> str:
        data = f"{sequence}:{event}:{prev_hash}:{payload_hash}:{timestamp}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def _compute_payload_hash(self, payload: Dict[str, Any]) -> str:
        clean_str = SecretScanner.redact(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        return hashlib.sha256(clean_str.encode("utf-8")).hexdigest()

    def get_last_entry(self) -> Optional[Dict[str, Any]]:
        """Reads the last recorded entry in the ledger."""
        target_file = self.ledger_file if os.path.exists(self.ledger_file) else self.legacy_ledger_file
        if not os.path.exists(target_file):
            return None
        last_line = None
        with open(target_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line.strip()
        return json.loads(last_line) if last_line else None

    def get_last_hash(self) -> str:
        """Returns the hash of the latest entry or genesis zeroes."""
        last = self.get_last_entry()
        return last["hash"] if last else "0" * 64

    def append(self, event: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Appends a new event and anchors its hash in the ledger."""
        with WorkspaceLock(self.paths.root, lock_name="ledger"):
            last = self.get_last_entry()
            seq = (last["sequence"] + 1) if last else 1
            prev_hash = last["hash"] if last else "0" * 64
            now_iso = datetime.now(timezone.utc).isoformat()
            p_hash = self._compute_payload_hash(payload)
            entry_hash = self._compute_entry_hash(seq, event, prev_hash, p_hash, now_iso)

            clean_payload_str = SecretScanner.redact(json.dumps(payload, ensure_ascii=False))
            clean_payload = json.loads(clean_payload_str)

            entry = {
                "sequence": seq,
                "event": event,
                "previous_hash": prev_hash,
                "payload_hash": p_hash,
                "timestamp": now_iso,
                "payload": clean_payload,
                "hash": entry_hash,
            }

            line = json.dumps(entry, ensure_ascii=False) + "\n"

            # Write to both .sclass/ and .agents/ for backward compatibility
            for fpath in (self.ledger_file, self.legacy_ledger_file):
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, "a", encoding="utf-8") as f:
                    f.write(line)
                    f.flush()
                    os.fsync(f.fileno())

            return entry

    def read_all_entries(self) -> List[Dict[str, Any]]:
        """Reads all entries in the ledger."""
        target_file = self.ledger_file if os.path.exists(self.ledger_file) else self.legacy_ledger_file
        if not os.path.exists(target_file):
            return []
        entries = []
        with open(target_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line.strip()))
        return entries

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """Verifies the entire cryptographic hash chain of the ledger."""
        entries = self.read_all_entries()
        if not entries:
            return True, None

        expected_prev = "0" * 64
        for idx, entry in enumerate(entries):
            expected_seq = idx + 1
            if entry.get("sequence") != expected_seq:
                return False, f"Broken sequence at index {idx}: expected {expected_seq}, got {entry.get('sequence')}"

            if entry.get("previous_hash") != expected_prev:
                return False, f"Broken previous_hash chain at sequence {entry.get('sequence')}"

            calc_payload_hash = self._compute_payload_hash(entry.get("payload", {}))
            if entry.get("payload_hash") != calc_payload_hash:
                return False, f"Payload hash mismatch at sequence {entry.get('sequence')}"

            calc_hash = self._compute_entry_hash(
                entry["sequence"],
                entry["event"],
                entry["previous_hash"],
                entry["payload_hash"],
                entry["timestamp"],
            )
            if entry.get("hash") != calc_hash:
                return False, f"Entry hash mismatch at sequence {entry.get('sequence')}"

            expected_prev = entry["hash"]

        return True, None

    def verify_chain(self) -> bool:
        """Simple boolean check for chain integrity."""
        valid, _ = self.verify_integrity()
        return valid
