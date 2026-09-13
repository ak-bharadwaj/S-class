"""
S-Class Verification: Pytest Verifier Plugin.
Evaluates pytest execution receipts against claims with structured test results and scope binding.
"""

from __future__ import annotations
import os
import re
from typing import Dict, Any, Optional, List

from sclass.domain.claim import Claim, ClaimScope
from sclass.domain.evidence import EvidenceReceipt
from sclass.domain.verification import VerificationResult, TestSelection
from sclass.execution.identity import ExecutionIdentity
from sclass.verification.detector import DetectionResult, VerifierConfidence
from sclass.verification.result_parser import PytestResultParser, NormalizedTestResult
from sclass.verification.verifiers.base import Verifier


class PytestVerifier(Verifier):
    """Authoritative verifier for pytest test runs."""
    verifier_id = "pytest"

    def identify(self, execution: ExecutionIdentity) -> DetectionResult:
        tokens = list(execution.actual_argv)
        raw_exe = execution.executable_path or (tokens[0] if tokens else "")
        exe_base = os.path.basename(raw_exe).lower()
        if exe_base.endswith(".exe"):
            exe_base = exe_base[:-4]

        # python -m pytest
        if exe_base in ("python", "python3", "py"):
            args = tokens[1:]
            if "-c" in args:
                return DetectionResult(
                    verifier_id="generic",
                    confidence=VerifierConfidence.CONTRADICTED,
                    evidence={"reason": "python -c flag is not a test runner"},
                    executable_match=False,
                    argv_match=False,
                    interpreter_match=True,
                )
            for i, arg in enumerate(args):
                if arg == "-m" and i + 1 < len(args) and args[i + 1].lower() == "pytest":
                    return DetectionResult(
                        verifier_id="pytest",
                        confidence=VerifierConfidence.AUTHORIZED,
                        evidence={"module": "pytest"},
                        executable_match=True,
                        argv_match=True,
                        interpreter_match=True,
                    )
                elif arg.startswith("-m") and arg[2:].lower() == "pytest":
                    return DetectionResult(
                        verifier_id="pytest",
                        confidence=VerifierConfidence.AUTHORIZED,
                        evidence={"module": "pytest"},
                        executable_match=True,
                        argv_match=True,
                        interpreter_match=True,
                    )

        if exe_base in ("pytest", "py.test"):
            return DetectionResult(
                verifier_id="pytest",
                confidence=VerifierConfidence.AUTHORIZED,
                evidence={"binary": exe_base},
                executable_match=True,
                argv_match=True,
                interpreter_match=False,
            )

        return DetectionResult(
            verifier_id="generic",
            confidence=VerifierConfidence.UNKNOWN,
            evidence={"reason": "Not a pytest invocation"},
            executable_match=False,
            argv_match=False,
            interpreter_match=False,
        )

    def parse_result(self, observation: Any) -> NormalizedTestResult:
        stdout = getattr(observation, "stdout_content", "") or ""
        stderr = getattr(observation, "stderr_content", "") or ""
        exit_code = getattr(observation, "exit_code", 0)
        command = getattr(observation, "command", "")
        # Extract selected targets from command
        targets = [t for t in command.split() if not t.startswith("-") and t not in ("pytest", "python", "py.test")]
        return PytestResultParser.parse(stdout, stderr, exit_code, targets=targets)

    def can_verify(self, claim: Claim, evidence: Any) -> bool:
        if claim.claim_type in ("test_pass", "test", "tests"):
            return True
        if getattr(evidence, "verifier", None) == "pytest":
            return True
        return False

    def verify(self, claim: Claim, evidence: Any, workspace_dir: str = "") -> VerificationResult:
        # Check execution kind
        execution_kind = getattr(evidence, "execution_kind", "")
        if execution_kind not in ("test_runner", "test_executor"):
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Claim asserts test results, but command '{getattr(evidence, 'command', '')}' was not executed by an authorized test runner.",
                receipt_id=getattr(evidence, "receipt_id", None),
            )

        exit_code = getattr(evidence, "exit_code", 0)

        # Check explicit failed_tests count from legacy evidence dict or structured result
        ev_items = getattr(evidence, "evidence", []) or []
        failed_count = 0
        passed_count = 0
        for item in ev_items:
            if isinstance(item, dict):
                failed_count = max(failed_count, item.get("failed_tests", 0))
                passed_count = max(passed_count, item.get("passed_tests", 0))

        # Parse structured result
        norm_result = self.parse_result(evidence)
        if norm_result.failed > 0:
            failed_count = max(failed_count, norm_result.failed)
        if norm_result.passed > 0:
            passed_count = max(passed_count, norm_result.passed)

        if exit_code != 0:
            reason = (
                f"Independent test runner observed {failed_count} test failure(s) (exit code {exit_code})."
                if failed_count > 0
                else f"Test command execution failed with exit code {exit_code}."
            )
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=reason,
                observed_exit_code=exit_code,
                passed_tests=passed_count,
                failed_tests=failed_count,
                receipt_id=getattr(evidence, "receipt_id", None),
                metadata={"structured_result": norm_result.to_dict()} if norm_result else {},
            )

        if failed_count > 0:
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Independent test runner observed {failed_count} test failure(s).",
                observed_exit_code=exit_code,
                passed_tests=passed_count,
                failed_tests=failed_count,
                receipt_id=getattr(evidence, "receipt_id", None),
                metadata={"structured_result": norm_result.to_dict()} if norm_result else {},
            )

        # Claim-to-test-target scope binding check
        command = getattr(evidence, "command", "")
        cmd_tokens = command.split()
        targets = [t for t in cmd_tokens if not t.startswith("-") and t not in ("pytest", "python", "-m", "py.test")]
        test_selection = TestSelection(selected_tests=tuple(targets), test_files=tuple(targets))

        if claim.scope:
            covers, scope_reason = test_selection.covers_scope(claim.scope)
            if not covers:
                return VerificationResult(
                    status="REJECT",
                    claim_id=claim.claim_id,
                    reason=f"Claim-to-test-target scope mismatch: {scope_reason}",
                    observed_exit_code=exit_code,
                    passed_tests=norm_result.passed,
                    receipt_id=getattr(evidence, "receipt_id", None),
                    metadata={"claim_scope": claim.scope.to_dict(), "test_selection": test_selection.to_dict()},
                )

        passed = norm_result.passed or sum(item.get("passed_tests", 0) for item in ev_items)

        return VerificationResult(
            status="ACCEPT",
            claim_id=claim.claim_id,
            reason="Pytest suite verified clean: exit code 0 and zero observed test failures.",
            observed_exit_code=0,
            observed_files_changed=tuple(getattr(evidence, "files_changed", [])),
            passed_tests=passed,
            receipt_id=getattr(evidence, "receipt_id", None),
            metadata={"structured_result": norm_result.to_dict()},
        )
