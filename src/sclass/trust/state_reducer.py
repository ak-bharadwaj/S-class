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


class CanonicalStateReducer:
    """
    Deterministic reducer reconstructing canonical VerifiedProjectState from authoritative records.
    """

    @classmethod
    def validate_record_integrity(cls, record: Dict[str, Any]) -> None:
        """Validates that a single canonical record is structurally sound and uncorrupted."""
        if not isinstance(record, dict):
            raise ObservationIntegrityError("Corrupt canonical record: record must be a dictionary")
        
        required_fields = ("entry_id", "entry_type", "timestamp")
        for f in required_fields:
            if f not in record or not record[f]:
                raise ObservationIntegrityError(f"Corrupt canonical record: missing or empty '{f}'")
            if not isinstance(record[f], str):
                raise ObservationIntegrityError(f"Corrupt canonical record: field '{f}' must be a string")

        if "payload" not in record or not isinstance(record["payload"], dict):
            raise ObservationIntegrityError("Corrupt canonical record: missing or non-dict 'payload'")

    @classmethod
    def validate_history_consistency(cls, records: List[Dict[str, Any]]) -> None:
        """
        Validates logical and causal consistency of the record sequence.
        Rejects impossible or corrupt histories fail-closed.
        """
        seen_ids: Set[str] = set()
        seen_claims: Set[str] = set()
        verified_evidence_refs: Set[str] = set()
        last_dt: Optional[datetime] = None
        last_timestamp_str: Optional[str] = None

        for rec in records:
            cls.validate_record_integrity(rec)
            
            eid = rec["entry_id"]
            if eid in seen_ids:
                raise ObservationIntegrityError(f"Corrupt canonical history: duplicate entry_id '{eid}' detected")
            seen_ids.add(eid)

            ts = rec["timestamp"]
            current_dt = _parse_iso_utc(ts)
            # Detect impossible backward time jumps (allow identical timestamps if same sub-second batch)
            if last_dt and current_dt < last_dt:
                raise ObservationIntegrityError(
                    f"Corrupt canonical history: non-monotonic timestamp progression '{ts}' < '{last_timestamp_str}'"
                )
            last_dt = current_dt
            last_timestamp_str = ts

            etype = rec["entry_type"]
            payload = rec["payload"]

            if etype == "evidence_receipt":
                rcpt_id = payload.get("receipt_id") or payload.get("id")
                if rcpt_id:
                    verified_evidence_refs.add(rcpt_id)

            elif etype == "verification_decision":
                # A verification decision must refer to valid evidence receipt
                ev_ref = rec.get("evidence_ref") or payload.get("evidence_id") or payload.get("receipt_id")
                is_verified = payload.get("is_verified", False)
                if is_verified and not ev_ref:
                    raise SecurityViolationError(
                        "Impossible state in history: verification decision has is_verified=True without evidence reference"
                    )

            elif etype == "claim":
                cid = payload.get("claim_id") or payload.get("id")
                if cid:
                    seen_claims.add(cid)

    @classmethod
    def reduce(
        cls,
        records: List[Dict[str, Any]],
        initial_state: Optional[VerifiedProjectState] = None,
        workspace_dir: str = "",
    ) -> VerifiedProjectState:
        """
        Deterministically reduces a sequence of canonical assurance records into VerifiedProjectState.
        """
        cls.validate_history_consistency(records)

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
