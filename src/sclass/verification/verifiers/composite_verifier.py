"""
S-Class Verification: CompositeVerifier (Tier V7).
"""
from __future__ import annotations
from typing import Any, List, Dict
from sclass.domain.verification import VerificationResult


class CompositeVerifier:
    def __init__(self, verifiers: List[Any]):
        self.verifiers = list(verifiers)

    def verify(self, workspace: str, *args, **kwargs) -> VerificationResult:
        failures: Dict[str, str] = {}
        for v in self.verifiers:
            name = getattr(v, "name", v.__class__.__name__)
            try:
                res = v.verify(workspace, *args, **kwargs)
            except TypeError:
                res = v.verify(*args, **kwargs)

            if getattr(res, "is_rejected", False) or getattr(res, "status", "") not in ("ACCEPT", "PASS"):
                failures[name] = getattr(res, "reason", "Verifier rejected")

        if failures:
            failure_keys = list(failures.keys())
            return VerificationResult(
                status="REJECT",
                reason=f"Composite verification failed on sub-verifiers: {failure_keys}. Breakdown: {failures}",
                metadata={"failures": failures}
            )

        return VerificationResult(
            status="ACCEPT",
            reason=f"All {len(self.verifiers)} composite sub-verifiers passed successfully"
        )
