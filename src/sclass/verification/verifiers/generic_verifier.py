"""
S-Class Verification: Generic Command & Feature Verifier Plugin.
Evaluates file changes, completions, and non-test command claims.
"""

from __future__ import annotations
from sclass.domain.claim import Claim
from sclass.domain.evidence import EvidenceReceipt
from sclass.domain.verification import VerificationResult
from sclass.verification.verifiers.base import Verifier


class GenericVerifier(Verifier):
    """Fallback verifier for file modifications, features, and non-test completion."""
    verifier_id = "generic"

    def can_verify(self, claim: Claim, evidence: EvidenceReceipt) -> bool:
        return True

    def verify(self, claim: Claim, evidence: EvidenceReceipt, workspace_dir: str) -> VerificationResult:
        # Documentation claims do not fail on exit code != 0
        if claim.claim_type in ("documentation", "docs"):
            return VerificationResult(
                status="ACCEPT",
                claim_id=claim.claim_id,
                reason="Documentation claim verified.",
                observed_exit_code=evidence.exit_code,
                observed_files_changed=tuple(evidence.files_changed),
                receipt_id=evidence.receipt_id,
            )

        if evidence.exit_code != 0:
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Observed execution failed with exit code {evidence.exit_code}. Contradictory evidence.",
                observed_exit_code=evidence.exit_code,
                observed_files_changed=tuple(evidence.files_changed),
                receipt_id=evidence.receipt_id,
            )

        if claim.claim_type in ("file_change", "feature") and not evidence.files_changed:
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason="Feature implementation claimed, but zero files were modified in repository state.",
                receipt_id=evidence.receipt_id,
            )

        # Test claims routed here without an authorized test runner must be rejected
        if claim.claim_type in ("test_pass", "test", "tests") and evidence.execution_kind not in ("test_runner", "test_executor"):
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Claim asserts test results, but command was not executed by an authorized test runner (execution_kind='{evidence.execution_kind}').",
                observed_exit_code=evidence.exit_code,
                observed_files_changed=tuple(evidence.files_changed),
                receipt_id=evidence.receipt_id,
            )

        # Strict semantic claim verification: distinguish EXECUTION_VERIFIED from CLAIM_VERIFIED
        semantic_claim_types = ("feature", "behavior", "semantic", "security", "correctness", "functionality")
        if claim.claim_type in semantic_claim_types and evidence.execution_kind not in ("test_runner", "test_executor"):
            return VerificationResult(
                status="INCONCLUSIVE",
                claim_id=claim.claim_id,
                reason=(
                    "Execution completed successfully (EXECUTION_VERIFIED), but generic command "
                    "evidence is inconclusive for semantic feature claim. Dedicated test runner verification required."
                ),
                observed_exit_code=evidence.exit_code,
                observed_files_changed=tuple(evidence.files_changed),
                receipt_id=evidence.receipt_id,
            )

        return VerificationResult(
            status="ACCEPT",
            claim_id=claim.claim_id,
            reason="Command execution completed successfully (EXECUTION_VERIFIED).",
            observed_exit_code=0,
            observed_files_changed=tuple(evidence.files_changed),
            receipt_id=evidence.receipt_id,
        )
