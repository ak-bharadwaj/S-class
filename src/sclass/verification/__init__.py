"""
S-Class Verification Layer.
Pluggable verifiers, claim verification engine, acceptance matrix, and verification planning.
"""

from sclass.verification.verifiers.base import Verifier
from sclass.verification.verifiers.pytest_verifier import PytestVerifier
from sclass.verification.verifiers.generic_verifier import GenericVerifier
from sclass.verification.registry import VerifierRegistry, get_verifier_registry
from sclass.verification.engine import verify_claim, check_staleness
from sclass.verification.state_machine import VerificationState, VerificationStateMachine
from sclass.verification.acceptance import ClaimAcceptanceMatrix, RequiredEvidenceKind
from sclass.verification.plan import VerificationPlan

__all__ = [
    "Verifier",
    "PytestVerifier",
    "GenericVerifier",
    "VerifierRegistry",
    "get_verifier_registry",
    "verify_claim",
    "check_staleness",
    "VerificationState",
    "VerificationStateMachine",
    "ClaimAcceptanceMatrix",
    "RequiredEvidenceKind",
    "VerificationPlan",
]
