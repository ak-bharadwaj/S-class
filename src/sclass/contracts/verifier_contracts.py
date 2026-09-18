"""Contracts for the V0-V7 verification hierarchy."""
from dataclasses import dataclass
from typing import Dict, Any, List

@dataclass(frozen=True)
class VerifierIdentity:
    verifier_id: str
    trust_tier: str
    executable_sha256: str
    trusted: bool

@dataclass(frozen=True)
class IndependentAssessment:
    claim_id: str
    verifier: VerifierIdentity
    verdict: str  # PASS, FAIL, INCONCLUSIVE
    evidence_ids: List[str]
    details: Dict[str, Any]
