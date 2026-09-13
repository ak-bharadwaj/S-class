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
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List

from sclass.survival.models import Claim, EvidenceReceipt, VerificationResult
from sclass.survival.evidence import save_receipt, load_receipt
from sclass.survival.ledger import LocalLedger
from sclass.survival.verification.evidence import check_verification_staleness


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

    # Aggregate passed test count
    passed = 0
    for ev in evidence.evidence:
        passed += ev.get("passed_tests", 0)

    # All gates cleared: ACCEPT
    evidence.verified = True
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
