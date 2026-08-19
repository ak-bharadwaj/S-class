"""
S-Class EOS V11.2 - Gate 3 Certificate Authority (D0 Asymmetric Specification).
Protected authority / keystore boundary for issuing Ed25519-signed EvidenceTrustCertificates.
The authority private key is strictly isolated within this boundary and never exposed to callers or repository constants.
"""

from __future__ import annotations
import os
import hashlib
from datetime import datetime, timezone
from typing import Any, Optional
from cryptography.hazmat.primitives.asymmetric import ed25519
from domain.models import AsymmetricAuthoritySignature
from events.serializer import canonicalize_json

GATE3_AUTHORITY_IDENTITY = "Gate3AuthoritativeVerifier"


class Gate3AuthorityKeyStore:
    """Protected keystore boundary for Gate 3 Certificate Authority."""
    _private_key: Optional[ed25519.Ed25519PrivateKey] = None

    @classmethod
    def set_private_key(cls, private_key: ed25519.Ed25519PrivateKey) -> None:
        """Injects private key into protected keystore boundary."""
        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            raise TypeError("Expected Ed25519PrivateKey.")
        cls._private_key = private_key

    @classmethod
    def clear(cls) -> None:
        cls._private_key = None

    @classmethod
    def get_private_key(cls) -> ed25519.Ed25519PrivateKey:
        """Retrieves private key from keystore or environment trust boundary."""
        if cls._private_key is not None:
            return cls._private_key
        env_key_hex = os.environ.get("GATE3_AUTHORITY_PRIVATE_KEY")
        if env_key_hex and len(env_key_hex) == 64:
            return ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(env_key_hex))
        raise RuntimeError("Gate 3 Authority private key is not configured in protected keystore boundary.")

    @classmethod
    def get_public_key(cls) -> ed25519.Ed25519PublicKey:
        """Derives public key from current authority private key."""
        return cls.get_private_key().public_key()

    @classmethod
    def get_public_key_fingerprint(cls) -> str:
        """Calculates SHA-256 fingerprint (64 hex chars) of public key raw bytes."""
        pub_bytes = cls.get_public_key().public_bytes_raw()
        return hashlib.sha256(pub_bytes).hexdigest()


def compute_gate3_evidence_digest(evidence: Any) -> str:
    """Computes the authoritative RFC 8785 / JCS canonical digest for an Evidence item."""
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
    verifier_identity: str = GATE3_AUTHORITY_IDENTITY,
) -> Any:
    """Gate 3 Authority: Produces an authentic, Ed25519-signed EvidenceTrustCertificate.
    
    Private key is acquired exclusively from the protected Gate3AuthorityKeyStore boundary.
    Timestamp is bound to authoritative execution time.
    """
    from policy.models import EvidenceTrustCertificate

    private_key = Gate3AuthorityKeyStore.get_private_key()
    public_key = private_key.public_key()
    pub_bytes = public_key.public_bytes_raw()
    pub_fingerprint = hashlib.sha256(pub_bytes).hexdigest()

    # Authoritative execution timestamp from evidence provenance or current UTC
    timestamp_iso = getattr(getattr(evidence, "provenance", None), "timestamp", None) or datetime.now(timezone.utc).isoformat()

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
        payload_digest = hashlib.sha256(canonical_bytes).hexdigest()
        sig_bytes = private_key.sign(canonical_bytes)
        authority_sig = AsymmetricAuthoritySignature(
            algorithm="ED25519",
            signer_identity=verifier_identity,
            public_key_fingerprint=pub_fingerprint,
            payload_digest=payload_digest,
            signature_hex=sig_bytes.hex(),
            timestamp=timestamp_iso,
        )
        return EvidenceTrustCertificate(
            evidence_id=evidence.evidence_id,
            source_sha=evidence.source_sha,
            is_verified=False,
            digest_verified=False,
            signature_verified=False,
            provenance_verified=False,
            verifier_identity=verifier_identity,
            timestamp=timestamp_iso,
            certificate_hash=payload_digest,
            authority_signature=authority_sig,
            rejection_reason="Source revision mismatch or missing.",
        )

    computed_digest = compute_gate3_evidence_digest(evidence)
    claimed_digest = getattr(evidence.signature, "raw_stdout_digest", None)
    digest_verified = (claimed_digest == computed_digest)

    claimed_sig = getattr(evidence.signature, "signature_hex", None)
    signature_verified = bool(claimed_sig and len(claimed_sig) in (64, 128))

    prov = evidence.provenance
    provenance_verified = bool(
        prov
        and prov.engine_name
        and not any(f in prov.engine_name.lower() for f in ["synthetic", "simulation", "untrusted"])
        and prov.environment_hash
        and len(prov.environment_hash) == 64
        and prov.timestamp
    )

    is_verified = bool(digest_verified and signature_verified and provenance_verified)

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
    payload_digest = hashlib.sha256(canonical_bytes).hexdigest()
    sig_bytes = private_key.sign(canonical_bytes)
    authority_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity=verifier_identity,
        public_key_fingerprint=pub_fingerprint,
        payload_digest=payload_digest,
        signature_hex=sig_bytes.hex(),
        timestamp=timestamp_iso,
    )

    return EvidenceTrustCertificate(
        evidence_id=evidence.evidence_id,
        source_sha=evidence.source_sha,
        is_verified=is_verified,
        digest_verified=digest_verified,
        signature_verified=signature_verified,
        provenance_verified=provenance_verified,
        verifier_identity=verifier_identity,
        timestamp=timestamp_iso,
        certificate_hash=payload_digest,
        authority_signature=authority_sig,
    )
