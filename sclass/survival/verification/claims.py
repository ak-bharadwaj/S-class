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
    VerificationResult,
    ProposedEvidence,
    ClaimedEvidence,
    LIFECYCLE_INTEGRITY_VERIFIED,
    LIFECYCLE_CLAIM_VERIFIED,
)
from sclass.survival.evidence import save_receipt, load_receipt
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

    # Finding #4: Distinguish Observed Receipt vs Proposed/Claimed Evidence
    if isinstance(evidence, (ProposedEvidence, ClaimedEvidence)) or not getattr(evidence, "is_observed", True):
        result = VerificationResult(
            status="REJECT",
            claim_id=claim.claim_id,
            reason="Claim rejected: Agent supplied proposed/claimed evidence, but verification requires an independently observed receipt.",
            receipt_id=getattr(evidence, "receipt_id", None),
        )
        if ledger:
            ledger.append("rejection", result.to_dict())
        return result

    # Finding #2: Missing receipt hash must be REJECT. No third state (missing -> REJECT, invalid -> REJECT, valid -> continue).
    recorded_hash = getattr(evidence, "receipt_hash", None) or (
        evidence.metadata.get("receipt_hash") if isinstance(evidence.metadata, dict) else None
    )
    if not recorded_hash:
        result = VerificationResult(
            status="REJECT",
            claim_id=claim.claim_id,
            reason="Claim rejected: Missing evidence receipt hash. Persisted authoritative receipt must have cryptographic receipt_hash.",
            receipt_id=evidence.receipt_id,
        )
        if ledger:
            ledger.append("rejection", result.to_dict())
        return result

    # Finding #1: Hash integrity verification across all security-relevant fields
    expected_hash = evidence.compute_hash()
    if recorded_hash != expected_hash:
        result = VerificationResult(
            status="REJECT",
            claim_id=claim.claim_id,
            reason="Claim rejected: Evidence receipt hash mismatch. Tampering detected.",
            receipt_id=evidence.receipt_id,
        )
        if ledger:
            ledger.append("rejection", result.to_dict())
        return result

    # Finding #6: Lifecycle transition to INTEGRITY_VERIFIED
    evidence.lifecycle_state = LIFECYCLE_INTEGRITY_VERIFIED

    # Finding #7 & Attack Family E: Structured claim evaluation
    is_test_claim = is_test_assertion(claim)

    if is_test_claim:
        if evidence.exit_code != 0:
            result = VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Claim rejected: Test command execution failed with exit code {evidence.exit_code}.",
                observed_exit_code=evidence.exit_code,
                observed_files_changed=tuple(evidence.files_changed or []),
                receipt_id=evidence.receipt_id,
            )
            if ledger:
                ledger.append("rejection", result.to_dict())
            return result

        # Check explicit failed_tests count if present in receipt evidence items
        for ev in (evidence.evidence or []):
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

    # Contradictory evidence defense for non-test non-documentation claims:
    # If the observed command execution failed with exit_code != 0, reject!
    elif not is_doc_claim(claim) and evidence.exit_code != 0:
        result = VerificationResult(
            status="REJECT",
            claim_id=claim.claim_id,
            reason=f"Claim rejected: Observed execution failed with exit code {evidence.exit_code}. Contradictory evidence.",
            observed_exit_code=evidence.exit_code,
            observed_files_changed=tuple(evidence.files_changed or []),
            receipt_id=evidence.receipt_id,
        )
        if ledger:
            ledger.append("rejection", result.to_dict())
        return result

    # Finding #3: Staleness check (including repository state & same-file fingerprints)
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

    # Aggregate passed test count
    passed = 0
    for ev in evidence.evidence:
        passed += ev.get("passed_tests", 0)

    # Finding #6: All gates cleared -> CLAIM_VERIFIED lifecycle transition
    evidence.verified = True
    evidence.lifecycle_state = LIFECYCLE_CLAIM_VERIFIED
    save_receipt(evidence, ws)

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
    )
    if ledger:
        ledger.append("verification", result.to_dict())
    return result
