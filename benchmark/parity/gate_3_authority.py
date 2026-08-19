"""
S-Class EOS V11.2 - Gate 3 Certificate Authority (D0 Keyed Specification).
Controlled trust boundary for issuing authenticated EvidenceTrustCertificates.
The authority key is never hardcoded; it is injected via the environment or secure keystore.
"""

from __future__ import annotations
import os
import hashlib
import hmac
from typing import Any, Optional

GATE3_AUTHORITY_IDENTITY = "Gate3AuthoritativeVerifier"


def get_gate3_authority_secret() -> Optional[str]:
    """Retrieves authority secret from controlled environment trust boundary."""
    return os.environ.get("GATE3_AUTHORITY_SECRET") or os.environ.get("SCLASS_GATE3_KEY")


def compute_gate3_evidence_digest(evidence: Any) -> str:
    """Computes the authoritative RFC 8785 / JCS canonical digest for an Evidence item."""
    from events.serializer import canonicalize_json
    payload = {
        "evidence_id": evidence.evidence_id,
        "claim_id": evidence.claim_id,
        "provider_id": evidence.provider_id,
        "capability": evidence.capability,
        "execution_id": evidence.execution_id,
        "source_sha": evidence.source_sha,
        "observation": {
            "raw_status": evidence.observation.raw_status.value if hasattr(evidence.observation.raw_status, "value") else str(evidence.observation.raw_status),
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
    canonical_bytes = canonicalize_json(payload)
    return hashlib.sha256(canonical_bytes).hexdigest()


def issue_gate_3_evidence_certificate(
    evidence: Any,
    expected_source_sha: str,
    authority_key: Optional[str] = None,
    verifier_identity: str = GATE3_AUTHORITY_IDENTITY,
) -> Any:
    """Gate 3 Authority: Produces an authentic, signed EvidenceTrustCertificate."""
    from events.serializer import canonicalize_json
    from policy.models import EvidenceTrustCertificate

    secret = authority_key or get_gate3_authority_secret()
    if not secret:
        raise RuntimeError("Gate 3 Certificate Authority secret is not configured in trust boundary.")

    timestamp_iso = "2026-08-19T10:00:00Z"
    
    if not expected_source_sha or evidence.source_sha != expected_source_sha:
        cert_data = {
            "evidence_id": evidence.evidence_id,
            "source_sha": evidence.source_sha,
            "is_verified": False,
            "digest_verified": False,
            "signature_verified": False,
            "provenance_verified": False,
            "verifier_identity": verifier_identity,
            "timestamp": timestamp_iso,
        }
        canonical_bytes = canonicalize_json(cert_data)
        cert_hash = hashlib.sha256(canonical_bytes).hexdigest()
        issuer_sig = hmac.new(secret.encode("utf-8"), canonical_bytes, hashlib.sha256).hexdigest()
        return EvidenceTrustCertificate(
            evidence_id=evidence.evidence_id,
            source_sha=evidence.source_sha,
            is_verified=False,
            digest_verified=False,
            signature_verified=False,
            provenance_verified=False,
            verifier_identity=verifier_identity,
            timestamp=timestamp_iso,
            certificate_hash=cert_hash,
            issuer_signature=issuer_sig,
            rejection_reason="Source revision mismatch or missing.",
        )

    computed_digest = compute_gate3_evidence_digest(evidence)
    claimed_digest = getattr(evidence.signature, "raw_stdout_digest", None)
    digest_verified = (claimed_digest == computed_digest)

    claimed_sig = getattr(evidence.signature, "signature_hex", None)
    expected_hmac = hmac.new(secret.encode("utf-8"), computed_digest.encode("utf-8"), hashlib.sha256).hexdigest()
    signature_verified = bool(claimed_sig and hmac.compare_digest(claimed_sig, expected_hmac))

    prov = evidence.provenance
    provenance_verified = bool(
        prov
        and prov.engine_name
        and not any(f in prov.engine_name.lower() for f in ["synthetic", "simulation", "untrusted"])
        and prov.environment_hash
        and len(prov.environment_hash) == 64
        and prov.timestamp
    )

    is_verified = (digest_verified and signature_verified and provenance_verified)

    cert_data = {
        "evidence_id": evidence.evidence_id,
        "source_sha": evidence.source_sha,
        "is_verified": is_verified,
        "digest_verified": digest_verified,
        "signature_verified": signature_verified,
        "provenance_verified": provenance_verified,
        "verifier_identity": verifier_identity,
        "timestamp": timestamp_iso,
    }
    canonical_bytes = canonicalize_json(cert_data)
    cert_hash = hashlib.sha256(canonical_bytes).hexdigest()
    issuer_sig = hmac.new(secret.encode("utf-8"), canonical_bytes, hashlib.sha256).hexdigest()

    return EvidenceTrustCertificate(
        evidence_id=evidence.evidence_id,
        source_sha=evidence.source_sha,
        is_verified=is_verified,
        digest_verified=digest_verified,
        signature_verified=signature_verified,
        provenance_verified=provenance_verified,
        verifier_identity=verifier_identity,
        timestamp=timestamp_iso,
        certificate_hash=cert_hash,
        issuer_signature=issuer_sig,
    )
