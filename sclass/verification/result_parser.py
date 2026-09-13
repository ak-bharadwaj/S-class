"""
S-Class Verification: Structured Test Result Parsers.
Extracts normalized test statistics (verifier_id, runner_version, discovered, passed,
failed, skipped, selected_targets, test_files, duration, artifact_hash)
from machine-readable and structured test runner outputs:
- pytest
- unittest
- jest
- vitest
- mocha
- playwright
- cargo test
- go test
- npm test
- pnpm test
- yarn test
- bun test
"""

from __future__ import annotations
import re
import json
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


def compute_output_hash(stdout: str, stderr: str) -> str:
    """Computes SHA256 digest of process output streams."""
    hasher = hashlib.sha256()
    hasher.update((stdout or "").encode("utf-8"))
    hasher.update((stderr or "").encode("utf-8"))
    return hasher.hexdigest()


@dataclass(frozen=True)
class NormalizedTestResult:
    """Authoritative normalized test execution metrics."""
    verifier_id: str
    discovered: int
    passed: int
    failed: int
    skipped: int
    selected_targets: List[str]
    duration: float
    raw_artifact_hash: str
    runner_version: Optional[str] = None
    test_files: List[str] = field(default_factory=list)
    xfailed: int = 0
    xpassed: int = 0

    @property
    def artifact_hash(self) -> str:
        return self.raw_artifact_hash

    @property
    def is_successful(self) -> bool:
        """Indicates whether all discovered tests succeeded without failure."""
        return self.failed == 0 and self.passed > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verifier_id": self.verifier_id,
            "runner_version": self.runner_version,
            "discovered": self.discovered,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "xfailed": self.xfailed,
            "xpassed": self.xpassed,
            "selected_targets": list(self.selected_targets),
            "test_files": list(self.test_files),
            "duration": self.duration,
            "raw_artifact_hash": self.raw_artifact_hash,
            "artifact_hash": self.raw_artifact_hash,
            "is_successful": self.is_successful,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NormalizedTestResult:
        return cls(
            verifier_id=data.get("verifier_id", "generic"),
            runner_version=data.get("runner_version"),
            discovered=data.get("discovered", 0),
            passed=data.get("passed", 0),
            failed=data.get("failed", 0),
            skipped=data.get("skipped", 0),
            xfailed=data.get("xfailed", 0),
            xpassed=data.get("xpassed", 0),
            selected_targets=list(data.get("selected_targets", [])),
            test_files=list(data.get("test_files", [])),
            duration=data.get("duration", 0.0),
            raw_artifact_hash=data.get("raw_artifact_hash") or data.get("artifact_hash", ""),
        )


class PytestResultParser:
    """Extracts structured results from pytest stdout/stderr streams."""

    @staticmethod
    def parse(stdout: str, stderr: str, exit_code: int, targets: Optional[List[str]] = None) -> NormalizedTestResult:
        content = stdout + "\n" + stderr
        raw_hash = compute_output_hash(stdout, stderr)

        passed = 0
        failed = 0
        skipped = 0
        xfailed = 0
        xpassed = 0
        duration = 0.0
        runner_version = None

        m_ver = re.search(r"pytest-([\d\.]+)", content)
        if m_ver:
            runner_version = m_ver.group(1)

        # Pattern: "=== 10 passed, 2 failed, 1 skipped in 1.23s ==="
        m_passed = re.search(r"(\d+)\s+passed", content)
        if m_passed:
            passed = int(m_passed.group(1))

        m_failed = re.search(r"(\d+)\s+failed", content)
        if m_failed:
            failed = int(m_failed.group(1))

        m_skipped = re.search(r"(\d+)\s+skipped", content)
        if m_skipped:
            skipped = int(m_skipped.group(1))

        m_xfail = re.search(r"(\d+)\s+xfailed", content)
        if m_xfail:
            xfailed = int(m_xfail.group(1))

        m_xpass = re.search(r"(\d+)\s+xpassed", content)
        if m_xpass:
            xpassed = int(m_xpass.group(1))

        m_dur = re.search(r"in\s+([\d\.]+)\s*s", content)
        if m_dur:
            try:
                duration = float(m_dur.group(1))
            except ValueError:
                pass

        # Extract test files
        test_files = []
        for line in content.splitlines():
            m_file = re.search(r"^([a-zA-Z0-9_\-\\/]+\.py)", line.strip())
            if m_file:
                test_files.append(m_file.group(1))

        if exit_code != 0 and failed == 0 and passed == 0:
            failed = 1

        discovered = passed + failed + skipped + xfailed + xpassed

        return NormalizedTestResult(
            verifier_id="pytest",
            runner_version=runner_version,
            discovered=discovered,
            passed=passed,
            failed=failed,
            skipped=skipped,
            xfailed=xfailed,
            xpassed=xpassed,
            selected_targets=list(targets or []),
            test_files=sorted(list(set(test_files))),
            duration=duration,
            raw_artifact_hash=raw_hash,
        )


class UnittestResultParser:
    """Extracts structured results from standard unittest output."""

    @staticmethod
    def parse(stdout: str, stderr: str, exit_code: int, targets: Optional[List[str]] = None) -> NormalizedTestResult:
        content = stdout + "\n" + stderr
        raw_hash = compute_output_hash(stdout, stderr)

        discovered = 0
        failed = 0
        passed = 0
        duration = 0.0

        m_ran = re.search(r"Ran\s+(\d+)\s+tests?\s+in\s+([\d\.]+)s", content)
        if m_ran:
            discovered = int(m_ran.group(1))
            try:
                duration = float(m_ran.group(2))
            except ValueError:
                pass

        if "FAILED" in content:
            m_failures = re.search(r"failures=(\d+)", content)
            m_errors = re.search(r"errors=(\d+)", content)
            fail_cnt = int(m_failures.group(1)) if m_failures else 0
            err_cnt = int(m_errors.group(1)) if m_errors else 0
            failed = fail_cnt + err_cnt
            if failed == 0:
                failed = 1
            passed = max(0, discovered - failed)
        elif "OK" in content:
            passed = discovered
            failed = 0
        elif exit_code != 0:
            failed = 1
            discovered = max(1, discovered)

        return NormalizedTestResult(
            verifier_id="unittest",
            runner_version=None,
            discovered=discovered,
            passed=passed,
            failed=failed,
            skipped=0,
            selected_targets=list(targets or []),
            test_files=[],
            duration=duration,
            raw_artifact_hash=raw_hash,
        )


class JestResultParser:
    """Extracts structured results from Jest test runs."""

    @staticmethod
    def parse(stdout: str, stderr: str, exit_code: int, targets: Optional[List[str]] = None) -> NormalizedTestResult:
        content = stdout + "\n" + stderr
        raw_hash = compute_output_hash(stdout, stderr)

        passed = 0
        failed = 0
        skipped = 0
        duration = 0.0

        m_pass = re.search(r"Tests:\s+.*?(\d+)\s+passed", content)
        if m_pass:
            passed = int(m_pass.group(1))
        m_fail = re.search(r"Tests:\s+.*?(\d+)\s+failed", content)
        if m_fail:
            failed = int(m_fail.group(1))
        m_skip = re.search(r"Tests:\s+.*?(\d+)\s+skipped", content)
        if m_skip:
            skipped = int(m_skip.group(1))

        m_dur = re.search(r"Time:\s+([\d\.]+)\s*s", content)
        if m_dur:
            try:
                duration = float(m_dur.group(1))
            except ValueError:
                pass

        if exit_code != 0 and failed == 0 and passed == 0:
            failed = 1

        discovered = passed + failed + skipped
        if discovered == 0 and passed > 0:
            discovered = passed

        return NormalizedTestResult(
            verifier_id="jest",
            runner_version=None,
            discovered=discovered,
            passed=passed,
            failed=failed,
            skipped=skipped,
            selected_targets=list(targets or []),
            test_files=[],
            duration=duration,
            raw_artifact_hash=raw_hash,
        )


class VitestResultParser:
    """Extracts structured results from Vitest test runs."""

    @staticmethod
    def parse(stdout: str, stderr: str, exit_code: int, targets: Optional[List[str]] = None) -> NormalizedTestResult:
        content = stdout + "\n" + stderr
        raw_hash = compute_output_hash(stdout, stderr)

        passed = 0
        failed = 0
        skipped = 0
        duration = 0.0

        m_pass = re.search(r"(\d+)\s+passed", content)
        if m_pass:
            passed = int(m_pass.group(1))
        m_fail = re.search(r"(\d+)\s+failed", content)
        if m_fail:
            failed = int(m_fail.group(1))
        m_skip = re.search(r"(\d+)\s+skipped", content)
        if m_skip:
            skipped = int(m_skip.group(1))

        m_dur = re.search(r"Duration\s+([\d\.]+)\s*s", content)
        if m_dur:
            try:
                duration = float(m_dur.group(1))
            except ValueError:
                pass

        if exit_code != 0 and failed == 0 and passed == 0:
            failed = 1

        discovered = passed + failed + skipped

        return NormalizedTestResult(
            verifier_id="vitest",
            runner_version=None,
            discovered=discovered,
            passed=passed,
            failed=failed,
            skipped=skipped,
            selected_targets=list(targets or []),
            test_files=[],
            duration=duration,
            raw_artifact_hash=raw_hash,
        )


class MochaResultParser:
    """Extracts structured results from Mocha test runs."""

    @staticmethod
    def parse(stdout: str, stderr: str, exit_code: int, targets: Optional[List[str]] = None) -> NormalizedTestResult:
        content = stdout + "\n" + stderr
        raw_hash = compute_output_hash(stdout, stderr)

        passed = 0
        failed = 0
        duration = 0.0

        m_pass = re.search(r"(\d+)\s+passing(?:\s+\(([\d\.]+m?s)\))?", content)
        if m_pass:
            passed = int(m_pass.group(1))
            if m_pass.group(2):
                dur_str = m_pass.group(2)
                try:
                    if dur_str.endswith("ms"):
                        duration = float(dur_str[:-2]) / 1000.0
                    elif dur_str.endswith("s"):
                        duration = float(dur_str[:-1])
                except ValueError:
                    pass

        m_fail = re.search(r"(\d+)\s+failing", content)
        if m_fail:
            failed = int(m_fail.group(1))

        if exit_code != 0 and failed == 0 and passed == 0:
            failed = 1

        return NormalizedTestResult(
            verifier_id="mocha",
            runner_version=None,
            discovered=passed + failed,
            passed=passed,
            failed=failed,
            skipped=0,
            selected_targets=list(targets or []),
            test_files=[],
            duration=duration,
            raw_artifact_hash=raw_hash,
        )


class PlaywrightResultParser:
    """Extracts structured results from Playwright test runs."""

    @staticmethod
    def parse(stdout: str, stderr: str, exit_code: int, targets: Optional[List[str]] = None) -> NormalizedTestResult:
        content = stdout + "\n" + stderr
        raw_hash = compute_output_hash(stdout, stderr)

        passed = 0
        failed = 0
        skipped = 0
        duration = 0.0

        m_pass = re.search(r"(\d+)\s+passed(?:\s+\(([\d\.]+m?s)\))?", content)
        if m_pass:
            passed = int(m_pass.group(1))
            if m_pass.group(2):
                dur_str = m_pass.group(2)
                try:
                    if dur_str.endswith("ms"):
                        duration = float(dur_str[:-2]) / 1000.0
                    elif dur_str.endswith("s"):
                        duration = float(dur_str[:-1])
                except ValueError:
                    pass

        m_fail = re.search(r"(\d+)\s+failed", content)
        if m_fail:
            failed = int(m_fail.group(1))
        m_skip = re.search(r"(\d+)\s+skipped", content)
        if m_skip:
            skipped = int(m_skip.group(1))

        if exit_code != 0 and failed == 0 and passed == 0:
            failed = 1

        return NormalizedTestResult(
            verifier_id="playwright",
            runner_version=None,
            discovered=passed + failed + skipped,
            passed=passed,
            failed=failed,
            skipped=skipped,
            selected_targets=list(targets or []),
            test_files=[],
            duration=duration,
            raw_artifact_hash=raw_hash,
        )


class CargoTestResultParser:
    """Extracts structured results from Cargo (Rust) test runs."""

    @staticmethod
    def parse(stdout: str, stderr: str, exit_code: int, targets: Optional[List[str]] = None) -> NormalizedTestResult:
        content = stdout + "\n" + stderr
        raw_hash = compute_output_hash(stdout, stderr)

        passed = 0
        failed = 0
        skipped = 0

        # Pattern: test result: ok. 12 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out
        m_res = re.search(r"test result:\s+(\w+)\.\s+(\d+)\s+passed;\s+(\d+)\s+failed;\s+(\d+)\s+ignored", content)
        if m_res:
            passed = int(m_res.group(2))
            failed = int(m_res.group(3))
            skipped = int(m_res.group(4))

        if exit_code != 0 and failed == 0 and passed == 0:
            failed = 1

        return NormalizedTestResult(
            verifier_id="cargo-test",
            runner_version=None,
            discovered=passed + failed + skipped,
            passed=passed,
            failed=failed,
            skipped=skipped,
            selected_targets=list(targets or []),
            test_files=[],
            duration=0.0,
            raw_artifact_hash=raw_hash,
        )


class GoTestResultParser:
    """Extracts structured results from go test runs."""

    @staticmethod
    def parse(stdout: str, stderr: str, exit_code: int, targets: Optional[List[str]] = None) -> NormalizedTestResult:
        content = stdout + "\n" + stderr
        raw_hash = compute_output_hash(stdout, stderr)

        passed = len(re.findall(r"--- PASS:", content))
        failed = len(re.findall(r"--- FAIL:", content))
        skipped = len(re.findall(r"--- SKIP:", content))
        duration = 0.0

        m_ok = re.search(r"ok\s+[^\s]+\s+([\d\.]+)s", content)
        if m_ok:
            try:
                duration = float(m_ok.group(1))
            except ValueError:
                pass
            if passed == 0 and failed == 0:
                passed = 1

        if exit_code != 0 and failed == 0 and passed == 0:
            failed = 1

        discovered = passed + failed + skipped

        return NormalizedTestResult(
            verifier_id="go-test",
            runner_version=None,
            discovered=discovered,
            passed=passed,
            failed=failed,
            skipped=skipped,
            selected_targets=list(targets or []),
            test_files=[],
            duration=duration,
            raw_artifact_hash=raw_hash,
        )


class PackageScriptResultParser:
    """Extracts structured results from npm/pnpm/yarn/bun package runners."""

    @staticmethod
    def parse(verifier_id: str, stdout: str, stderr: str, exit_code: int, targets: Optional[List[str]] = None) -> NormalizedTestResult:
        content = stdout + "\n" + stderr
        raw_hash = compute_output_hash(stdout, stderr)

        # Delegate to jest/vitest/mocha parser if their patterns appear in output
        if "Tests:" in content and "passed" in content:
            res = JestResultParser.parse(stdout, stderr, exit_code, targets)
            return NormalizedTestResult(
                verifier_id=verifier_id,
                runner_version=res.runner_version,
                discovered=res.discovered,
                passed=res.passed,
                failed=res.failed,
                skipped=res.skipped,
                selected_targets=list(targets or []),
                test_files=res.test_files,
                duration=res.duration,
                raw_artifact_hash=raw_hash,
            )

        passed = 1 if exit_code == 0 else 0
        failed = 0 if exit_code == 0 else 1

        return NormalizedTestResult(
            verifier_id=verifier_id,
            runner_version=None,
            discovered=1,
            passed=passed,
            failed=failed,
            skipped=0,
            selected_targets=list(targets or []),
            test_files=[],
            duration=0.0,
            raw_artifact_hash=raw_hash,
        )


class GenericResultParser:
    """Fallback result parser for non-structured runners."""

    @staticmethod
    def parse(verifier_id: str, stdout: str, stderr: str, exit_code: int, targets: Optional[List[str]] = None) -> NormalizedTestResult:
        raw_hash = compute_output_hash(stdout, stderr)
        passed = 1 if exit_code == 0 else 0
        failed = 0 if exit_code == 0 else 1
        discovered = 1

        return NormalizedTestResult(
            verifier_id=verifier_id,
            runner_version=None,
            discovered=discovered,
            passed=passed,
            failed=failed,
            skipped=0,
            selected_targets=list(targets or []),
            test_files=[],
            duration=0.0,
            raw_artifact_hash=raw_hash,
        )
