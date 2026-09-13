"""
S-Class Verification: Verification Engine.
Orchestrates claim-to-evidence verification, ledger provenance anchoring, and pluggable verifier evaluation.
"""

from __future__ import annotations
import os
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

from sclass.domain.claim import Claim
from sclass.domain.evidence import EvidenceReceipt, ProposedEvidence, ClaimedEvidence
from sclass.domain.verification import VerificationResult, VerificationEvent
from sclass.trust.ledger import LocalLedger
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
from sclass.verification.registry import get_verifier_registry


def check_staleness(evidence: EvidenceReceipt, workspace_dir: str) -> Tuple[bool, Optional[str]]:
    """Detects whether repository state was modified after the evidence was observed."""
    ws = os.path.abspath(workspace_dir)
    current_snapshot = compute_workspace_snapshot(ws)
    current_fp = compute_workspace_fingerprint(current_snapshot)

    recorded_fp = evidence.workspace_fingerprint
    if recorded_fp and current_fp != recorded_fp:
        return False, "Workspace files or content modified after observation."

    return True, None


def _update_hooks_verified(workspace_dir: str, agent: str = "") -> None:
    """Updates last_verified timestamp in .agents/sclass_hooks.json."""
    try:
        cfg_path = os.path.join(workspace_dir, ".agents", "sclass_hooks.json")
        if not os.path.exists(cfg_path):
            return
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        now_iso = datetime.now(timezone.utc).isoformat()
        if "last_verified" not in cfg or not isinstance(cfg["last_verified"], dict):
            cfg["last_verified"] = {}
        cfg["last_verified"][agent or "default"] = now_iso
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def _record_rejection(
    claim: Claim,
    reason: str,
    evidence: Optional[EvidenceReceipt],
    ledger: Optional[LocalLedger],
    exit_code: Optional[int] = None,
    failed_tests: int = 0,
) -> VerificationResult:
    r_id = getattr(evidence, "receipt_id", None)
    r_hash = getattr(evidence, "receipt_hash", "") or (evidence.compute_hash() if hasattr(evidence, "compute_hash") else "")
    ws_fp = getattr(evidence, "workspace_fingerprint", "") or ""
    prev_hash = ledger.get_last_hash() if (ledger and hasattr(ledger, "get_last_hash")) else "0" * 64

    event = None
    if evidence is not None:
        event = VerificationEvent(
            claim_id=claim.claim_id,
            receipt_id=r_id or "",
            receipt_hash=r_hash,
            verifier="sclass_engine",
            verification_time=datetime.now(timezone.utc).isoformat(),
            result="REJECT",
            reason=reason,
            repository_fingerprint=ws_fp,
            previous_ledger_hash=prev_hash,
        )

    res = VerificationResult(
        status="REJECT",
        claim_id=claim.claim_id,
        reason=reason,
        observed_exit_code=exit_code,
        failed_tests=failed_tests,
        receipt_id=r_id,
        verification_event=event,
    )
    if ledger:
        payload = res.to_dict()
        if event:
            payload.update(event.to_dict())
        ledger.append("rejection", payload)
    return res


def verify_claim(
    claim: Claim,
    evidence: Optional[EvidenceReceipt],
    workspace_dir: Optional[str] = None,
    ledger: Optional[LocalLedger] = None,
) -> VerificationResult:
    """
    Authoritatively verifies an agent claim against observed evidence.
    Returns VerificationResult (ACCEPT | REJECT | INVALID).
    """
    ws = os.path.abspath(workspace_dir or (evidence.workspace if evidence else os.getcwd()))
    if ledger is None:
        try:
            ledger = LocalLedger(workspace_dir=ws)
        except Exception:
            ledger = None

    if evidence is None:
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Agent claimed completion but produced no independently observed evidence receipt.",
            evidence=None,
            ledger=ledger,
        )

    if isinstance(evidence, (ProposedEvidence, ClaimedEvidence)) or getattr(evidence, "_explicitly_unobserved", False):
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Agent supplied proposed/claimed evidence, but verification requires an independently observed receipt.",
            evidence=evidence,
            ledger=ledger,
        )

    recorded_hash = getattr(evidence, "receipt_hash", None)
    if not recorded_hash:
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Missing evidence receipt hash. Authoritative receipt must have cryptographic receipt_hash.",
            evidence=evidence,
            ledger=ledger,
        )

    if recorded_hash != evidence.compute_hash():
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Evidence receipt hash mismatch. Tampering detected.",
            evidence=evidence,
            ledger=ledger,
        )

    # Universal provenance check against LocalLedger
    if ledger is None:
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Local ledger is required to verify observation provenance.",
            evidence=evidence,
            ledger=ledger,
        )

    is_chain_valid, chain_error = ledger.verify_integrity()
    if not is_chain_valid:
        return _record_rejection(
            claim=claim,
            reason=f"Claim rejected: Local ledger integrity compromised ({chain_error}). Evidence provenance cannot be established.",
            evidence=evidence,
            ledger=ledger,
        )

    matching_obs = None
    for entry in ledger.read_all_entries():
        if entry.get("event") == "OBSERVATION" and entry.get("payload", {}).get("receipt_id") == evidence.receipt_id:
            matching_obs = entry
            break

    if not matching_obs:
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Agent supplied unobserved or untrusted evidence. Provenance not found in local ledger (missing OBSERVATION event).",
            evidence=evidence,
            ledger=ledger,
        )

    obs_payload = matching_obs.get("payload", {})
    if obs_payload.get("receipt_hash") != recorded_hash:
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Receipt hash mismatch between evidence receipt and ledger OBSERVATION event. Tampering detected.",
            evidence=evidence,
            ledger=ledger,
        )

    # Check fingerprint consistency between receipt and ledger
    receipt_meta = evidence.metadata if isinstance(evidence.metadata, dict) else {}
    receipt_fp_before = receipt_meta.get("workspace_fingerprint_before")
    receipt_fp_after = getattr(evidence, "workspace_fingerprint", None) or receipt_meta.get("workspace_fingerprint")

    ledger_fp_before = obs_payload.get("fingerprint_before")
    ledger_fp_after = obs_payload.get("fingerprint_after")

    if not ledger_fp_before or not ledger_fp_after or not receipt_fp_before or not receipt_fp_after:
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Missing workspace fingerprints in evidence or ledger observation.",
            evidence=evidence,
            ledger=ledger,
        )

    if receipt_fp_before != ledger_fp_before or receipt_fp_after != ledger_fp_after:
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Workspace fingerprint mismatch between evidence receipt and ledger OBSERVATION event.",
            evidence=evidence,
            ledger=ledger,
        )

    # Check post-verification staleness
    is_fresh, stale_reason = check_staleness(evidence, ws)
    if not is_fresh:
        return _record_rejection(
            claim=claim,
            reason=f"Claim rejected: Evidence is stale. {stale_reason}",
            evidence=evidence,
            ledger=ledger,
        )

    # Select and invoke pluggable verifier
    registry = get_verifier_registry()
    verifier = registry.select(claim, evidence)
    verdict = verifier.verify(claim, evidence, ws)

    if verdict.is_rejected:
        return _record_rejection(
            claim=claim,
            reason=verdict.reason,
            evidence=evidence,
            ledger=ledger,
            exit_code=verdict.observed_exit_code,
            failed_tests=verdict.failed_tests,
        )

    # Emit VerificationEvent
    prev_hash = matching_obs.get("previous_hash") or ledger.get_last_hash()
    event = VerificationEvent(
        claim_id=claim.claim_id,
        receipt_id=evidence.receipt_id,
        receipt_hash=recorded_hash,
        verifier=verifier.verifier_id,
        verification_time=datetime.now(timezone.utc).isoformat(),
        result="CLAIM_VERIFIED",
        reason=verdict.reason,
        repository_fingerprint=evidence.workspace_fingerprint,
        previous_ledger_hash=prev_hash,
        metadata={"exit_code": evidence.exit_code, "agent": evidence.agent},
    )

    verdict.verification_event = event
    _update_hooks_verified(ws, evidence.agent)

    if ledger:
        event_dict = verdict.to_dict()
        event_dict.update(event.to_dict())
        ledger.append("verification", event_dict)

    return verdict
