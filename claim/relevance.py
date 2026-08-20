"""
S-Class EOS V11.2 - D4 Relevance Derivation Engine (§7.2).
Formal evaluation of R(C, E) = CapabilityMatch x ScopeMatch x CommitMatch x VerifiedTrust.
Consumes verified trust from D3 EvidenceTrustCertificate without duplicate cryptographic verification.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Any, Sequence
from domain.models import Claim, Evidence
from domain.types import ClaimTier


# Tier-to-Capability Compatibility Matrix (§7.1)
TIER_CAPABILITY_MATRIX = {
    ClaimTier.V0_OBSERVABLE: {"UNIT_TEST_EXECUTION", "API_CONTRACT_FUZZING"},
    ClaimTier.V1_STRUCTURAL: {"STATIC_AST_ANALYSIS", "TYPE_CHECK", "DEPENDENCY_SECURITY_SCAN"},
    ClaimTier.V2_BEHAVIORAL: {"PROPERTY_TESTING", "API_CONTRACT_FUZZING", "UNIT_TEST_EXECUTION"},
    ClaimTier.V3_PROPERTY: {"PROPERTY_TESTING", "API_CONTRACT_FUZZING", "DEPENDENCY_SECURITY_SCAN"},
    ClaimTier.V4_ADVERSARIAL_EXPLORATORY: {"PROVENANCE_BEARING_HUMAN_REVIEW", "PROPERTY_TESTING"},
}


@dataclass(frozen=True)
class RelevanceResult:
    """Formal diagnostic output of Relevance Derivation R(C, E)."""
    is_relevant: bool
    capability_match: bool
    scope_match: bool
    commit_match: bool
    trust_verified: bool
    rejection_reason: Optional[str] = None


def is_capability_compatible(capability: str, required_capabilities: Sequence[str], tier: Optional[ClaimTier] = None) -> bool:
    """Evaluates whether evidence capability satisfies claim requirements or tier taxonomy."""
    if not capability:
        return False
    if required_capabilities:
        return capability in required_capabilities
    if tier and tier in TIER_CAPABILITY_MATRIX:
        return capability in TIER_CAPABILITY_MATRIX[tier]
    return True


def is_scope_compatible(claim: Claim, evidence: Evidence) -> bool:
    """Evaluates whether evidence targets match claim subject identifier."""
    if not claim or not evidence or not evidence.scope:
        return False
    targets = evidence.scope.targets_evaluated
    if not targets:
        return False
    if "*" in targets:
        return True
    return claim.subject.identifier in targets


def evaluate_relevance(
    claim: Claim,
    evidence: Evidence,
    expected_source_sha: str,
    trust_certificate: Optional[Any] = None,
    verified_trust: bool = True,
) -> RelevanceResult:
    """Formal evaluation of Relevance Indicator R(C, E).
    
    R(C, E) = CapabilityMatch x ScopeMatch x CommitMatch x VerifiedTrust
    
    Hard boundary: Consumes D3 EvidenceTrustCertificate / verified_trust result.
    Does not independently perform cryptographic HMAC validation or keystore lookup.
    """
    if not claim or not evidence:
        return RelevanceResult(
            is_relevant=False,
            capability_match=False,
            scope_match=False,
            commit_match=False,
            trust_verified=False,
            rejection_reason="Missing claim or evidence input.",
        )

    # 1. CapabilityMatch
    cap_match = is_capability_compatible(
        evidence.capability,
        claim.required_provider_capabilities,
        claim.tier,
    )
    if not cap_match:
        return RelevanceResult(
            is_relevant=False,
            capability_match=False,
            scope_match=False,
            commit_match=False,
            trust_verified=False,
            rejection_reason=f"Capability mismatch: provider capability '{evidence.capability}' not compatible with claim '{claim.claim_id}'.",
        )

    # 2. ScopeMatch
    scope_match = is_scope_compatible(claim, evidence)
    if not scope_match:
        return RelevanceResult(
            is_relevant=False,
            capability_match=True,
            scope_match=False,
            commit_match=False,
            trust_verified=False,
            rejection_reason=f"Scope mismatch: claim subject '{claim.subject.identifier}' not in evidence targets {evidence.scope.targets_evaluated}.",
        )

    # 3. CommitMatch
    commit_match = bool(expected_source_sha and evidence.source_sha == expected_source_sha)
    if not commit_match:
        return RelevanceResult(
            is_relevant=False,
            capability_match=True,
            scope_match=True,
            commit_match=False,
            trust_verified=False,
            rejection_reason=f"Commit SHA mismatch: evidence SHA '{evidence.source_sha}' != expected HEAD '{expected_source_sha}'.",
        )

    # 4. VerifiedTrust (D3 consumption boundary)
    if trust_certificate is not None:
        trust_ok = bool(
            getattr(trust_certificate, "is_verified", False)
            and getattr(trust_certificate, "evidence_id", None) == evidence.evidence_id
            and getattr(trust_certificate, "source_sha", None) == evidence.source_sha
        )
    else:
        trust_ok = bool(verified_trust)

    if not trust_ok:
        return RelevanceResult(
            is_relevant=False,
            capability_match=True,
            scope_match=True,
            commit_match=True,
            trust_verified=False,
            rejection_reason="Verified trust requirement failed: D3 certificate unverified or absent.",
        )

    return RelevanceResult(
        is_relevant=True,
        capability_match=True,
        scope_match=True,
        commit_match=True,
        trust_verified=True,
        rejection_reason=None,
    )
