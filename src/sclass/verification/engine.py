"""
S-Class Verification: Verification Engine.
Orchestrates claim-to-evidence verification, ledger provenance anchoring,
claim acceptance matrix evaluation, and pluggable verifier execution.
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
from sclass.verification.acceptance import ClaimAcceptanceMatrix
from sclass.verification.state_machine import VerificationState, VerificationStateMachine


def check_staleness(evidence: Any, workspace_dir: str) -> Tuple[bool, Optional[str]]:
    """Detects whether repository state was modified after the evidence was observed."""
    ws = os.path.abspath(workspace_dir)

    if hasattr(evidence, "validate_dependencies") and callable(evidence.validate_dependencies):
        is_valid, dep_reason = evidence.validate_dependencies(ws)
        if not is_valid:
            if hasattr(evidence, "state_machine") and getattr(evidence.state_machine, "current_state", None) == VerificationState.ACCEPTED:
                try:
                    evidence.state_machine.transition_to(VerificationState.INVALIDATED, reason="Workspace mutation detected")
                except Exception:
                    pass
            return False, dep_reason or "Workspace files or content modified after observation."

    current_snapshot = compute_workspace_snapshot(ws)
    current_fp = compute_workspace_fingerprint(current_snapshot)

    recorded_fp = getattr(evidence, "workspace_fingerprint", None)
    if recorded_fp and current_fp != recorded_fp:
        if hasattr(evidence, "state_machine") and getattr(evidence.state_machine, "current_state", None) == VerificationState.ACCEPTED:
            try:
                evidence.state_machine.transition_to(VerificationState.INVALIDATED, reason="Workspace mutation detected")
            except Exception:
                pass
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
    evidence: Optional[Any],
    ledger: Optional[LocalLedger],
    exit_code: Optional[int] = None,
    failed_tests: int = 0,
    state_machine: Optional[VerificationStateMachine] = None,
) -> VerificationResult:
    r_id = getattr(evidence, "receipt_id", None)
    r_hash = getattr(evidence, "receipt_hash", "") or (evidence.compute_hash() if hasattr(evidence, "compute_hash") else "")
    ws_fp = getattr(evidence, "workspace_fingerprint", "") or ""
    prev_hash = ledger.get_last_hash() if (ledger and hasattr(ledger, "get_last_hash")) else "0" * 64

    if state_machine:
        try:
            state_machine.transition_to(VerificationState.REJECTED, reason=reason)
        except Exception:
            pass

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
        verification_state="REJECTED",
        state_machine=state_machine,
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
    evidence: Optional[Any],
    workspace_dir: Optional[str] = None,
    ledger: Optional[LocalLedger] = None,
) -> VerificationResult:
    """
    Authoritatively verifies an agent claim against observed evidence.
    Returns VerificationResult (ACCEPT | REJECT | INVALID | INCONCLUSIVE).
    """
    sm = getattr(claim, "state_machine", None) or VerificationStateMachine(
        initial_state=VerificationState.CLAIMED,
        claim_id=claim.claim_id,
    )
    try:
        sm.transition_to(VerificationState.EVIDENCE_REQUIRED, reason="Evaluating provided evidence")
    except Exception:
        pass

    ws = os.path.abspath(workspace_dir or (getattr(evidence, "workspace", None) if evidence else os.getcwd()))
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
            state_machine=sm,
        )

    if isinstance(evidence, (ProposedEvidence, ClaimedEvidence)) or getattr(evidence, "_explicitly_unobserved", False):
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Agent supplied proposed/claimed evidence, but verification requires an independently observed receipt.",
            evidence=evidence,
            ledger=ledger,
            state_machine=sm,
        )

    recorded_hash = getattr(evidence, "receipt_hash", None)
    if not recorded_hash:
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Missing evidence receipt hash. Authoritative receipt must have cryptographic receipt_hash.",
            evidence=evidence,
            ledger=ledger,
            state_machine=sm,
        )

    if hasattr(evidence, "compute_hash") and recorded_hash != evidence.compute_hash():
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Evidence receipt hash mismatch. Tampering detected.",
            evidence=evidence,
            ledger=ledger,
            state_machine=sm,
        )

    # Universal provenance check against LocalLedger
    if ledger is None:
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Local ledger is required to verify observation provenance.",
            evidence=evidence,
            ledger=ledger,
            state_machine=sm,
        )

    is_chain_valid, chain_error = ledger.verify_integrity()
    if not is_chain_valid:
        return _record_rejection(
            claim=claim,
            reason=f"Claim rejected: Local ledger integrity compromised ({chain_error}). Evidence provenance cannot be established.",
            evidence=evidence,
            ledger=ledger,
            state_machine=sm,
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
            state_machine=sm,
        )

    obs_payload = matching_obs.get("payload", {})
    if obs_payload.get("receipt_hash") != recorded_hash:
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Receipt hash mismatch between evidence receipt and ledger OBSERVATION event. Tampering detected.",
            evidence=evidence,
            ledger=ledger,
            state_machine=sm,
        )

    # Check fingerprint consistency between receipt and ledger
    receipt_meta = evidence.metadata if isinstance(getattr(evidence, "metadata", None), dict) else {}
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
            state_machine=sm,
        )

    if receipt_fp_before != ledger_fp_before or receipt_fp_after != ledger_fp_after:
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Workspace fingerprint mismatch between evidence receipt and ledger OBSERVATION event.",
            evidence=evidence,
            ledger=ledger,
            state_machine=sm,
        )

    # Check post-verification staleness
    is_fresh, stale_reason = check_staleness(evidence, ws)
    if not is_fresh:
        return _record_rejection(
            claim=claim,
            reason=f"Claim rejected: Evidence is stale. {stale_reason}",
            evidence=evidence,
            ledger=ledger,
            state_machine=sm,
        )

    # Evidence is observed and valid: advance state machine
    try:
        sm.transition_to(VerificationState.OBSERVED, reason="Observed receipt validated")
        sm.transition_to(VerificationState.VERIFICATION_RUNNING, reason="Executing verification plan")
    except Exception:
        pass

    # Invariant 3: Validate caller-requested verifier against actual detected verifier
    requested_v = getattr(claim, "requested_verifier", None) or getattr(claim, "verifier", None)
    actual_v = getattr(evidence, "verifier", "")
    if requested_v and requested_v not in ("generic", ""):
        if actual_v in ("generic", "", "none") or (actual_v != requested_v and not actual_v.startswith(requested_v)):
            return _record_rejection(
                claim=claim,
                reason=(
                    f"Verifier mismatch: Claim requested verifier '{requested_v}', but actual observed "
                    f"process identity ran verifier '{actual_v or 'none'}'. Agent cannot upgrade unverified execution."
                ),
                evidence=evidence,
                ledger=ledger,
                state_machine=sm,
            )

    # Evaluate ClaimAcceptanceMatrix sufficiency
    is_suff, def_verdict, matrix_reason = ClaimAcceptanceMatrix.evaluate_evidence_sufficiency(claim, evidence)
    if not is_suff:
        if def_verdict == "REJECT":
            return _record_rejection(
                claim=claim,
                reason=f"Claim rejected per acceptance matrix: {matrix_reason}",
                evidence=evidence,
                ledger=ledger,
                state_machine=sm,
            )
        elif def_verdict == "INCONCLUSIVE":
            try:
                sm.transition_to(VerificationState.INCONCLUSIVE, reason=matrix_reason)
            except Exception:
                pass
            return VerificationResult(
                status="INCONCLUSIVE",
                claim_id=claim.claim_id,
                reason=matrix_reason,
                observed_exit_code=getattr(evidence, "exit_code", None),
                receipt_id=evidence.receipt_id,
                verification_state="INCONCLUSIVE",
                state_machine=sm,
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
            state_machine=sm,
        )

    if verdict.is_inconclusive:
        try:
            sm.transition_to(VerificationState.INCONCLUSIVE, reason=verdict.reason)
        except Exception:
            pass
        verdict.state_machine = sm
        verdict.verification_state = "INCONCLUSIVE"
        return verdict

    # Emit VerificationEvent for accepted claims
    prev_hash = matching_obs.get("previous_hash") or ledger.get_last_hash()
    event = VerificationEvent(
        claim_id=claim.claim_id,
        receipt_id=evidence.receipt_id,
        receipt_hash=recorded_hash,
        verifier=verifier.verifier_id,
        verification_time=datetime.now(timezone.utc).isoformat(),
        result="CLAIM_VERIFIED",
        reason=verdict.reason,
        repository_fingerprint=getattr(evidence, "workspace_fingerprint", ""),
        previous_ledger_hash=prev_hash,
        metadata={"exit_code": getattr(evidence, "exit_code", 0), "agent": getattr(evidence, "agent", "agent")},
    )

    try:
        sm.transition_to(VerificationState.ACCEPTED, reason=verdict.reason)
    except Exception:
        pass

    verdict.state_machine = sm
    verdict.verification_state = "ACCEPTED"
    verdict.verification_event = event
    _update_hooks_verified(ws, getattr(evidence, "agent", ""))

    if ledger:
        event_dict = verdict.to_dict()
        event_dict.update(event.to_dict())
        ledger.append("verification", event_dict)

    return verdict
