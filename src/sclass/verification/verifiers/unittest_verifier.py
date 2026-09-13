"""
S-Class Verification: Unittest Verifier Plugin.
Evaluates python unittest execution receipts against claims.
"""

from __future__ import annotations
import os
from typing import Dict, Any, Optional

from sclass.domain.claim import Claim
from sclass.domain.verification import VerificationResult, TestSelection
from sclass.execution.identity import ExecutionIdentity
from sclass.verification.detector import DetectionResult, VerifierConfidence
from sclass.verification.result_parser import UnittestResultParser, NormalizedTestResult
from sclass.verification.verifiers.base import Verifier


class UnittestVerifier(Verifier):
    """Authoritative verifier for python unittest runs."""
    verifier_id = "unittest"

    def identify(self, execution: ExecutionIdentity) -> DetectionResult:
        tokens = list(execution.actual_argv)
        raw_exe = execution.executable_path or (tokens[0] if tokens else "")
        exe_base = os.path.basename(raw_exe).lower()
        if exe_base.endswith(".exe"):
            exe_base = exe_base[:-4]

        if exe_base in ("python", "python3", "py") or exe_base.startswith("python3.") or exe_base.startswith("python2.") or exe_base.startswith("pypy"):
            args = tokens[1:]
            for i, arg in enumerate(args):
                if arg == "-m" and i + 1 < len(args) and args[i + 1].lower() == "unittest":
                    return DetectionResult(
                        verifier_id="unittest",
                        confidence=VerifierConfidence.AUTHORIZED,
                        evidence={"module": "unittest"},
                        executable_match=True,
                        argv_match=True,
                        interpreter_match=True,
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
        exit_code = getattr(observation, "exit_code", 0)
        command = getattr(observation, "command", "")
        targets = [t for t in command.split() if not t.startswith("-") and t not in ("python", "unittest")]
        return UnittestResultParser.parse(stdout, stderr, exit_code, targets=targets)

    def can_verify(self, claim: Claim, evidence: Any) -> bool:
        return getattr(evidence, "verifier", None) == "unittest"

    def verify(self, claim: Claim, evidence: Any, workspace_dir: str = "") -> VerificationResult:
        execution_kind = getattr(evidence, "execution_kind", "")
        if execution_kind not in ("test_runner", "test_executor"):
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason="Claim asserts test results, but command was not executed by an authorized test runner.",
                receipt_id=getattr(evidence, "receipt_id", None),
            )

        exit_code = getattr(evidence, "exit_code", 0)
        norm_result = self.parse_result(evidence)

        if exit_code != 0 or norm_result.failed > 0:
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Unittest observed {norm_result.failed} test failure(s) (exit_code={exit_code}).",
                observed_exit_code=exit_code,
                failed_tests=norm_result.failed,
                passed_tests=norm_result.passed,
                receipt_id=getattr(evidence, "receipt_id", None),
            )

        # Scope check
        if claim.scope:
            command = getattr(evidence, "command", "")
            targets = [t for t in command.split() if not t.startswith("-") and t not in ("python", "unittest")]
            selection = TestSelection(selected_tests=tuple(targets), test_files=tuple(targets))
            covers, scope_reason = selection.covers_scope(claim.scope)
            if not covers:
                return VerificationResult(
                    status="REJECT",
                    claim_id=claim.claim_id,
                    reason=f"Claim-to-test-target scope mismatch: {scope_reason}",
                    observed_exit_code=exit_code,
                    passed_tests=norm_result.passed,
                    receipt_id=getattr(evidence, "receipt_id", None),
                )

        return VerificationResult(
            status="ACCEPT",
            claim_id=claim.claim_id,
            reason="Unittest suite verified clean: exit code 0 and zero failures.",
            observed_exit_code=0,
            passed_tests=norm_result.passed,
            receipt_id=getattr(evidence, "receipt_id", None),
            metadata={"structured_result": norm_result.to_dict()},
        )
