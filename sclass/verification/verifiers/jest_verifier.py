"""
S-Class Verification: Jest Verifier Plugin.
"""

from __future__ import annotations
import re
from typing import Any, Optional

from sclass.domain.claim import Claim
from sclass.domain.verification import VerificationResult, TestSelection
from sclass.execution.identity import ExecutionIdentity
from sclass.verification.detector import DetectionResult, VerifierConfidence
from sclass.verification.result_parser import compute_output_hash, NormalizedTestResult
from sclass.verification.verifiers.base import Verifier


class JestVerifier(Verifier):
    """Authoritative verifier for Jest test runs."""
    verifier_id = "jest"

    def identify(self, execution: ExecutionIdentity) -> DetectionResult:
        tokens = list(execution.actual_argv)
        raw = execution.executable_name.lower()
        if "jest" in raw or (tokens and "jest" in tokens[0].lower()):
            return DetectionResult(
                verifier_id="jest",
                confidence=VerifierConfidence.AUTHORIZED,
                evidence={"binary": "jest"},
                executable_match=True,
                argv_match=True,
                interpreter_match=False,
            )
        return DetectionResult(
            verifier_id="generic",
            confidence=VerifierConfidence.UNKNOWN,
            evidence={},
            executable_match=False,
            argv_match=False,
            interpreter_match=False,
        )

    def parse_result(self, observation: Any) -> NormalizedTestResult:
        stdout = getattr(observation, "stdout_content", "") or ""
        stderr = getattr(observation, "stderr_content", "") or ""
        content = stdout + "\n" + stderr
        exit_code = getattr(observation, "exit_code", 0)

        passed = 0
        failed = 0
        m_pass = re.search(r"(\d+)\s+passed", content)
        if m_pass:
            passed = int(m_pass.group(1))
        m_fail = re.search(r"(\d+)\s+failed", content)
        if m_fail:
            failed = int(m_fail.group(1))

        if exit_code != 0 and failed == 0 and passed == 0:
            failed = 1

        return NormalizedTestResult(
            verifier_id="jest",
            discovered=passed + failed,
            passed=passed,
            failed=failed,
            skipped=0,
            selected_targets=[],
            duration=0.0,
            raw_artifact_hash=compute_output_hash(stdout, stderr),
        )

    def can_verify(self, claim: Claim, evidence: Any) -> bool:
        return getattr(evidence, "verifier", None) == "jest"

    def verify(self, claim: Claim, evidence: Any, workspace_dir: str = "") -> VerificationResult:
        exit_code = getattr(evidence, "exit_code", 0)
        norm = self.parse_result(evidence)
        if exit_code != 0 or norm.failed > 0:
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Jest observed {norm.failed} test failure(s) (exit_code={exit_code}).",
                observed_exit_code=exit_code,
                failed_tests=norm.failed,
                passed_tests=norm.passed,
                receipt_id=getattr(evidence, "receipt_id", None),
            )
        return VerificationResult(
            status="ACCEPT",
            claim_id=claim.claim_id,
            reason="Jest suite verified clean: exit code 0 and zero failures.",
            observed_exit_code=0,
            passed_tests=norm.passed,
            receipt_id=getattr(evidence, "receipt_id", None),
        )
