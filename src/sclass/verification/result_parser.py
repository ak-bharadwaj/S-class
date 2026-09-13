"""
S-Class Verification: Structured Test Result Parsers.
Extracts normalized test statistics (discovered, passed, failed, skipped, targets, duration)
from machine-readable or structured test runner outputs.
"""

from __future__ import annotations
import re
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


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
    xfailed: int = 0
    xpassed: int = 0

    @property
    def is_successful(self) -> bool:
        """Indicates whether all discovered tests succeeded without failure."""
        return self.failed == 0 and self.passed > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verifier_id": self.verifier_id,
            "discovered": self.discovered,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "xfailed": self.xfailed,
            "xpassed": self.xpassed,
            "selected_targets": list(self.selected_targets),
            "duration": self.duration,
            "raw_artifact_hash": self.raw_artifact_hash,
            "is_successful": self.is_successful,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NormalizedTestResult:
        return cls(
            verifier_id=data.get("verifier_id", "generic"),
            discovered=data.get("discovered", 0),
            passed=data.get("passed", 0),
            failed=data.get("failed", 0),
            skipped=data.get("skipped", 0),
            xfailed=data.get("xfailed", 0),
            xpassed=data.get("xpassed", 0),
            selected_targets=list(data.get("selected_targets", [])),
            duration=data.get("duration", 0.0),
            raw_artifact_hash=data.get("raw_artifact_hash", ""),
        )


def compute_output_hash(stdout: str, stderr: str) -> str:
    """Computes SHA256 digest of process output streams."""
    hasher = hashlib.sha256()
    hasher.update((stdout or "").encode("utf-8"))
    hasher.update((stderr or "").encode("utf-8"))
    return hasher.hexdigest()


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

        # If exit_code != 0 and no failed count extracted, mark at least 1 failure
        if exit_code != 0 and failed == 0 and passed == 0:
            failed = 1

        discovered = passed + failed + skipped + xfailed + xpassed

        return NormalizedTestResult(
            verifier_id="pytest",
            discovered=discovered,
            passed=passed,
            failed=failed,
            skipped=skipped,
            xfailed=xfailed,
            xpassed=xpassed,
            selected_targets=list(targets or []),
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
            discovered=discovered,
            passed=passed,
            failed=failed,
            skipped=0,
            selected_targets=list(targets or []),
            duration=duration,
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
            discovered=discovered,
            passed=passed,
            failed=failed,
            skipped=0,
            selected_targets=list(targets or []),
            duration=0.0,
            raw_artifact_hash=raw_hash,
        )
