"""
S-Class Verification: Base Verifier Protocol.
"""

from __future__ import annotations
from typing import Protocol, runtime_checkable

from sclass.domain.claim import Claim
from sclass.domain.evidence import EvidenceReceipt
from sclass.domain.verification import VerificationResult


@runtime_checkable
class Verifier(Protocol):
    """Protocol for pluggable verification engines."""
    verifier_id: str

    def can_verify(self, claim: Claim, evidence: EvidenceReceipt) -> bool:
        """Returns True if this verifier is qualified to evaluate the given claim and evidence."""
        ...

    def verify(self, claim: Claim, evidence: EvidenceReceipt, workspace_dir: str) -> VerificationResult:
        """Authoritatively evaluates the claim against the independently observed evidence."""
        ...
