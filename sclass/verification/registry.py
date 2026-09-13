"""
S-Class Verification: Verifier Registry.
Manages discovery, registration, and authoritative selection of verifier plugins.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any

from sclass.domain.claim import Claim
from sclass.domain.evidence import EvidenceReceipt
from sclass.verification.verifiers.base import Verifier
from sclass.verification.verifiers.pytest_verifier import PytestVerifier
from sclass.verification.verifiers.unittest_verifier import UnittestVerifier
from sclass.verification.verifiers.jest_verifier import JestVerifier
from sclass.verification.verifiers.ecosystem_verifiers import (
    VitestVerifier,
    MochaVerifier,
    PlaywrightVerifier,
    CargoTestVerifier,
    GoTestVerifier,
    NpmTestVerifier,
)
from sclass.verification.verifiers.generic_verifier import GenericVerifier


class VerifierRegistry:
    """Registry coordinating all authoritative verifier plugins."""

    def __init__(self):
        self._verifiers: Dict[str, Verifier] = {}
        self.register(PytestVerifier())
        self.register(UnittestVerifier())
        self.register(JestVerifier())
        self.register(VitestVerifier())
        self.register(MochaVerifier())
        self.register(PlaywrightVerifier())
        self.register(CargoTestVerifier())
        self.register(GoTestVerifier())
        self.register(NpmTestVerifier())
        self.register(GenericVerifier())

    def register(self, verifier: Verifier) -> None:
        """Registers a verifier plugin."""
        self._verifiers[verifier.verifier_id] = verifier

    def get_verifier(self, verifier_id: str) -> Optional[Verifier]:
        """Gets verifier by ID."""
        return self._verifiers.get(verifier_id)

    def list_verifiers(self) -> List[str]:
        """Lists registered verifier identifiers."""
        return list(self._verifiers.keys())

    def select(self, claim: Claim, evidence: Any) -> Verifier:
        """
        Authoritatively selects the verifier for claim evaluation.
        Evidence verifier (derived from process identity) is authoritative.
        Caller-supplied verifier in claim is only an untrusted request.
        """
        ev_ver = getattr(evidence, "verifier", None)
        if ev_ver and ev_ver in self._verifiers:
            return self._verifiers[ev_ver]

        # Check aliases (e.g. cargo -> cargo-test)
        if ev_ver:
            for vid, v in self._verifiers.items():
                if vid.startswith(ev_ver):
                    return v

        # Check explicit claim requested verifier if evidence is not yet bound
        claim_ver = getattr(claim, "requested_verifier", getattr(claim, "verifier", None))
        if claim_ver and claim_ver in self._verifiers:
            return self._verifiers[claim_ver]

        # Check verifiers that can_verify
        for vid, v in self._verifiers.items():
            if vid != "generic" and hasattr(v, "can_verify") and v.can_verify(claim, evidence):
                return v

        return self._verifiers.get("generic", GenericVerifier())


_GLOBAL_REGISTRY: Optional[VerifierRegistry] = None


def get_verifier_registry() -> VerifierRegistry:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = VerifierRegistry()
    return _GLOBAL_REGISTRY
