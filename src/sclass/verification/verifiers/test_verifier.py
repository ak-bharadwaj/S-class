"""
S-Class Verification: TestVerifier (Tier V3).
"""
from __future__ import annotations
from typing import Any, Dict, Optional
from sclass.domain.verification import VerificationResult


class TestVerifier:
    __test__ = False

    def __init__(self, runner: str = "pytest", min_passed: int = 1):
        self.runner = runner
        self.min_passed = min_passed

    def verify(self, receipt: Any) -> VerificationResult:
        claim_id = getattr(receipt, "claim_id", "") or ""
        exit_code = getattr(receipt, "exit_code", None)
        metadata: Dict[str, Any] = getattr(receipt, "metadata", {}) or {}

        if exit_code is not None and exit_code != 0:
            return VerificationResult(
                status="REJECT",
                claim_id=claim_id,
                reason=f"Test runner '{self.runner}' exited with failure code {exit_code}",
                observed_exit_code=exit_code,
                metadata=metadata
            )

        failed = metadata.get("failed", 0)
        errors = metadata.get("errors", 0)
        passed = metadata.get("passed", 0)

        if failed > 0 or errors > 0:
            return VerificationResult(
                status="REJECT",
                claim_id=claim_id,
                reason=f"Test runner reported failures: {failed} failed, {errors} errors",
                failed_tests=failed,
                passed_tests=passed,
                metadata=metadata
            )

        if passed < self.min_passed:
            return VerificationResult(
                status="REJECT",
                claim_id=claim_id,
                reason=f"Test runner passed {passed} tests, below minimum required threshold of {self.min_passed}",
                passed_tests=passed,
                metadata=metadata
            )

        return VerificationResult(
            status="ACCEPT",
            claim_id=claim_id,
            reason=f"Test runner '{self.runner}' verified: {passed} passed, 0 failures",
            passed_tests=passed,
            failed_tests=0,
            metadata=metadata
        )
