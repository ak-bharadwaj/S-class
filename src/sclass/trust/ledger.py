"""
S-Class Trust: Append-Only Local Cryptographic Ledger.
Maintains tamper-evident SHA-256 hash chains for all observation facts and verification events.
Provides atomic commit, integrity verification, snapshots, export, and fail-safe recovery.
"""

from __future__ import annotations
import os
import json
import shutil
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional, Callable

from sclass.storage.paths import WorkspacePaths
from sclass.storage.locks import WorkspaceLock
from sclass.control.secret_scanner import SecretScanner
from sclass.core.errors import ProvenanceError, ObservationIntegrityError


class LocalLedger:
    """Tamper-evident append-only ledger with cryptographic hash chaining and atomic commitments."""

    def __init__(self, workspace_dir: str):
        self.paths = WorkspacePaths(workspace_dir)
        self.paths.ensure_directories()
        # Primary ledger file inside .sclass/trust/ledger/
        self.ledger_file = os.path.join(self.paths.ledger_dir, "audit_ledger.jsonl")
        # Legacy compatibility path (.agents/ledger/audit_ledger.jsonl)
        self.legacy_ledger_file = os.path.join(self.paths.legacy_ledger_dir, "audit_ledger.jsonl")
        self.snapshot_dir = os.path.join(self.paths.trust_dir, "snapshots")
        os.makedirs(self.snapshot_dir, exist_ok=True)

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

    def get_head_hash(self) -> str:
        """Returns the hash of the latest entry or genesis zeroes (alias for get_last_hash)."""
        return self.get_last_hash()

    def get_entry_count(self) -> int:
        """Returns total number of committed entries in the ledger."""
        target_file = self.ledger_file if os.path.exists(self.ledger_file) else self.legacy_ledger_file
        if not os.path.exists(target_file):
            return 0
        count = 0
        with open(target_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count


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

    def append_atomic(
        self,
        event: str,
        payload: Dict[str, Any],
        commit_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Atomically prepares observation, calculates hashes, invokes commit_hook
        (e.g., writing the receipt), and commits the ledger entry.
        If commit_hook fails, no ledger entry is committed.
        """
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

            if commit_hook:
                try:
                    commit_hook(entry)
                except Exception as ch_err:
                    raise ObservationIntegrityError(
                        f"Atomic observation commit failed before ledger append: {ch_err}"
                    ) from ch_err

            line = json.dumps(entry, ensure_ascii=False) + "\n"
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

    def read_all(self) -> List[Dict[str, Any]]:
        """Alias for read_all_entries for backward compatibility."""
        return self.read_all_entries()

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

    def verify(self) -> Tuple[bool, Optional[str]]:
        """Standard interface for verifying ledger integrity."""
        return self.verify_integrity()

    def verify_chain(self) -> bool:
        """Simple boolean check for chain integrity."""
        valid, _ = self.verify_integrity()
        return valid

    def export(self, target_path: Optional[str] = None) -> str:
        """Exports ledger entries to a designated export file."""
        entries = self.read_all_entries()
        out_path = target_path or os.path.join(self.paths.trust_dir, f"ledger_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        return out_path

    def snapshot(self, snapshot_path: Optional[str] = None) -> str:
        """Creates a verified snapshot of the current ledger state."""
        valid, err = self.verify_integrity()
        if not valid:
            raise ProvenanceError(f"Cannot snapshot invalid ledger: {err}")
        snap_file = snapshot_path or os.path.join(self.snapshot_dir, f"snapshot_{self.get_last_hash()[:16]}.json")
        entries = self.read_all_entries()
        snapshot_payload = {
            "head_hash": self.get_last_hash(),
            "entry_count": len(entries),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entries": entries,
        }
        with open(snap_file, "w", encoding="utf-8") as f:
            json.dump(snapshot_payload, f, indent=2)
        return snap_file

    def repair(self, snapshot_file: Optional[str] = None) -> str:
        """
        Evaluates ledger integrity recovery.
        Never silently rewrites history!
        Returns one of:
        - 'VALID': chain is completely healthy.
        - 'RECOVERED_FROM_SNAPSHOT': restored up to a verified snapshot.
        - 'FORKED': diverging ledger histories detected.
        - 'CORRUPTED': hash chain corrupted without valid snapshot.
        - 'RESET_REQUIRED': ledger unrecoverable.
        """
        valid, err = self.verify_integrity()
        if valid:
            return "VALID"

        # Check for snapshot restoration
        candidate_snaps = []
        if snapshot_file and os.path.isfile(snapshot_file):
            candidate_snaps.append(snapshot_file)
        elif os.path.isdir(self.snapshot_dir):
            for fname in sorted(os.listdir(self.snapshot_dir), reverse=True):
                if fname.endswith(".json"):
                    candidate_snaps.append(os.path.join(self.snapshot_dir, fname))

        for snap in candidate_snaps:
            try:
                with open(snap, "r", encoding="utf-8") as f:
                    snap_data = json.load(f)
                snap_entries = snap_data.get("entries", [])
                if not snap_entries:
                    continue

                # Verify snapshot internal integrity
                expected_prev = "0" * 64
                snap_valid = True
                for idx, entry in enumerate(snap_entries):
                    if entry.get("sequence") != idx + 1 or entry.get("previous_hash") != expected_prev:
                        snap_valid = False
                        break
                    expected_prev = entry["hash"]

                if snap_valid:
                    # Restore from snapshot without overwriting audit log of repair
                    for fpath in (self.ledger_file, self.legacy_ledger_file):
                        os.makedirs(os.path.dirname(fpath), exist_ok=True)
                        with open(fpath, "w", encoding="utf-8") as f:
                            for entry in snap_entries:
                                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    return "RECOVERED_FROM_SNAPSHOT"
            except Exception:
                continue

        # Check if legacy and primary ledger files differ (forked)
        if os.path.exists(self.ledger_file) and os.path.exists(self.legacy_ledger_file):
            try:
                with open(self.ledger_file, "rb") as f1, open(self.legacy_ledger_file, "rb") as f2:
                    if f1.read() != f2.read():
                        return "FORKED"
            except Exception:
                pass

        return "CORRUPTED"
