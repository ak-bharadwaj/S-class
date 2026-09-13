"""
S-Class Verification: Base Verifier Protocol.
Defines canonical verifier lifecycle separating identification, result parsing, and claim evaluation.
"""

from __future__ import annotations
from typing import Protocol, runtime_checkable, Any, Optional

from sclass.domain.claim import Claim
from sclass.domain.evidence import EvidenceReceipt
from sclass.domain.verification import VerificationResult
from sclass.execution.identity import ExecutionIdentity
from sclass.verification.detector import DetectionResult
from sclass.verification.result_parser import NormalizedTestResult


@runtime_checkable
class Verifier(Protocol):
    """Authoritative protocol for pluggable verification engines."""
    verifier_id: str

    def identify(self, execution: ExecutionIdentity) -> DetectionResult:
        """Determines whether this verifier matches the authoritative execution identity."""
        ...

    def parse_result(self, observation: Any) -> NormalizedTestResult:
        """Extracts structured test statistics from the observation evidence."""
        ...

    def verify(self, claim: Claim, evidence: Any, workspace_dir: str = "") -> VerificationResult:
        """Authoritatively evaluates the claim against the independently observed evidence."""
        ...

    def can_verify(self, claim: Claim, evidence: Any) -> bool:
        """Backwards compatibility helper."""
        ...
