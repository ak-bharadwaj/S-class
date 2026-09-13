"""
S-Class Verification: Ecosystem Test Verifiers.
Implements structured verifier plugins for:
- Vitest
- Mocha
- Playwright
- Cargo (Rust)
- Go (go test)
- Package scripts (npm, pnpm, yarn, bun)
"""

from __future__ import annotations
import re
import os
from typing import Any, Optional, List

from sclass.domain.claim import Claim
from sclass.domain.verification import VerificationResult, TestSelection
from sclass.execution.identity import ExecutionIdentity
from sclass.verification.detector import DetectionResult, VerifierConfidence
from sclass.verification.result_parser import compute_output_hash, NormalizedTestResult
from sclass.verification.verifiers.base import Verifier


class VitestVerifier(Verifier):
    """Verifier for Vitest test runs."""
    verifier_id = "vitest"

    def identify(self, execution: ExecutionIdentity) -> DetectionResult:
        raw = execution.executable_name.lower()
        if "vitest" in raw or (execution.actual_argv and "vitest" in execution.actual_argv[0].lower()):
            return DetectionResult(
                verifier_id="vitest",
                confidence=VerifierConfidence.AUTHORIZED,
                evidence={"binary": "vitest"},
                executable_match=True,
                argv_match=True,
                interpreter_match=False,
            )
        return DetectionResult(verifier_id="generic", confidence=VerifierConfidence.UNKNOWN, evidence={}, executable_match=False, argv_match=False, interpreter_match=False)

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
            verifier_id="vitest",
            discovered=passed + failed,
            passed=passed,
            failed=failed,
            skipped=0,
            selected_targets=[],
            duration=0.0,
            raw_artifact_hash=compute_output_hash(stdout, stderr),
        )

    def can_verify(self, claim: Claim, evidence: Any) -> bool:
        return getattr(evidence, "verifier", None) == "vitest"

    def verify(self, claim: Claim, evidence: Any, workspace_dir: str = "") -> VerificationResult:
        exit_code = getattr(evidence, "exit_code", 0)
        norm = self.parse_result(evidence)
        if exit_code != 0 or norm.failed > 0:
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Vitest observed {norm.failed} test failure(s) (exit_code={exit_code}).",
                observed_exit_code=exit_code,
                failed_tests=norm.failed,
                passed_tests=norm.passed,
                receipt_id=getattr(evidence, "receipt_id", None),
            )
        return VerificationResult(
            status="ACCEPT",
            claim_id=claim.claim_id,
            reason="Vitest suite verified clean: exit code 0 and zero failures.",
            observed_exit_code=0,
            passed_tests=norm.passed,
            receipt_id=getattr(evidence, "receipt_id", None),
        )


class MochaVerifier(Verifier):
    """Verifier for Mocha test runs."""
    verifier_id = "mocha"

    def identify(self, execution: ExecutionIdentity) -> DetectionResult:
        raw = execution.executable_name.lower()
        if "mocha" in raw or (execution.actual_argv and "mocha" in execution.actual_argv[0].lower()):
            return DetectionResult(
                verifier_id="mocha",
                confidence=VerifierConfidence.AUTHORIZED,
                evidence={"binary": "mocha"},
                executable_match=True,
                argv_match=True,
                interpreter_match=False,
            )
        return DetectionResult(verifier_id="generic", confidence=VerifierConfidence.UNKNOWN, evidence={}, executable_match=False, argv_match=False, interpreter_match=False)

    def parse_result(self, observation: Any) -> NormalizedTestResult:
        stdout = getattr(observation, "stdout_content", "") or ""
        stderr = getattr(observation, "stderr_content", "") or ""
        content = stdout + "\n" + stderr
        exit_code = getattr(observation, "exit_code", 0)

        passed = 0
        failed = 0
        m_pass = re.search(r"(\d+)\s+passing", content)
        if m_pass:
            passed = int(m_pass.group(1))
        m_fail = re.search(r"(\d+)\s+failing", content)
        if m_fail:
            failed = int(m_fail.group(1))
        if exit_code != 0 and failed == 0 and passed == 0:
            failed = 1

        return NormalizedTestResult(
            verifier_id="mocha",
            discovered=passed + failed,
            passed=passed,
            failed=failed,
            skipped=0,
            selected_targets=[],
            duration=0.0,
            raw_artifact_hash=compute_output_hash(stdout, stderr),
        )

    def can_verify(self, claim: Claim, evidence: Any) -> bool:
        return getattr(evidence, "verifier", None) == "mocha"

    def verify(self, claim: Claim, evidence: Any, workspace_dir: str = "") -> VerificationResult:
        exit_code = getattr(evidence, "exit_code", 0)
        norm = self.parse_result(evidence)
        if exit_code != 0 or norm.failed > 0:
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Mocha observed {norm.failed} test failure(s) (exit_code={exit_code}).",
                observed_exit_code=exit_code,
                failed_tests=norm.failed,
                passed_tests=norm.passed,
                receipt_id=getattr(evidence, "receipt_id", None),
            )
        return VerificationResult(
            status="ACCEPT",
            claim_id=claim.claim_id,
            reason="Mocha suite verified clean: exit code 0 and zero failures.",
            observed_exit_code=0,
            passed_tests=norm.passed,
            receipt_id=getattr(evidence, "receipt_id", None),
        )


class PlaywrightVerifier(Verifier):
    """Verifier for Playwright test runs."""
    verifier_id = "playwright"

    def identify(self, execution: ExecutionIdentity) -> DetectionResult:
        tokens = list(execution.actual_argv)
        raw = execution.executable_name.lower()
        if "playwright" in raw and len(tokens) > 1 and tokens[1].lower() == "test":
            return DetectionResult(
                verifier_id="playwright",
                confidence=VerifierConfidence.AUTHORIZED,
                evidence={"binary": "playwright", "subcommand": "test"},
                executable_match=True,
                argv_match=True,
                interpreter_match=False,
            )
        return DetectionResult(verifier_id="generic", confidence=VerifierConfidence.UNKNOWN, evidence={}, executable_match=False, argv_match=False, interpreter_match=False)

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
            verifier_id="playwright",
            discovered=passed + failed,
            passed=passed,
            failed=failed,
            skipped=0,
            selected_targets=[],
            duration=0.0,
            raw_artifact_hash=compute_output_hash(stdout, stderr),
        )

    def can_verify(self, claim: Claim, evidence: Any) -> bool:
        return getattr(evidence, "verifier", None) == "playwright"

    def verify(self, claim: Claim, evidence: Any, workspace_dir: str = "") -> VerificationResult:
        exit_code = getattr(evidence, "exit_code", 0)
        norm = self.parse_result(evidence)
        if exit_code != 0 or norm.failed > 0:
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Playwright observed {norm.failed} test failure(s) (exit_code={exit_code}).",
                observed_exit_code=exit_code,
                failed_tests=norm.failed,
                passed_tests=norm.passed,
                receipt_id=getattr(evidence, "receipt_id", None),
            )
        return VerificationResult(
            status="ACCEPT",
            claim_id=claim.claim_id,
            reason="Playwright suite verified clean: exit code 0 and zero failures.",
            observed_exit_code=0,
            passed_tests=norm.passed,
            receipt_id=getattr(evidence, "receipt_id", None),
        )


class CargoTestVerifier(Verifier):
    """Verifier for Cargo (Rust) test runs."""
    verifier_id = "cargo-test"

    def identify(self, execution: ExecutionIdentity) -> DetectionResult:
        tokens = list(execution.actual_argv)
        raw = execution.executable_name.lower()
        if "cargo" in raw and len(tokens) > 1 and tokens[1].lower() == "test":
            return DetectionResult(
                verifier_id="cargo-test",
                confidence=VerifierConfidence.AUTHORIZED,
                evidence={"binary": "cargo", "subcommand": "test"},
                executable_match=True,
                argv_match=True,
                interpreter_match=False,
            )
        return DetectionResult(verifier_id="generic", confidence=VerifierConfidence.UNKNOWN, evidence={}, executable_match=False, argv_match=False, interpreter_match=False)

    def parse_result(self, observation: Any) -> NormalizedTestResult:
        stdout = getattr(observation, "stdout_content", "") or ""
        stderr = getattr(observation, "stderr_content", "") or ""
        content = stdout + "\n" + stderr
        exit_code = getattr(observation, "exit_code", 0)

        passed = 0
        failed = 0
        m_res = re.search(r"test result: (ok|FAILED)\. (\d+) passed; (\d+) failed", content)
        if m_res:
            passed = int(m_res.group(2))
            failed = int(m_res.group(3))
        elif exit_code != 0:
            failed = 1
        elif exit_code == 0:
            passed = 1

        return NormalizedTestResult(
            verifier_id="cargo-test",
            discovered=passed + failed,
            passed=passed,
            failed=failed,
            skipped=0,
            selected_targets=[],
            duration=0.0,
            raw_artifact_hash=compute_output_hash(stdout, stderr),
        )

    def can_verify(self, claim: Claim, evidence: Any) -> bool:
        return getattr(evidence, "verifier", None) in ("cargo", "cargo-test")

    def verify(self, claim: Claim, evidence: Any, workspace_dir: str = "") -> VerificationResult:
        exit_code = getattr(evidence, "exit_code", 0)
        norm = self.parse_result(evidence)
        if exit_code != 0 or norm.failed > 0:
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Cargo test observed {norm.failed} failure(s) (exit_code={exit_code}).",
                observed_exit_code=exit_code,
                failed_tests=norm.failed,
                passed_tests=norm.passed,
                receipt_id=getattr(evidence, "receipt_id", None),
            )
        return VerificationResult(
            status="ACCEPT",
            claim_id=claim.claim_id,
            reason="Cargo test suite verified clean: exit code 0 and zero failures.",
            observed_exit_code=0,
            passed_tests=norm.passed,
            receipt_id=getattr(evidence, "receipt_id", None),
        )


class GoTestVerifier(Verifier):
    """Verifier for Go (go test) test runs."""
    verifier_id = "go-test"

    def identify(self, execution: ExecutionIdentity) -> DetectionResult:
        tokens = list(execution.actual_argv)
        raw = execution.executable_name.lower()
        if "go" in raw and len(tokens) > 1 and tokens[1].lower() == "test":
            return DetectionResult(
                verifier_id="go-test",
                confidence=VerifierConfidence.AUTHORIZED,
                evidence={"binary": "go", "subcommand": "test"},
                executable_match=True,
                argv_match=True,
                interpreter_match=False,
            )
        return DetectionResult(verifier_id="generic", confidence=VerifierConfidence.UNKNOWN, evidence={}, executable_match=False, argv_match=False, interpreter_match=False)

    def parse_result(self, observation: Any) -> NormalizedTestResult:
        stdout = getattr(observation, "stdout_content", "") or ""
        stderr = getattr(observation, "stderr_content", "") or ""
        content = stdout + "\n" + stderr
        exit_code = getattr(observation, "exit_code", 0)

        passed = len(re.findall(r"--- PASS:", content))
        failed = len(re.findall(r"--- FAIL:", content))
        if exit_code != 0 and failed == 0:
            failed = 1
        elif exit_code == 0 and passed == 0:
            passed = 1

        return NormalizedTestResult(
            verifier_id="go-test",
            discovered=passed + failed,
            passed=passed,
            failed=failed,
            skipped=0,
            selected_targets=[],
            duration=0.0,
            raw_artifact_hash=compute_output_hash(stdout, stderr),
        )

    def can_verify(self, claim: Claim, evidence: Any) -> bool:
        return getattr(evidence, "verifier", None) in ("go", "go-test")

    def verify(self, claim: Claim, evidence: Any, workspace_dir: str = "") -> VerificationResult:
        exit_code = getattr(evidence, "exit_code", 0)
        norm = self.parse_result(evidence)
        if exit_code != 0 or norm.failed > 0:
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Go test observed failure(s) (exit_code={exit_code}).",
                observed_exit_code=exit_code,
                failed_tests=norm.failed,
                passed_tests=norm.passed,
                receipt_id=getattr(evidence, "receipt_id", None),
            )
        return VerificationResult(
            status="ACCEPT",
            claim_id=claim.claim_id,
            reason="Go test suite verified clean: exit code 0.",
            observed_exit_code=0,
            passed_tests=norm.passed,
            receipt_id=getattr(evidence, "receipt_id", None),
        )


class NpmTestVerifier(Verifier):
    """Verifier for package script test runners (npm test, pnpm test, yarn test, bun test)."""
    verifier_id = "npm-test"

    def identify(self, execution: ExecutionIdentity) -> DetectionResult:
        tokens = list(execution.actual_argv)
        exe = execution.executable_name.lower()
        if exe in ("npm", "pnpm", "yarn", "bun") and len(tokens) > 1 and tokens[1].lower() in ("test", "run"):
            return DetectionResult(
                verifier_id=f"{exe}-test",
                confidence=VerifierConfidence.AUTHORIZED,
                evidence={"binary": exe, "script": "test"},
                executable_match=True,
                argv_match=True,
                interpreter_match=False,
            )
        return DetectionResult(verifier_id="generic", confidence=VerifierConfidence.UNKNOWN, evidence={}, executable_match=False, argv_match=False, interpreter_match=False)

    def parse_result(self, observation: Any) -> NormalizedTestResult:
        stdout = getattr(observation, "stdout_content", "") or ""
        stderr = getattr(observation, "stderr_content", "") or ""
        exit_code = getattr(observation, "exit_code", 0)
        passed = 1 if exit_code == 0 else 0
        failed = 0 if exit_code == 0 else 1

        return NormalizedTestResult(
            verifier_id="npm-test",
            discovered=1,
            passed=passed,
            failed=failed,
            skipped=0,
            selected_targets=[],
            duration=0.0,
            raw_artifact_hash=compute_output_hash(stdout, stderr),
        )

    def can_verify(self, claim: Claim, evidence: Any) -> bool:
        ver = getattr(evidence, "verifier", "")
        return ver in ("npm", "npm-test", "pnpm", "pnpm-test", "yarn", "yarn-test", "bun", "bun-test")

    def verify(self, claim: Claim, evidence: Any, workspace_dir: str = "") -> VerificationResult:
        exit_code = getattr(evidence, "exit_code", 0)
        norm = self.parse_result(evidence)
        if exit_code != 0:
            return VerificationResult(
                status="REJECT",
                claim_id=claim.claim_id,
                reason=f"Package test script exited with non-zero exit code {exit_code}.",
                observed_exit_code=exit_code,
                failed_tests=1,
                receipt_id=getattr(evidence, "receipt_id", None),
            )
        return VerificationResult(
            status="ACCEPT",
            claim_id=claim.claim_id,
            reason="Package test script verified clean: exit code 0.",
            observed_exit_code=0,
            passed_tests=norm.passed,
            receipt_id=getattr(evidence, "receipt_id", None),
        )
