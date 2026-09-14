"""
S-Class Verification: StaticAnalysisVerifier (Tier V4).
"""
from __future__ import annotations
from typing import Any, List, Dict
from sclass.domain.verification import VerificationResult


class StaticAnalysisVerifier:
    def __init__(self, scanner: str = "semgrep", fail_closed: bool = True):
        self.scanner = scanner
        self.fail_closed = fail_closed

    def evaluate_findings(self, findings: List[Dict[str, Any]]) -> VerificationResult:
        high_critical = [
            f for f in findings
            if str(f.get("severity", "")).upper() in ("HIGH", "CRITICAL")
        ]
        if high_critical:
            return VerificationResult(
                status="REJECT",
                reason=f"Static analysis scanner '{self.scanner}' found {len(high_critical)} high/critical vulnerabilities",
                metadata={"findings": high_critical}
            )

        return VerificationResult(
            status="ACCEPT",
            reason=f"Static analysis scanner '{self.scanner}' completed with 0 high/critical vulnerabilities",
            metadata={"total_findings": len(findings)}
        )

    def handle_missing_scanner(self) -> VerificationResult:
        if self.fail_closed:
            return VerificationResult(
                status="REJECT",
                reason=f"Static analysis scanner '{self.scanner}' binary missing from PATH (fail-closed Law L8)",
                metadata={"scanner": self.scanner}
            )
        return VerificationResult(
            status="ACCEPT",
            reason=f"Static analysis scanner '{self.scanner}' binary missing but scanner is optional",
            metadata={"scanner": self.scanner}
        )
