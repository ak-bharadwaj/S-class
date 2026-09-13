"""
S-Class Survival v0: Claim -> Evidence Verifier (sclass/survival/verification.py)

Implements Phase 5, 8, 9:
Evaluates unverified agent Claims against authoritative, independently observed EvidenceReceipts.
Defends against:
- Attack 1: Claims tests passed, exit_code != 0
- Attack 2: Fabricates qa_report or forged receipt
- Attack 8: Stale evidence
- Attack 9: Agent changes repository after verification -> invalidation
- Attack 10: Agent says done but produces no evidence
"""

from __future__ import annotations
import os
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List

from sclass.survival.models import Claim, EvidenceReceipt, VerificationResult
from sclass.survival.evidence import _get_git_commit_hash, _get_git_changed_files, save_receipt, load_receipt
from sclass.survival.ledger import LocalLedger


def check_verification_staleness(receipt: EvidenceReceipt, workspace_dir: str) -> Tuple[bool, Optional[str]]:
    """
    Checks if repository state has changed since the evidence was produced.
    Returns (True, None) if fresh, or (False, reason) if invalidated.
    """
    current_head = _get_git_commit_hash(workspace_dir)
    if receipt.result_commit and current_head and receipt.result_commit != "0" * 40 and current_head != "0" * 40:
        if receipt.result_commit != current_head:
            return (False, f"Repository HEAD advanced from {receipt.result_commit[:8]} to {current_head[:8]}")

    # Check for uncommitted changes introduced after execution
    changed = _get_git_changed_files(workspace_dir, receipt.result_commit)
    # Filter out .agents directory changes
    code_changes = [f for f in changed if not f.startswith(".agents")]
    if code_changes:
        # If there are new uncommitted code changes not recorded in the receipt
        unrecorded = [f for f in code_changes if f not in receipt.files_changed]
        if unrecorded:
            return (False, f"Repository contains {len(unrecorded)} uncommitted file changes introduced after verification: {', '.join(unrecorded[:3])}")

    return (True, None)


def verify_claim(
    claim: Claim,
    evidence: Optional[EvidenceReceipt],
    workspace_dir: Optional[str] = None,
    ledger: Optional[LocalLedger] = None,
) -> VerificationResult:
    """
    Verifies an agent claim against observed evidence.
    Returns authoritative VerificationResult (ACCEPT | REJECT | INVALID).
    """
    ws = os.path.abspath(workspace_dir or (evidence.workspace if evidence else os.getcwd()))

    # Attack 10: Agent says "done" but produces no evidence
    if evidence is None:
        result = VerificationResult(
            status="REJECT",
            claim_id=claim.claim_id,
            reason="Claim rejected: Agent claimed completion but produced no independently observed evidence receipt.",
        )
        if ledger:
            ledger.append("rejection", result.to_dict())
        return result

    # Attack 2: Fabricated or tampered evidence receipt
    expected_hash = evidence.compute_hash()
    recorded_hash = evidence.metadata.get("receipt_hash") or getattr(evidence, "receipt_hash", None)
    if recorded_hash and recorded_hash != expected_hash:
        result = VerificationResult(
            status="REJECT",
            claim_id=claim.claim_id,
            reason="Claim rejected: Evidence receipt hash mismatch. Tampering detected.",
            receipt_id=evidence.receipt_id,
        )
        if ledger:
            ledger.append("rejection", result.to_dict())
        return result

    # Attack 1: Agent claims tests passed, actual exit code != 0 or tests failed
    is_test_claim = (
        claim.claim_type == "test_pass"
        or any(w in claim.statement.lower() for w in ("test", "pytest", "tests pass", "all passed"))
    )

    if is_test_claim:
        if evidence.exit_code != 0:
            result = VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Claim rejected: Test command execution failed with exit code {evidence.exit_code}.",
                observed_exit_code=evidence.exit_code,
                observed_files_changed=tuple(evidence.files_changed),
                receipt_id=evidence.receipt_id,
            )
            if ledger:
                ledger.append("rejection", result.to_dict())
            return result

        # Check explicit failed_tests count if present in receipt evidence items
        for ev in evidence.evidence:
            failed = ev.get("failed_tests", 0)
            if failed > 0:
                result = VerificationResult(
                    status="REJECT",
                    claim_id=claim.claim_id,
                    reason=f"Claim rejected: Independent test runner observed {failed} test failure(s).",
                    observed_exit_code=evidence.exit_code,
                    failed_tests=failed,
                    receipt_id=evidence.receipt_id,
                )
                if ledger:
                    ledger.append("rejection", result.to_dict())
                return result

    # Attack 8: Evidence is stale
    is_fresh, staleness_reason = check_verification_staleness(evidence, ws)
    if not is_fresh:
        result = VerificationResult(
            status="REJECT",
            claim_id=claim.claim_id,
            reason=f"Claim rejected: Evidence is stale. {staleness_reason}",
            invalidation_reason=staleness_reason,
            receipt_id=evidence.receipt_id,
        )
        if ledger:
            ledger.append("rejection", result.to_dict())
        return result

    # Code changes verification for implementation claims
    if claim.claim_type in ("file_change", "feature"):
        if not evidence.files_changed:
            result = VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason="Claim rejected: Feature implementation claimed, but zero files were modified in repository state.",
                observed_files_changed=tuple(),
                receipt_id=evidence.receipt_id,
            )
            if ledger:
                ledger.append("rejection", result.to_dict())
            return result

    # All gates cleared: ACCEPT
    evidence.verified = True
    save_receipt(evidence, ws)

    result = VerificationResult(
        status="ACCEPT",
        claim_id=claim.claim_id,
        reason="Claim verified: All evidence requirements satisfied by independently observed execution.",
        observed_exit_code=evidence.exit_code,
        observed_files_changed=tuple(evidence.files_changed),
        receipt_id=evidence.receipt_id,
    )
    if ledger:
        ledger.append("verification", result.to_dict())
    return result

