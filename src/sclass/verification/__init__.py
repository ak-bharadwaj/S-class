"""
S-Class Verification Layer.
Pluggable verifiers and claim verification engine.
"""

from sclass.verification.verifiers.base import Verifier
from sclass.verification.verifiers.pytest_verifier import PytestVerifier
from sclass.verification.verifiers.generic_verifier import GenericVerifier
from sclass.verification.registry import VerifierRegistry, get_verifier_registry
from sclass.verification.engine import verify_claim, check_staleness

__all__ = [
    "Verifier",
    "PytestVerifier",
    "GenericVerifier",
    "VerifierRegistry",
    "get_verifier_registry",
    "verify_claim",
    "check_staleness",
]
