"""Gate 3 / D0 Certified Provenance & HMAC Verifier Interface for S-Class EOS."""

import hashlib
import hmac
import json
from typing import Optional

from domain.models import Evidence
from policy.models import EvidenceTrustCertificate

DEFAULT_SESSION_KEY = "SCLASS_HMAC_SESSION_SECRET_KEY_001"


def compute_canonical_evidence_digest(evidence: Evidence) -> str:
    """Computes deterministic canonical SHA-256 digest over the observation and provenance payload."""
    payload = {
        "evidence_id": evidence.evidence_id,
        "claim_id": evidence.claim_id,
        "provider_id": evidence.provider_id,
        "capability": evidence.capability,
        "execution_id": evidence.execution_id,
        "source_sha": evidence.source_sha,
        "observation": {
            "raw_status": getattr(evidence.observation.raw_status, "value", str(evidence.observation.raw_status)),
            "diagnostics": list(evidence.observation.diagnostics),
            "counterexample": evidence.observation.counterexample,
        },
        "provenance": {
            "engine_name": evidence.provenance.engine_name,
            "engine_version": evidence.provenance.engine_version,
            "environment_hash": evidence.provenance.environment_hash,
            "timestamp": evidence.provenance.timestamp,
        },
    }
    canonical_bytes = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def compute_evidence_hmac(digest: str, secret_key: str = DEFAULT_SESSION_KEY) -> str:
    """Computes keyed HMAC-SHA256 signature for a verified digest."""
    return hmac.new(secret_key.encode("utf-8"), digest.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_evidence_authenticity(
    evidence: Evidence,
    expected_source_sha: Optional[str],
    secret_key: str = DEFAULT_SESSION_KEY,
) -> EvidenceTrustCertificate:
    """Authoritative verifier producing immutable EvidenceTrustCertificate for D3 consumption."""
    ev_id = getattr(evidence, "evidence_id", "UNKNOWN")
    act_sha = getattr(evidence, "source_sha", "")

    if not expected_source_sha:
        return EvidenceTrustCertificate(
            evidence_id=ev_id,
            source_sha=act_sha,
            is_verified=False,
            digest_verified=False,
            signature_verified=False,
            provenance_verified=False,
            rejection_reason="Missing expected source revision for evaluation context.",
        )

    if act_sha != expected_source_sha:
        return EvidenceTrustCertificate(
            evidence_id=ev_id,
            source_sha=act_sha,
            is_verified=False,
            digest_verified=False,
            signature_verified=False,
            provenance_verified=False,
            rejection_reason=f"Source revision mismatch: expected '{expected_source_sha}', got '{act_sha}'.",
        )

    # 1. Recompute canonical digest
    computed_digest = compute_canonical_evidence_digest(evidence)
    claimed_digest = getattr(getattr(evidence, "signature", None), "raw_stdout_digest", None)
    if not claimed_digest or claimed_digest != computed_digest:
        return EvidenceTrustCertificate(
            evidence_id=ev_id,
            source_sha=act_sha,
            is_verified=False,
            digest_verified=False,
            signature_verified=False,
            provenance_verified=True,
            rejection_reason=f"Observation digest tampering: claimed '{claimed_digest}', computed '{computed_digest}'.",
        )

    # 2. Verify HMAC cryptographic signature
    claimed_sig = getattr(getattr(evidence, "signature", None), "signature_hex", None)
    expected_sig = compute_evidence_hmac(computed_digest, secret_key)
    if not claimed_sig or not hmac.compare_digest(claimed_sig, expected_sig):
        return EvidenceTrustCertificate(
            evidence_id=ev_id,
            source_sha=act_sha,
            is_verified=False,
            digest_verified=True,
            signature_verified=False,
            provenance_verified=True,
            rejection_reason="HMAC signature verification failed: invalid or forged signature.",
        )

    return EvidenceTrustCertificate(
        evidence_id=ev_id,
        source_sha=act_sha,
        is_verified=True,
        digest_verified=True,
        signature_verified=True,
        provenance_verified=True,
    )
