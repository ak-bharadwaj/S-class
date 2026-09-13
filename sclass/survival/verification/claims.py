"""
S-Class Survival v0: Verifier Claims Module (sclass/survival/verification/claims.py)

Implements Phase 5, Phase 6, Phase 9:
✓ Claim -> Evidence verification
✓ Exit code verification
✓ Test result verification (including passed_tests and failed_tests counts)
✓ Post-verification invalidation on repository changes
✓ Updates last_verified in sclass_hooks.json upon genuine verification success
"""

from __future__ import annotations
import os
import re
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List

from sclass.survival.models import (
    Claim,
    EvidenceReceipt,
    ObservedReceipt,
    VerificationResult,
    VerificationEvent,
    ProposedEvidence,
    ClaimedEvidence,
    LIFECYCLE_INTEGRITY_VERIFIED,
    LIFECYCLE_CLAIM_VERIFIED,
)
from sclass.survival.evidence import load_receipt
from sclass.survival.ledger import LocalLedger
from sclass.survival.verification.evidence import check_verification_staleness


TEST_PASS_PATTERNS = [
    re.compile(r"\b(tests?)\s+(?:are\s+)?(?:pass|passed|passing|green|succeeded)\b", re.IGNORECASE),
    re.compile(r"\b(?:all\s+)?tests?\s+pass(?:ed|ing)?\b", re.IGNORECASE),
    re.compile(r"\bpytest\b(?:\s+(?:pass|passed|clean|green|succeed))?", re.IGNORECASE),
    re.compile(r"\b(?:all\s+)?(?:green|passing)\b.*\btests?\b", re.IGNORECASE),
    re.compile(r"\b(?:implementation|build|suite|code|repo|everything|all)\s+is\s+green\b", re.IGNORECASE),
    re.compile(r"\b(?:all\s+)?green\b", re.IGNORECASE),
    re.compile(r"\b100%\s+(?:pass|success|tests)\b", re.IGNORECASE),
    re.compile(r"\bunit\s+tests?\s+(?:pass|passed)\b", re.IGNORECASE),
    re.compile(r"\bpasses\s+all\s+tests\b", re.IGNORECASE),
]

DOC_PATTERNS = [
    re.compile(r"\b(?:documentation|docs?|readme|comments?|docstring)\b", re.IGNORECASE),
]

IMPLEMENTATION_PATTERNS = [
    re.compile(r"\b(?:implemented|implementing|fix|fixed|fixing|added|built|created|updated|done|completed|refactored)\b", re.IGNORECASE),
]


def is_doc_claim(claim: Claim) -> bool:
    """Determines if a claim is purely about documentation."""
    if claim.claim_type in ("documentation", "doc_change", "docs"):
        return True
    stmt = claim.statement.strip()
    if any(p.search(stmt) for p in DOC_PATTERNS):
        has_pass_assertion = any(p.search(stmt) for p in TEST_PASS_PATTERNS)
        if not has_pass_assertion:
            return True
    return False


def is_test_assertion(claim: Claim) -> bool:
    """Determines if a claim asserts test execution results with structured precedence."""
    if claim.claim_type == "test_pass":
        return True
    if is_doc_claim(claim):
        return False

    stmt = claim.statement.strip()
    for p in TEST_PASS_PATTERNS:
        if p.search(stmt):
            return True

    return False


def _update_sclass_hooks_verified(workspace_dir: str, agent: str = "") -> None:
    """Updates last_verified in .agents/sclass_hooks.json when verification succeeds."""
    try:
        cfg_path = os.path.join(workspace_dir, ".agents", "sclass_hooks.json")
        if not os.path.exists(cfg_path):
            return

        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        now_iso = datetime.now(timezone.utc).isoformat()
        if "last_verified" not in cfg or not isinstance(cfg["last_verified"], dict):
            cfg["last_verified"] = {}

        target_key = agent or "default"
        cfg["last_verified"][target_key] = now_iso

        # If matching platform exists in platforms dictionary, mark verified
        if "platforms" in cfg and isinstance(cfg["platforms"], dict):
            for plat in (agent, f"{agent}_code", "claude_code", "cursor", "codex", "antigravity"):
                if plat in cfg["platforms"] and isinstance(cfg["platforms"][plat], dict):
                    cfg["platforms"][plat]["verified"] = True
                    cfg["platforms"][plat]["last_verified"] = now_iso

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
    files_changed: Optional[Tuple[str, ...]] = None,
    failed_tests: int = 0,
    invalidation_reason: Optional[str] = None,
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
            verifier="sclass_verifier",
            verification_time=datetime.now(timezone.utc).isoformat(),
            result="REJECT",
            reason=reason,
            repository_fingerprint=ws_fp,
            previous_ledger_hash=prev_hash,
            metadata={
                "exit_code": exit_code,
                "invalidation_reason": invalidation_reason,
            },
        )

    res = VerificationResult(
        status="REJECT",
        claim_id=claim.claim_id,
        reason=reason,
        observed_exit_code=exit_code,
        observed_files_changed=files_changed or tuple(),
        failed_tests=failed_tests,
        invalidation_reason=invalidation_reason,
        receipt_id=r_id,
        verification_event=event,
    )
    if ledger:
        payload = res.to_dict()
        if event:
            payload.update({
                "receipt_id": r_id,
                "receipt_hash": r_hash,
                "workspace_fingerprint": ws_fp,
                "previous_ledger_hash": prev_hash,
                "verification_result": "REJECT",
                "event_id": event.event_id,
            })
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
    Receipt is treated as immutable observation facts: no fields are mutated.
    Emits a typed VerificationEvent cryptographically bound to the receipt,
    workspace fingerprint, and ledger chain.
    """
    ws = os.path.abspath(workspace_dir or (evidence.workspace if evidence else os.getcwd()))
    if ledger is None:
        try:
            ledger = LocalLedger(workspace_dir=ws)
        except Exception:
            ledger = None

    # Attack 10: Agent says "done" but produces no evidence
    if evidence is None:
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Agent claimed completion but produced no independently observed evidence receipt.",
            evidence=None,
            ledger=ledger,
        )

    # Finding #4: Distinguish Proposed/Claimed Evidence or explicitly unobserved assertions
    if isinstance(evidence, (ProposedEvidence, ClaimedEvidence)) or getattr(evidence, "_explicitly_unobserved", False):
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Agent supplied proposed/claimed evidence, but verification requires an independently observed receipt.",
            evidence=evidence,
            ledger=ledger,
        )

    # Finding #2: Missing receipt hash must be REJECT.
    recorded_hash = getattr(evidence, "receipt_hash", None) or (
        evidence.metadata.get("receipt_hash") if isinstance(evidence.metadata, dict) else None
    )
    if not recorded_hash:
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Missing evidence receipt hash. Persisted authoritative receipt must have cryptographic receipt_hash.",
            evidence=evidence,
            ledger=ledger,
        )

    # Finding #1: Hash integrity verification across all security-relevant fields
    expected_hash = evidence.compute_hash()
    if recorded_hash != expected_hash:
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Evidence receipt hash mismatch. Tampering detected.",
            evidence=evidence,
            ledger=ledger,
        )

    # Phase 1 Trust Boundary: Non-forgeable ObservedReceipt capability check
    # Persisted data or forged EvidenceReceipts without capability token cannot satisfy verification
    if not isinstance(evidence, ObservedReceipt) or not getattr(evidence, "is_observed", False):
        return _record_rejection(
            claim=claim,
            reason="Claim rejected: Agent supplied unobserved or untrusted evidence. Verification requires an authentic ObservedReceipt produced by observe_command.",
            evidence=evidence,
            ledger=ledger,
        )

    # Structured claim evaluation
    is_test_claim = is_test_assertion(claim)

    if is_test_claim:
        if evidence.exit_code != 0:
            return _record_rejection(
                claim=claim,
                reason=f"Claim rejected: Test command execution failed with exit code {evidence.exit_code}.",
                evidence=evidence,
                ledger=ledger,
                exit_code=evidence.exit_code,
                files_changed=tuple(evidence.files_changed or []),
            )

        # Check explicit failed_tests count if present in receipt evidence items
        for ev in (evidence.evidence or []):
            failed = ev.get("failed_tests", 0)
            if failed > 0:
                return _record_rejection(
                    claim=claim,
                    reason=f"Claim rejected: Independent test runner observed {failed} test failure(s).",
                    evidence=evidence,
                    ledger=ledger,
                    exit_code=evidence.exit_code,
                    failed_tests=failed,
                )

    # Contradictory evidence defense for non-test non-documentation claims:
    elif not is_doc_claim(claim) and evidence.exit_code != 0:
        return _record_rejection(
            claim=claim,
            reason=f"Claim rejected: Observed execution failed with exit code {evidence.exit_code}. Contradictory evidence.",
            evidence=evidence,
            ledger=ledger,
            exit_code=evidence.exit_code,
            files_changed=tuple(evidence.files_changed or []),
        )

    # Finding #3 & Phase 4: Staleness and comprehensive workspace snapshot check
    is_fresh, staleness_reason = check_verification_staleness(evidence, ws)
    if not is_fresh:
        return _record_rejection(
            claim=claim,
            reason=f"Claim rejected: Evidence is stale. {staleness_reason}",
            evidence=evidence,
            ledger=ledger,
            invalidation_reason=staleness_reason,
        )

    # Code changes verification for implementation claims
    if claim.claim_type in ("file_change", "feature"):
        if not evidence.files_changed:
            return _record_rejection(
                claim=claim,
                reason="Claim rejected: Feature implementation claimed, but zero files were modified in repository state.",
                evidence=evidence,
                ledger=ledger,
            )

    # Aggregate passed test count
    passed = 0
    for ev in evidence.evidence:
        passed += ev.get("passed_tests", 0)

    # The receipt stays immutable (no mutation of verified or lifecycle_state on evidence object)
    # Instead, we construct a cryptographically bound VerificationEvent
    prev_ledger_hash = ledger.get_last_hash() if (ledger and hasattr(ledger, "get_last_hash")) else "0" * 64
    ws_fp = getattr(evidence, "workspace_fingerprint", "") or ""

    verif_event = VerificationEvent(
        claim_id=claim.claim_id,
        receipt_id=evidence.receipt_id,
        receipt_hash=recorded_hash,
        verifier="sclass_verifier",
        verification_time=datetime.now(timezone.utc).isoformat(),
        result="CLAIM_VERIFIED",
        reason="Claim verified: All evidence requirements satisfied by independently observed execution.",
        repository_fingerprint=ws_fp,
        previous_ledger_hash=prev_ledger_hash,
        metadata={
            "exit_code": evidence.exit_code,
            "files_changed": list(evidence.files_changed or []),
            "agent": evidence.agent,
        },
    )

    # Update last_verified in sclass_hooks.json
    _update_sclass_hooks_verified(ws, evidence.agent)

    result = VerificationResult(
        status="ACCEPT",
        claim_id=claim.claim_id,
        reason="Claim verified: All evidence requirements satisfied by independently observed execution.",
        observed_exit_code=evidence.exit_code,
        observed_files_changed=tuple(evidence.files_changed),
        passed_tests=passed,
        receipt_id=evidence.receipt_id,
        verification_event=verif_event,
    )
    if ledger:
        event_dict = result.to_dict()
        event_dict.update({
            "receipt_id": evidence.receipt_id,
            "receipt_hash": recorded_hash,
            "workspace_fingerprint": ws_fp,
            "previous_ledger_hash": prev_ledger_hash,
            "verification_result": "CLAIM_VERIFIED",
            "event_id": verif_event.event_id,
        })
        ledger.append("verification", event_dict)
    return result
