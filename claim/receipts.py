"""
S-Class EOS V11.2 - D4 Assessment Receipt Minting (§3.10, §7.5).
Generates immutable, Ed25519-signed AssessmentReceipt records.
Uses existing D0/D3 cryptographic authority boundary without new keystores or protocols.
"""

from __future__ import annotations
import hashlib
from typing import Mapping, Sequence, Optional
from domain.models import (
    AssessmentReceipt,
    ClaimAssessment,
    ConflictDetail,
    AsymmetricAuthoritySignature,
    Claim,
)
from domain.types import AssessmentVerdict, ClaimStatus
from events.serializer import canonicalize_json
from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore
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
    signer_identity: str = "Gate3AuthoritativeVerifier",
    timestamp_iso: str = "2026-08-20T00:00:00Z",
) -> AssessmentReceipt:
    """Mints an authentic, Ed25519-signed AssessmentReceipt (§3.10, §7.5).
    
    Reuses Gate3AuthorityKeyStore from the certified authority boundary.
    """
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
        evaluated_at=timestamp_iso,
    )

    canonical_bytes = canonicalize_json(payload)
    payload_digest = hashlib.sha256(canonical_bytes).hexdigest()

    private_key = Gate3AuthorityKeyStore.get_private_key()
    pub_fingerprint = Gate3AuthorityKeyStore.get_public_key_fingerprint()
    sig_bytes = private_key.sign(canonical_bytes)

    authority_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity=signer_identity,
        public_key_fingerprint=pub_fingerprint,
        payload_digest=payload_digest,
        signature_hex=sig_bytes.hex(),
        timestamp=timestamp_iso,
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
        evaluated_at=timestamp_iso,
    )


def verify_assessment_receipt_signature(receipt: AssessmentReceipt) -> bool:
    """Cryptographically verifies the authenticity of an AssessmentReceipt."""
    if not receipt or not receipt.signature:
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
        expected_digest = hashlib.sha256(canonical_bytes).hexdigest()
        if sig.payload_digest != expected_digest:
            return False

        public_key = Gate3AuthorityKeyStore.get_public_key()
        public_key.verify(bytes.fromhex(sig.signature_hex), canonical_bytes)
        return True
    except Exception:
        return False
