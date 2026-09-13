"""
S-Class Verification: Pytest Verifier Plugin.
Evaluates pytest execution receipts against claims.
"""

from __future__ import annotations
import re
from typing import Dict, Any

from sclass.domain.claim import Claim
from sclass.domain.evidence import EvidenceReceipt
from sclass.domain.verification import VerificationResult
from sclass.verification.verifiers.base import Verifier


class PytestVerifier(Verifier):
    """Authoritative verifier for pytest test runs."""
    verifier_id = "pytest"

    def can_verify(self, claim: Claim, evidence: EvidenceReceipt) -> bool:
        if claim.claim_type in ("test_pass", "test", "tests"):
            return True
        if evidence.verifier == "pytest":
            return True
        return False

    def verify(self, claim: Claim, evidence: EvidenceReceipt, workspace_dir: str) -> VerificationResult:
        # Check execution kind
        if evidence.execution_kind not in ("test_runner", "test_executor"):
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Claim asserts test results, but command '{evidence.command}' was not executed by an authorized test runner.",
                receipt_id=evidence.receipt_id,
            )

        if evidence.exit_code != 0:
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Test command execution failed with exit code {evidence.exit_code}.",
                observed_exit_code=evidence.exit_code,
                receipt_id=evidence.receipt_id,
            )

        # Check explicit failed_tests count
        for item in evidence.evidence:
            failed = item.get("failed_tests", 0)
            if failed > 0:
                return VerificationResult(
                    status="REJECT",
                    claim_id=claim.claim_id,
                    reason=f"Independent test runner observed {failed} test failure(s).",
                    observed_exit_code=evidence.exit_code,
                    failed_tests=failed,
                    receipt_id=evidence.receipt_id,
                )

        passed = sum(item.get("passed_tests", 0) for item in evidence.evidence)

        return VerificationResult(
            status="ACCEPT",
            claim_id=claim.claim_id,
            reason="Pytest suite verified clean: exit code 0 and zero observed test failures.",
            observed_exit_code=0,
            observed_files_changed=tuple(evidence.files_changed),
            passed_tests=passed,
            receipt_id=evidence.receipt_id,
        )
