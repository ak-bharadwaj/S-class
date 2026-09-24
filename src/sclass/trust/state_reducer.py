"""
S-Class Trust: Canonical State Reducer (Section 12 / Part C4).
Implements the deterministic recovery reducer pattern:
canonical records -> consistency validation -> deterministic reconstruction -> current state.

Invariants:
1. Impossible, corrupt, or tampered histories must be rejected fail-closed, not guessed through.
2. Given identical canonical history, reconstructed state is 100% deterministic.
3. Execution plane cannot directly establish assurance state.
"""

from __future__ import annotations
import os
import json
import hmac
import hashlib
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timezone

from sclass.domain.project import VerifiedProjectState
from sclass.domain.claim import ClaimType, ClaimStatus
from sclass.domain.obligations import ObligationStatus
from sclass.core.errors import ObservationIntegrityError, SecurityViolationError


def _parse_iso_utc(ts: str) -> datetime:
    clean = (ts or "").strip()
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception as e:
        raise ObservationIntegrityError(f"Corrupt canonical record: invalid timestamp format '{ts}': {e}")


_KNOWN_RECORD_TYPES: Set[str] = {
    "obligation",
    "claim",
    "evidence_receipt",
    "verification_decision",
    "invalidation",
    "frontier_update",
    "regression",
    "assumption",
    "evolution_assessment",
}


class CanonicalStateReducer:
    """
    Deterministic reducer reconstructing canonical VerifiedProjectState from authoritative records.
    """

    @classmethod
    def validate_record_integrity(cls, record: Dict[str, Any], require_authentication: bool = True) -> None:
        """Validates that a single canonical record is structurally sound and uncorrupted."""
        if not isinstance(record, dict):
            raise ObservationIntegrityError("Corrupt canonical record: record must be a dictionary")
        
        required_fields = ["entry_id", "entry_type", "timestamp"]
        if require_authentication:
            required_fields.extend(["sequence", "previous_record_hash", "record_hash", "authenticator", "writer_id", "schema_version"])

        for f in required_fields:
            if f not in record or record[f] is None or record[f] == "":
                raise ObservationIntegrityError(f"Corrupt canonical record: missing or empty '{f}'")
            if f == "sequence":
                if not isinstance(record[f], int):
                    raise ObservationIntegrityError(f"Corrupt canonical record: field '{f}' must be an integer")
            else:
                if not isinstance(record[f], str):
                    raise ObservationIntegrityError(f"Corrupt canonical record: field '{f}' must be a string")

        etype = record.get("entry_type")
        if etype not in _KNOWN_RECORD_TYPES:
            raise ObservationIntegrityError(f"Corrupt canonical record: unknown record type '{etype}'")

        if "payload" not in record or not isinstance(record["payload"], dict):
            raise ObservationIntegrityError("Corrupt canonical record: missing or non-dict 'payload'")

    @classmethod
    def validate_history_consistency(
        cls,
        records: List[Dict[str, Any]],
        expected_workspace: Optional[str] = None,
        expected_task_id: Optional[str] = None,
        require_authentication: bool = True,
    ) -> None:
        """
        Validates logical, cryptographic, and causal consistency of the record sequence.
        Rejects impossible or corrupt histories fail-closed.
        """
        seen_ids: Set[str] = set()
        seen_claims: Set[str] = set()
        seen_sequences: Set[int] = set()
        verified_evidence_refs: Set[str] = set()
        last_dt: Optional[datetime] = None
        last_timestamp_str: Optional[str] = None
        expected_prev_hash: Optional[str] = None

        for rec in records:
            cls.validate_record_integrity(rec, require_authentication=require_authentication)
            
            eid = rec["entry_id"]
            if eid in seen_ids:
                raise ObservationIntegrityError(f"Corrupt canonical history: duplicate entry_id '{eid}' detected")
            seen_ids.add(eid)

            # Sequence verification (Section 10)
            seq = rec.get("sequence") or rec.get("sequence_number")
            if seq is not None:
                if seq in seen_sequences:
                    raise ObservationIntegrityError(f"Corrupt canonical history: duplicate sequence number '{seq}' detected")
                seen_sequences.add(seq)
            elif require_authentication:
                raise ObservationIntegrityError(f"Corrupt canonical history: missing sequence number on '{eid}'")

            # Hash chain verification (Section 9 & 10)
            prev_hash = rec.get("previous_record_hash")
            rec_hash = rec.get("record_hash")
            if prev_hash is not None and expected_prev_hash is not None:
                if prev_hash != expected_prev_hash:
                    raise ObservationIntegrityError(
                        f"Corrupt canonical history: broken hash chain. Expected previous '{expected_prev_hash}', got '{prev_hash}'"
                    )
            if rec_hash is not None:
                expected_prev_hash = rec_hash

            # Record hash content verification
            if rec_hash is not None and seq is not None and prev_hash is not None:
                payload_str = json.dumps(rec.get("payload", {}), sort_keys=True)
                calc_hash = hashlib.sha256(
                    f"{seq}|{eid}|{rec.get('entry_type')}|{rec.get('timestamp')}|{prev_hash}|{payload_str}".encode("utf-8")
                ).hexdigest()
                if not hmac.compare_digest(rec_hash, calc_hash):
                    raise ObservationIntegrityError(
                        f"Corrupt canonical record '{eid}': record_hash does not match content hash"
                    )

            # HMAC Authenticator verification (if present or required)
            auth = rec.get("authenticator")
            if auth is not None and rec_hash:
                writer = rec.get("writer_id", "sclass_assurance_writer")
                s_ver = rec.get("schema_version", "1.0.0")
                from sclass.policy.authorization_service import get_authorization_secret
                secret = get_authorization_secret()
                expected_auth = hmac.new(
                    secret, f"{rec_hash}|{writer}|{s_ver}".encode("utf-8"), hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(auth, expected_auth):
                    raise SecurityViolationError(
                        f"Tampered canonical record '{eid}': HMAC authenticator verification failed"
                    )
            elif require_authentication:
                raise SecurityViolationError(
                    f"Unauthenticated canonical record '{eid}': missing mandatory HMAC authenticator"
                )

            ts = rec["timestamp"]
            current_dt = _parse_iso_utc(ts)
            # Detect impossible backward time jumps
            if last_dt and current_dt < last_dt:
                raise ObservationIntegrityError(
                    f"Corrupt canonical history: non-monotonic timestamp progression '{ts}' < '{last_timestamp_str}'"
                )

            # Future timestamp drift allowance (300 seconds)
            drift_seconds = (current_dt - datetime.now(timezone.utc)).total_seconds()
            if drift_seconds > 300.0:
                raise ObservationIntegrityError(
                    f"Corrupt canonical record: future timestamp '{ts}' exceeds 300s drift allowance (drift={drift_seconds:.1f}s)"
                )

            last_dt = current_dt
            last_timestamp_str = ts

            etype = rec["entry_type"]
            payload = rec["payload"]

            # Workspace / Task ID binding verification
            if expected_workspace:
                rec_ws = rec.get("workspace_id") or payload.get("workspace_id") or payload.get("workspace")
                if rec_ws and os.path.normpath(rec_ws).lower() != os.path.normpath(expected_workspace).lower():
                    raise ObservationIntegrityError(
                        f"Workspace mismatch in canonical record '{eid}': '{rec_ws}' != '{expected_workspace}'"
                    )

            if expected_task_id:
                rec_task = rec.get("task_id") or payload.get("task_id")
                if rec_task and rec_task != expected_task_id:
                    raise ObservationIntegrityError(
                        f"Task mismatch in canonical record '{eid}': '{rec_task}' != '{expected_task_id}'"
                    )

            if etype == "evidence_receipt":
                rcpt_id = payload.get("receipt_id") or payload.get("id")
                if rcpt_id:
                    verified_evidence_refs.add(rcpt_id)

            elif etype == "verification_decision":
                # A verification decision must refer to valid evidence receipt
                ev_ref = rec.get("evidence_ref") or payload.get("evidence_id") or payload.get("receipt_id")
                is_verified = payload.get("is_verified", False)
                if is_verified:
                    if not ev_ref or ev_ref not in verified_evidence_refs:
                        raise SecurityViolationError(
                            f"Impossible state in history: verification decision has is_verified=True without valid evidence reference '{ev_ref}'"
                        )

            elif etype == "claim":
                cid = payload.get("claim_id") or payload.get("id")
                if cid:
                    if cid in seen_claims:
                        raise ObservationIntegrityError(
                            f"Corrupt canonical history: duplicate claim declaration '{cid}' detected"
                        )
                    seen_claims.add(cid)

    @classmethod
    def reduce(
        cls,
        records: List[Dict[str, Any]],
        initial_state: Optional[VerifiedProjectState] = None,
        workspace_dir: str = "",
        require_authentication: Optional[bool] = None,
    ) -> VerifiedProjectState:
        """
        Deterministically reduces a sequence of canonical assurance records into VerifiedProjectState.
        """
        if require_authentication is None:
            require_authentication = (
                os.environ.get("SCLASS_STRICT_SECURITY") == "1"
                or os.environ.get("SCLASS_ENVIRONMENT") == "production"
                or any(r.get("sequence") is not None for r in records)
            )
        cls.validate_history_consistency(
            records,
            expected_workspace=workspace_dir if workspace_dir else None,
            require_authentication=require_authentication,
        )

        state = initial_state or VerifiedProjectState(workspace=workspace_dir)

        for rec in records:
            etype = rec["entry_type"]
            payload = rec["payload"]

            if etype == "obligation":
                state.add_obligation(payload)

            elif etype == "claim":
                state.record_pending_verification(payload)

            elif etype == "evidence_receipt":
                if payload not in state.evidence:
                    state.evidence.append(dict(payload))

            elif etype == "verification_decision":
                claim_id = payload.get("claim_id")
                is_verified = payload.get("is_verified", False)
                if is_verified and claim_id:
                    # Find receipt
                    rcpt_id = rec.get("evidence_ref") or payload.get("evidence_id")
                    matching_rcpt = next((e for e in state.evidence if (e.get("receipt_id") == rcpt_id or e.get("id") == rcpt_id)), None)
                    claim_obj = {
                        "claim_id": claim_id,
                        "task_id": payload.get("task_id", ""),
                        "statement": payload.get("statement", payload.get("summary", "")),
                        "claim_type": payload.get("claim_type", ClaimType.CORRECTNESS.value),
                    }
                    state.record_verified_claim(claim_obj, receipt=matching_rcpt)
                elif not is_verified and claim_id:
                    state.record_rejected_claim(claim_id)

            elif etype == "invalidation":
                cid = payload.get("claim_id")
                reason = payload.get("reason", "Invalidated by state record")
                if cid:
                    state.record_invalidated_claim(cid, reason=reason)

            elif etype == "frontier_update":
                frontier_items = payload.get("frontier", [])
                if isinstance(frontier_items, list):
                    state.update_frontier(frontier_items)

            elif etype == "regression":
                state.record_regression(payload)

            elif etype == "assumption":
                stmt = payload.get("statement", "")
                meta = payload.get("metadata", {})
                state.record_assumption(stmt, metadata=meta)

        return state
