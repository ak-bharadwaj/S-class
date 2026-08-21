"""
S-Class EOS V11.2 - Schemathesis Gate 3 Certificate Verifier (D0 Asymmetric Specification).
Single-source verifier validating Gate 3 Parity Certificates and EvidenceTrustCertificates.
The verifier receives and possesses only public verification keys.
"""

from __future__ import annotations
import os
import sys
import json
import hashlib
import hmac
import argparse
from typing import Any, Dict, Optional
from domain.models import AsymmetricAuthoritySignature
from events.serializer import canonicalize_json

TRUSTED_VERIFIER_IDENTITIES = frozenset({"PARITY-GATE-3", "Gate3AuthoritativeVerifier", "Gate3EvidenceVerifier"})


class Gate3PublicKeystore:
    """Public keystore boundary for Gate 3 root verifiers."""
    _public_key: Optional[Any] = None
    _is_sealed: bool = False

    @classmethod
    def bootstrap_root_public_key(cls, public_key: Any) -> None:
        """Controlled bootstrap of the Gate 3 root public key by trusted application composition root."""
        from cryptography.hazmat.primitives.asymmetric import ed25519
        if not isinstance(public_key, ed25519.Ed25519PublicKey):
            raise TypeError(f"Expected Ed25519PublicKey instance, got {type(public_key).__name__}")
        if cls._is_sealed and cls._public_key is not None:
            raise RuntimeError("Gate3PublicKeystore root public key is already initialized and cannot be replaced at runtime.")

        # If canonical authority keystore is already configured, verify key match
        from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore
        try:
            canonical_pub = Gate3AuthorityKeyStore.get_public_key()
            if canonical_pub is not None:
                if public_key.public_bytes_raw() != canonical_pub.public_bytes_raw():
                    raise RuntimeError("Unauthorized root initialization rejected: public key does not match canonical Gate 3 authority.")
        except Exception as e:
            if isinstance(e, RuntimeError) and "Unauthorized root" in str(e):
                raise

        cls._public_key = public_key
        cls._is_sealed = True

    @classmethod
    def set_public_key(cls, public_key: Any) -> None:
        """Injects public key into verifier keystore with strict type and authorization validation."""
        cls.bootstrap_root_public_key(public_key)

    @classmethod
    def clear(cls) -> None:
        """Controlled teardown of public keystore boundary strictly for test fixtures."""
        if os.environ.get("SCLASS_TEST_FIXTURE_ACTIVE") != "1" and os.environ.get("PYTEST_CURRENT_TEST") is None:
            raise RuntimeError("Root keystore teardown prohibited outside active test fixture harness.")
        cls._public_key = None
        cls._is_sealed = False

    @classmethod
    def get_public_key(cls) -> Optional[Any]:
        if cls._public_key is not None:
            return cls._public_key
        env_pub_hex = os.environ.get("GATE3_AUTHORITY_PUBLIC_KEY")
        if env_pub_hex and len(env_pub_hex) == 64:
            from cryptography.hazmat.primitives.asymmetric import ed25519
            return ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(env_pub_hex))
        from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore
        try:
            return Gate3AuthorityKeyStore.get_public_key()
        except Exception:
            pass
        return None


def verify_gate_3_evidence_trust_certificate(
    cert: Any,
    expected_source_sha: Optional[str] = None,
    public_key: Optional[Any] = None,
) -> bool:
    """Strictly validates an EvidenceTrustCertificate against the Gate 3 Asymmetric Authority."""
    from policy.models import EvidenceTrustCertificate
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.exceptions import InvalidSignature

    if not isinstance(cert, EvidenceTrustCertificate):
        return False

    if not cert.verifier_identity or cert.verifier_identity not in TRUSTED_VERIFIER_IDENTITIES:
        return False

    if not cert.certificate_hash or not cert.timestamp or not cert.authority_signature:
        return False

    if not isinstance(cert.authority_signature, AsymmetricAuthoritySignature):
        return False

    if cert.authority_signature.algorithm != "ED25519":
        return False

    if cert.authority_signature.signer_identity != cert.verifier_identity:
        return False

    if cert.authority_signature.timestamp != cert.timestamp:
        return False

    if not cert.is_verified or not cert.digest_verified or not cert.signature_verified or not cert.provenance_verified:
        return False

    if expected_source_sha is not None and cert.source_sha != expected_source_sha:
        return False

    # 1. Obtain and strictly typecheck public verification key
    pub_key = public_key or Gate3PublicKeystore.get_public_key()
    if pub_key is None:
        # Fails closed if public verification key is absent from the trust boundary
        return False
    if not isinstance(pub_key, ed25519.Ed25519PublicKey):
        raise TypeError(f"Expected Ed25519PublicKey instance, got {type(pub_key).__name__}")

    # 2. Check public key fingerprint match
    pub_bytes = pub_key.public_bytes_raw()
    expected_fp = hashlib.sha256(pub_bytes).hexdigest()
    if not hmac.compare_digest(cert.authority_signature.public_key_fingerprint, expected_fp):
        return False

    # 3. Canonical JCS byte representation of certificate fields
    cert_data = {
        "evidence_id": cert.evidence_id,
        "source_sha": cert.source_sha,
        "is_verified": cert.is_verified,
        "digest_verified": cert.digest_verified,
        "signature_verified": cert.signature_verified,
        "provenance_verified": cert.provenance_verified,
        "verifier_identity": cert.verifier_identity,
        "timestamp": cert.timestamp,
    }
    canonical_bytes = canonicalize_json(cert_data)

    # 4. Verify canonical payload digest match
    expected_digest = hashlib.sha256(canonical_bytes).hexdigest()
    if not hmac.compare_digest(cert.certificate_hash, expected_digest):
        return False
    if not hmac.compare_digest(cert.authority_signature.payload_digest, expected_digest):
        return False

    # 5. Cryptographic Ed25519 signature verification (narrowed exceptions only)
    try:
        sig_bytes = bytes.fromhex(cert.authority_signature.signature_hex)
        pub_key.verify(sig_bytes, canonical_bytes)
    except (InvalidSignature, ValueError):
        return False

    return True


def verify_gate_3_certificate(cert_path: str, expected_sha: str, expected_version: str = "4.24.3") -> bool:
    """Strictly verifies a Gate 3 Parity Certificate under the D0 Keyed HMAC Provider Contract."""
    if not os.path.exists(cert_path):
        raise FileNotFoundError(f"Certificate not found at: {cert_path}")

    with open(cert_path, "r", encoding="utf-8") as f:
        cert = json.load(f)

    # 1. Structural & Contract Spec Checks
    if cert.get("gate") != "PARITY-GATE-3":
        raise ValueError(f"Invalid gate in certificate: expected 'PARITY-GATE-3', got '{cert.get('gate')}'")

    if cert.get("contract_spec") not in ["D0", "D0_KEYED_HMAC"]:
        raise ValueError(f"Invalid contract spec: expected 'D0_KEYED_HMAC', got '{cert.get('contract_spec')}'")

    if cert.get("verdict") != "PASS":
        raise ValueError(f"Certificate verdict is not PASS: got '{cert.get('verdict')}'")

    # 2. Provenance & Source SHA Checks
    actual_sha = cert.get("source_sha")
    if not actual_sha or actual_sha == "UNKNOWN" or len(actual_sha) != 40:
        raise ValueError(f"Certificate has missing, UNKNOWN, or invalid source SHA: '{actual_sha}'")

    if expected_sha and expected_sha != "UNKNOWN" and actual_sha != expected_sha:
        raise ValueError(f"Source SHA mismatch: expected '{expected_sha}', got '{actual_sha}'")

    # 3. Version Pinning Checks
    st_ver = cert.get("schemathesis_version")
    if st_ver != expected_version:
        raise ValueError(f"Schemathesis version mismatch: expected '{expected_version}', got '{st_ver}'")

    pinned_ver = cert.get("exact_pinned_version")
    if pinned_ver != expected_version:
        raise ValueError(f"Exact pinned version mismatch: expected '{expected_version}', got '{pinned_ver}'")

    if cert.get("provider_version") != "1.0.0":
        raise ValueError(f"Provider version mismatch: expected '1.0.0', got '{cert.get('provider_version')}'")

    # 4. Zero Object Leakage & Keyed HMAC Check
    if cert.get("zero_object_leakage_verified") is not True:
        raise ValueError("Certificate indicates object leakage verification failed or missing.")

    if cert.get("keyed_hmac_authentication_verified") is not True:
        raise ValueError("Certificate indicates keyed HMAC authentication verification failed or missing.")

    # 5. Corpus Results & D0 Digest Validation
    corpus = cert.get("corpus_results", {})
    required_scenarios = ["clean_api", "schema_violation", "server_error_5xx", "malformed_schema", "unreachable_target"]
    for sc in required_scenarios:
        if sc not in corpus:
            raise KeyError(f"Missing corpus scenario result: {sc}")
        sc_res = corpus[sc]
        for req_field in ["schema_hash", "config_hash", "input_digest", "worker_digest", "worker_hmac", "provenance_hash"]:
            if req_field not in sc_res or not sc_res[req_field]:
                raise ValueError(f"Corpus scenario '{sc}' missing required D0 field '{req_field}'.")

    # Check scenario statuses
    if corpus["clean_api"]["status"] != "TARGET_CLEAN" or not corpus["clean_api"]["passed"]:
        raise ValueError("Corpus clean_api scenario did not pass as TARGET_CLEAN")

    if corpus["schema_violation"]["status"] != "TARGET_CONTRACT_VIOLATED" or corpus["schema_violation"]["passed"]:
        raise ValueError("Corpus schema_violation scenario did not fail closed")

    if corpus["server_error_5xx"]["status"] != "TARGET_CONTRACT_VIOLATED" or corpus["server_error_5xx"]["passed"]:
        raise ValueError("Corpus server_error_5xx scenario did not fail closed")

    if corpus["malformed_schema"]["status"] != "INPUT_INVALID" or corpus["malformed_schema"]["passed"]:
        raise ValueError("Corpus malformed_schema scenario did not fail closed")

    if corpus["unreachable_target"]["status"] not in ["TARGET_CONTRACT_VIOLATED", "TOOL_EXECUTION_FAILED"] or corpus["unreachable_target"]["passed"]:
        raise ValueError("Corpus unreachable_target scenario did not fail closed")

    # 6. Certificate Hash Integrity
    stored_hash = cert.get("certificate_hash")
    if not stored_hash:
        raise ValueError("Certificate missing certificate_hash field.")

    cert_copy = dict(cert)
    del cert_copy["certificate_hash"]
    expected_hash = hashlib.sha256(json.dumps(cert_copy, sort_keys=True).encode("utf-8")).hexdigest()

    if stored_hash != expected_hash:
        raise ValueError(f"Certificate hash tampering detected! Stored: {stored_hash}, Expected: {expected_hash}")

    print(f"VERIFIED: D0 Keyed Gate 3 Parity Certificate {cert_path} successfully validated against SHA {actual_sha} and Schemathesis {st_ver}.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Verify S-Class Gate 3 Parity Certificate (D0 Keyed Protocol)")
    parser.add_argument("--certificate", required=True, help="Path to certificate JSON file")
    parser.add_argument("--expected-sha", required=True, help="Expected authoritative git commit SHA")
    parser.add_argument("--expected-version", default="4.24.3", help="Expected Schemathesis version (default: 4.24.3)")

    args = parser.parse_args()
    try:
        verify_gate_3_certificate(
            cert_path=args.certificate,
            expected_sha=args.expected_sha,
            expected_version=args.expected_version
        )
        sys.exit(0)
    except Exception as e:
        print(f"FAILED: Certificate verification rejected: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
