"""
S-Class Verification: Verifier Registry.
Manages discovery and selection of pluggable verifiers.
"""

from __future__ import annotations
from typing import Dict, List, Optional

from sclass.domain.claim import Claim
from sclass.domain.evidence import EvidenceReceipt
from sclass.verification.verifiers.base import Verifier
from sclass.verification.verifiers.pytest_verifier import PytestVerifier
from sclass.verification.verifiers.generic_verifier import GenericVerifier


class VerifierRegistry:
    """Registry coordinating available verifier plugins."""

    def __init__(self):
        self._verifiers: Dict[str, Verifier] = {}
        self.register(PytestVerifier())
        self.register(GenericVerifier())

    def register(self, verifier: Verifier) -> None:
        """Registers a verifier plugin."""
        self._verifiers[verifier.verifier_id] = verifier

    def get_verifier(self, verifier_id: str) -> Optional[Verifier]:
        """Gets verifier by ID."""
        return self._verifiers.get(verifier_id)

    def select(self, claim: Claim, evidence: EvidenceReceipt) -> Verifier:
        """Selects the most specific verifier for this claim and evidence."""
        # Check explicit claim verifier request
        if claim.verifier and claim.verifier in self._verifiers:
            return self._verifiers[claim.verifier]

        # Check evidence verifier name
        if evidence.verifier and evidence.verifier in self._verifiers:
            return self._verifiers[evidence.verifier]

        # Check verifiers that can_verify (excluding generic fallback)
        for vid, v in self._verifiers.items():
            if vid != "generic" and v.can_verify(claim, evidence):
                return v

        return self._verifiers.get("generic", GenericVerifier())


_GLOBAL_REGISTRY: Optional[VerifierRegistry] = None


def get_verifier_registry() -> VerifierRegistry:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = VerifierRegistry()
    return _GLOBAL_REGISTRY
