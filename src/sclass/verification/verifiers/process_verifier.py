"""
S-Class Verification: ProcessVerifier (Tier V1).
"""
from __future__ import annotations
from typing import Any, Optional, Dict
from sclass.domain.verification import VerificationResult


class ProcessVerifier:
    def __init__(self, expected_exit_code: int = 0, max_duration_ms: float = 5000.0):
        self.expected_exit_code = expected_exit_code
        self.max_duration_ms = max_duration_ms

    def verify(self, receipt: Any) -> VerificationResult:
        exit_code = getattr(receipt, "exit_code", None)
        claim_id = getattr(receipt, "claim_id", "") or ""
        metadata: Dict[str, Any] = getattr(receipt, "metadata", {}) or {}

        duration_ms = metadata.get("duration_ms")
        if duration_ms is not None and float(duration_ms) > self.max_duration_ms:
            return VerificationResult(
                status="REJECT",
                claim_id=claim_id,
                reason=f"Process execution exceeded duration limit: {duration_ms}ms > {self.max_duration_ms}ms",
                observed_exit_code=exit_code,
                metadata={"duration_ms": duration_ms, "max_duration_ms": self.max_duration_ms},
            )

        if exit_code is None:
            return VerificationResult(
                status="REJECT",
                claim_id=claim_id,
                reason="Process receipt missing exit code",
                observed_exit_code=None,
            )

        if exit_code != self.expected_exit_code:
            return VerificationResult(
                status="REJECT",
                claim_id=claim_id,
                reason=f"Process exited with code {exit_code} (expected {self.expected_exit_code})",
                observed_exit_code=exit_code,
            )

        return VerificationResult(
            status="ACCEPT",
            claim_id=claim_id,
            reason=f"Process exited cleanly with code {exit_code}",
            observed_exit_code=exit_code,
            metadata=metadata,
        )
