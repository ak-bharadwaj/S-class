"""
S-Class EOS V11.2 - D4 Assessment Receipt Minting (§3.10, §7.5).
Generates immutable, Ed25519-signed AssessmentReceipt records.
Consumes narrow D3 Authority interface (AuthoritySignerProtocol) without direct access to private key material.
Requires explicit evaluated_at timestamp (no hidden defaults).
Preserves conflict lineage and dual evidence in ClaimAssessment and AssessmentReceipt.
"""

from __future__ import annotations
from typing import Mapping, Sequence
from domain.models import (
    AssessmentReceipt,
    ClaimAssessment,
    ConflictDetail,
    AsymmetricAuthoritySignature,
    Claim,
)
from domain.types import AssessmentVerdict, ClaimStatus
from events.serializer import canonicalize_json
from policy.models import AuthoritySignerProtocol
from claim.reducer import ClaimReductionState, ClaimEpistemicState


def _build_receipt_payload(
    receipt_id: str,
    obligation_id: str,
    policy_version: int,
    repository_sha: str,
    verdict: AssessmentVerdict,
    claim_assessments: Sequence[ClaimAssessment],
    conflicts: Sequence[ConflictDetail],
    stale_evidence: Sequence[str],
    evaluated_at: str,
) -> dict:
    return {
        "receipt_id": receipt_id,
        "obligation_id": obligation_id,
        "policy_version": policy_version,
        "repository_sha": repository_sha,
        "verdict": verdict.value if hasattr(verdict, "value") else str(verdict),
        "claim_assessments": [
            {
                "claim_id": ca.claim_id,
                "status": ca.status.value if hasattr(ca.status, "value") else str(ca.status),
                "supporting_evidence_ids": list(ca.supporting_evidence_ids),
                "refuting_evidence_ids": list(ca.refuting_evidence_ids),
            }
            for ca in sorted(claim_assessments, key=lambda x: x.claim_id)
        ],
        "conflicts": [
            {
                "claim_id": cf.claim_id,
                "evidence_ids": list(cf.evidence_ids),
                "description": cf.description,
            }
            for cf in sorted(conflicts, key=lambda x: x.claim_id)
        ],
        "stale_evidence": sorted(list(set(stale_evidence))),
        "evaluated_at": evaluated_at,
    }


def mint_assessment_receipt(
    receipt_id: str,
    obligation_id: str,
    policy_version: int,
    repository_sha: str,
    claim_states: Mapping[str, ClaimReductionState],
    intended_claims: Mapping[str, Claim],
    evaluated_at: str,
    authority_signer: AuthoritySignerProtocol,
    signer_identity: str = "Gate3AuthoritativeVerifier",
) -> AssessmentReceipt:
    """Mints an authentic, Ed25519-signed AssessmentReceipt (§3.10, §7.5).
    
    Consumes narrow authority interface (AuthoritySignerProtocol) without direct private key access.
    Requires explicit evaluated_at timestamp.
    """
    if not evaluated_at or not isinstance(evaluated_at, str):
        raise ValueError("evaluated_at timestamp is required and must be a non-empty ISO-8601 string.")
    if not isinstance(authority_signer, AuthoritySignerProtocol):
        raise TypeError("authority_signer must implement AuthoritySignerProtocol.")

    claim_assessments: list[ClaimAssessment] = []
    conflicts: list[ConflictDetail] = []
    stale_evidence: list[str] = []

    all_satisfied = True

    for claim_id, claim in intended_claims.items():
        state = claim_states.get(claim_id)
        if not state:
            status = ClaimStatus.UNSUPPORTED
            all_satisfied = False
            claim_assessments.append(
                ClaimAssessment(
                    claim_id=claim_id,
                    status=status,
                    supporting_evidence_ids=(),
                    refuting_evidence_ids=(),
                )
            )
            continue

        domain_status = state.epistemic_state.to_domain_status()
        if state.epistemic_state != ClaimEpistemicState.SUPPORTED:
            all_satisfied = False

        claim_assessments.append(
            ClaimAssessment(
                claim_id=claim_id,
                status=domain_status,
                supporting_evidence_ids=state.supporting_evidence_ids,
                refuting_evidence_ids=state.refuting_evidence_ids,
            )
        )

        if state.conflicts:
            conflicts.append(
                ConflictDetail(
                    claim_id=claim_id,
                    evidence_ids=state.supporting_evidence_ids + state.refuting_evidence_ids,
                    description="; ".join(state.conflicts),
                )
            )

        stale_evidence.extend(state.stale_evidence_ids)

    verdict = AssessmentVerdict.SATISFIED if all_satisfied else AssessmentVerdict.REJECTED

    payload = _build_receipt_payload(
        receipt_id=receipt_id,
        obligation_id=obligation_id,
        policy_version=policy_version,
        repository_sha=repository_sha,
        verdict=verdict,
        claim_assessments=claim_assessments,
        conflicts=conflicts,
        stale_evidence=stale_evidence,
        evaluated_at=evaluated_at,
    )

    canonical_bytes = canonicalize_json(payload)
    authority_sig = authority_signer.sign_payload(
        canonical_bytes=canonical_bytes,
        verifier_identity=signer_identity,
        timestamp_iso=evaluated_at,
    )

    return AssessmentReceipt(
        receipt_id=receipt_id,
        obligation_id=obligation_id,
        policy_version=policy_version,
        repository_sha=repository_sha,
        verdict=verdict,
        claim_assessments=tuple(claim_assessments),
        signature=authority_sig,
        conflicts=tuple(conflicts),
        stale_evidence=tuple(sorted(list(set(stale_evidence)))),
        evaluated_at=evaluated_at,
    )


def verify_assessment_receipt_signature(
    receipt: AssessmentReceipt,
    authority_signer: AuthoritySignerProtocol,
) -> bool:
    """Cryptographically verifies the authenticity of an AssessmentReceipt via D3 Authority interface."""
    if not receipt or not receipt.signature:
        return False
    if not isinstance(authority_signer, AuthoritySignerProtocol):
        return False
    sig = receipt.signature
    if sig.algorithm != "ED25519":
        return False

    payload = _build_receipt_payload(
        receipt_id=receipt.receipt_id,
        obligation_id=receipt.obligation_id,
        policy_version=receipt.policy_version,
        repository_sha=receipt.repository_sha,
        verdict=receipt.verdict,
        claim_assessments=receipt.claim_assessments,
        conflicts=receipt.conflicts,
        stale_evidence=receipt.stale_evidence,
        evaluated_at=receipt.evaluated_at,
    )

    try:
        canonical_bytes = canonicalize_json(payload)
        return authority_signer.verify_signature(canonical_bytes, sig)
    except (ValueError, TypeError, KeyError):
        return False
