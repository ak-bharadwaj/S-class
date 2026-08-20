"""
S-Class EOS V11.2 - Gate 3 Certificate Authority & Provider Keystore (D0 Asymmetric Specification).
Protected authority / keystore boundary for issuing Ed25519-signed EvidenceTrustCertificates,
cryptographically verifying provider HMAC signatures, enforcing non-overwritable provider keys with
explicit rotation semantics, and enforcing D0 cross-process atomic single-use anti-replay rules.
"""

from __future__ import annotations
import os
import hmac
import uuid
import hashlib
import threading
from datetime import datetime, timezone
from typing import Any, Optional, Dict, Set
from domain.models import AsymmetricAuthoritySignature, HmacSessionSignature, Evidence, EvidenceScope, EvidenceObservation, Provenance
from domain.types import EvidencePolarity, EvidenceValidity, RawStatus
from events.serializer import canonicalize_json

GATE3_AUTHORITY_IDENTITY = "Gate3AuthoritativeVerifier"


class Gate3AuthorityKeyStore:
    """Protected keystore boundary for Gate 3 Certificate Authority."""
    _private_key: Optional[Any] = None

    @classmethod
    def set_private_key(cls, private_key: Any) -> None:
        """Injects private key into protected keystore boundary with strict type validation.
        Controlled initialization boundary: prevents arbitrary runtime replacement of the authority key.
        """
        from cryptography.hazmat.primitives.asymmetric import ed25519
        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            raise TypeError(f"Expected Ed25519PrivateKey instance, got {type(private_key).__name__}")
        if cls._private_key is not None:
            raise RuntimeError("Gate3AuthorityKeyStore private key is already initialized and cannot be replaced at runtime.")
        cls._private_key = private_key

    @classmethod
    def clear(cls) -> None:
        """Controlled teardown of keystore boundary for test fixtures."""
        cls._private_key = None

    @classmethod
    def get_private_key(cls) -> Any:
        """Retrieves private key from keystore or environment trust boundary."""
        if cls._private_key is not None:
            return cls._private_key
        env_key_hex = os.environ.get("GATE3_AUTHORITY_PRIVATE_KEY")
        if env_key_hex and len(env_key_hex) == 64:
            from cryptography.hazmat.primitives.asymmetric import ed25519
            return ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(env_key_hex))
        raise RuntimeError("Gate 3 Authority private key is not configured in protected keystore boundary.")

    @classmethod
    def get_public_key(cls) -> Any:
        """Derives public key from current authority private key."""
        return cls.get_private_key().public_key()

    @classmethod
    def get_public_key_fingerprint(cls) -> str:
        """Calculates SHA-256 fingerprint (64 hex chars) of public key raw bytes."""
        pub_bytes = cls.get_public_key().public_bytes_raw()
        return hashlib.sha256(pub_bytes).hexdigest()


class Gate3ProviderKeyStore:
    """Certified provider keystore boundary managing provider signing and verification keys.
    Non-overwritable registration with explicit rotation semantics.
    Environment provider keys must be explicitly bootstrapped or registered.
    """
    _provider_keys: Dict[str, bytes] = {}
    _retired_keys: Set[str] = set()

    @classmethod
    def bootstrap_from_environment(cls, allowed_key_ids: Optional[Dict[str, str]] = None) -> None:
        """Explicit bootstrap configuration binding authorized environment provider identities.
        Does not silently accept arbitrary environment variables at runtime.
        """
        if allowed_key_ids is not None:
            for key_id, env_var_name in allowed_key_ids.items():
                secret = os.environ.get(env_var_name)
                if secret and len(secret.encode("utf-8")) >= 16:
                    cls.register_provider_key(key_id, secret.encode("utf-8"))
        else:
            default_env = os.environ.get("GATE3_PROVIDER_KEY")
            if default_env and len(default_env.encode("utf-8")) >= 16:
                if "KEY-001" not in cls._provider_keys:
                    cls.register_provider_key("KEY-001", default_env.encode("utf-8"))

    @classmethod
    def register_provider_key(cls, key_id: str, key_bytes: bytes) -> None:
        """Registers a new provider key. Overwriting an existing key fails closed."""
        if not key_id or not isinstance(key_id, str):
            raise TypeError("key_id must be a non-empty string.")
        if not isinstance(key_bytes, bytes) or len(key_bytes) < 16:
            raise ValueError("key_bytes must be bytes of at least 16 bytes.")
        if key_id in cls._provider_keys or key_id in cls._retired_keys:
            raise RuntimeError(f"Provider key '{key_id}' is already registered and cannot be overwritten. Use rotate_provider_key() for key rotation.")
        cls._provider_keys[key_id] = key_bytes

    @classmethod
    def rotate_provider_key(cls, old_key_id: str, new_key_id: str, new_key_bytes: bytes) -> None:
        """Rotates provider key: retires the old key ID and registers the new key ID."""
        if not old_key_id or not isinstance(old_key_id, str):
            raise TypeError("old_key_id must be a non-empty string.")
        if old_key_id not in cls._provider_keys:
            raise KeyError(f"Cannot rotate non-existent provider key '{old_key_id}'.")
        if not new_key_id or not isinstance(new_key_id, str):
            raise TypeError("new_key_id must be a non-empty string.")
        if new_key_id in cls._provider_keys or new_key_id in cls._retired_keys:
            raise RuntimeError(f"New provider key '{new_key_id}' is already registered.")
        if not isinstance(new_key_bytes, bytes) or len(new_key_bytes) < 16:
            raise ValueError("new_key_bytes must be bytes of at least 16 bytes.")

        cls._provider_keys.pop(old_key_id)
        cls._retired_keys.add(old_key_id)
        cls._provider_keys[new_key_id] = new_key_bytes

    @classmethod
    def is_retired(cls, key_id: str) -> bool:
        return key_id in cls._retired_keys

    @classmethod
    def clear(cls) -> None:
        """Controlled teardown of provider keystore for test fixtures."""
        cls._provider_keys.clear()
        cls._retired_keys.clear()

    @classmethod
    def get_provider_key(cls, key_id: str) -> bytes:
        """Retrieves provider key exclusively from explicitly registered keys in the certified keystore."""
        if not key_id or not isinstance(key_id, str):
            raise TypeError("key_id must be a non-empty string.")
        if key_id in cls._retired_keys:
            raise RuntimeError(f"Provider key '{key_id}' has been retired and cannot be used.")
        if key_id in cls._provider_keys:
            return cls._provider_keys[key_id]

        raise KeyError(f"Provider key '{key_id}' is not registered in certified keystore.")


class Gate3NonceTracker:
    """Enforces D0 cross-process atomic single-use anti-replay rules for evidence nonces
    backed by kernel advisory file locking.
    """
    _default_store_path: str = os.path.join(os.path.dirname(__file__), ".gate3_nonces.log")
    _store_path: str = _default_store_path
    _process_local_cache: Set[str] = set()
    _thread_lock = threading.Lock()

    @classmethod
    def set_store_path(cls, path: str) -> None:
        with cls._thread_lock:
            cls._store_path = path
            cls._process_local_cache.clear()

    @classmethod
    def get_store_path(cls) -> str:
        return cls._store_path

    @classmethod
    def clear(cls) -> None:
        """Controlled teardown for test fixtures across processes."""
        from file_lock import FileLock
        with cls._thread_lock:
            cls._process_local_cache.clear()
            lock_path = cls._store_path + ".lock"
            try:
                parent_dir = os.path.dirname(cls._store_path)
                if parent_dir and not os.path.exists(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)
                with FileLock(lock_path, timeout=5.0):
                    if os.path.exists(cls._store_path):
                        try:
                            os.remove(cls._store_path)
                        except OSError:
                            with open(cls._store_path, "w", encoding="utf-8") as f:
                                pass
            except Exception:
                if os.path.exists(cls._store_path):
                    try:
                        with open(cls._store_path, "w", encoding="utf-8") as f:
                            pass
                    except OSError:
                        pass

    @classmethod
    def consume_nonce(cls, nonce: str) -> bool:
        """Atomically reserves a single-use nonce across processes.
        Returns True if reservation succeeded.
        Returns False if nonce was already consumed (replay detected).
        """
        if not nonce or not isinstance(nonce, str):
            return False

        from file_lock import FileLock
        lock_path = cls._store_path + ".lock"

        with cls._thread_lock:
            if nonce in cls._process_local_cache:
                return False

            parent_dir = os.path.dirname(cls._store_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            with FileLock(lock_path, timeout=10.0):
                # Read committed nonces from persistent store
                consumed = set()
                if os.path.exists(cls._store_path):
                    with open(cls._store_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line_str = line.strip()
                            if line_str:
                                consumed.add(line_str)

                if nonce in consumed:
                    cls._process_local_cache.add(nonce)
                    return False

                # Atomically append nonce and fsync
                with open(cls._store_path, "a", encoding="utf-8") as f:
                    f.write(nonce + "\n")
                    f.flush()
                    os.fsync(f.fileno())

                consumed.add(nonce)
                cls._process_local_cache.add(nonce)
                return True

    @classmethod
    def is_consumed(cls, nonce: str) -> bool:
        if not nonce:
            return False
        from file_lock import FileLock
        with cls._thread_lock:
            if nonce in cls._process_local_cache:
                return True
            if not os.path.exists(cls._store_path):
                return False
            lock_path = cls._store_path + ".lock"
            try:
                with FileLock(lock_path, timeout=5.0):
                    if os.path.exists(cls._store_path):
                        with open(cls._store_path, "r", encoding="utf-8") as f:
                            for line in f:
                                if line.strip() == nonce:
                                    cls._process_local_cache.add(nonce)
                                    return True
            except Exception:
                pass
            return False


def compute_gate3_evidence_digest(evidence: Any) -> str:
    """Computes the authoritative RFC 8785 / JCS canonical digest for an Evidence item."""
    counterexample = getattr(evidence.observation, "counterexample", None)
    if counterexample is not None and not isinstance(counterexample, dict):
        counterexample = dict(counterexample)

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
            "counterexample": counterexample,
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


def sign_provider_evidence(
    evidence_id: str,
    claim_id: str,
    provider_id: str,
    capability: str,
    execution_id: str,
    source_sha: str,
    scope: Any,
    observation: Any,
    provenance: Any,
    key_id: str = "KEY-001",
    nonce: Optional[str] = None,
) -> HmacSessionSignature:
    """Generates an authentic provider HmacSessionSignature for an evidence item.
    Signing key is acquired exclusively from the certified Gate3ProviderKeyStore boundary.
    """
    if nonce is None:
        nonce = f"NONCE-{evidence_id}-{uuid.uuid4().hex[:12].upper()}"

    dummy_sig = HmacSessionSignature(
        algorithm="HMAC-SHA256",
        key_id=key_id,
        nonce=nonce,
        raw_stdout_digest="0" * 64,
        signature_hex="0" * 64,
        timestamp=provenance.timestamp,
    )
    temp_ev = Evidence(
        evidence_id=evidence_id,
        claim_id=claim_id,
        provider_id=provider_id,
        capability=capability,
        execution_id=execution_id,
        source_sha=source_sha,
        scope=scope,
        observation=observation,
        polarity=EvidencePolarity.SUPPORTS,
        validity=EvidenceValidity.VALID,
        independence_group="INDEP-1",
        provenance=provenance,
        signature=dummy_sig,
    )
    raw_digest = compute_gate3_evidence_digest(temp_ev)

    sig_payload = {
        "raw_stdout_digest": raw_digest,
        "key_id": key_id,
        "nonce": nonce,
        "timestamp": provenance.timestamp,
    }
    canonical_sig_bytes = canonicalize_json(sig_payload)
    key_bytes = Gate3ProviderKeyStore.get_provider_key(key_id)
    sig_hex = hmac.new(key_bytes, canonical_sig_bytes, hashlib.sha256).hexdigest()

    return HmacSessionSignature(
        algorithm="HMAC-SHA256",
        key_id=key_id,
        nonce=nonce,
        raw_stdout_digest=raw_digest,
        signature_hex=sig_hex,
        timestamp=provenance.timestamp,
    )


def verify_provider_evidence_signature(evidence: Any) -> bool:
    """Cryptographically verifies provider evidence signature (HmacSessionSignature).
    
    Checks:
    1. Valid HmacSessionSignature dataclass instance with algorithm HMAC-SHA256.
    2. Actual evidence payload digest matches evidence.signature.raw_stdout_digest.
    3. Cryptographic HMAC-SHA256 signature verification over canonical signature payload
       using provider key exclusively from Gate3ProviderKeyStore.
    """
    if not hasattr(evidence, "signature") or not evidence.signature:
        return False
    sig = evidence.signature
    if not isinstance(sig, HmacSessionSignature):
        return False
    if sig.algorithm != "HMAC-SHA256":
        return False
    if not sig.signature_hex or len(sig.signature_hex) != 64:
        return False

    # 1. Digest Verification: evidence payload digest matches signature.raw_stdout_digest
    computed_digest = compute_gate3_evidence_digest(evidence)
    if not hmac.compare_digest(sig.raw_stdout_digest, computed_digest):
        return False

    # 2. Signature Payload Reconstruction (JCS Canonical Bytes)
    sig_payload = {
        "raw_stdout_digest": sig.raw_stdout_digest,
        "key_id": sig.key_id,
        "nonce": sig.nonce,
        "timestamp": sig.timestamp,
    }
    try:
        canonical_sig_bytes = canonicalize_json(sig_payload)
    except Exception:
        return False

    # 3. Key Retrieval & Cryptographic HMAC Comparison (exclusively from Gate3ProviderKeyStore)
    try:
        key_bytes = Gate3ProviderKeyStore.get_provider_key(sig.key_id)
    except Exception:
        return False

    expected_sig_hex = hmac.new(key_bytes, canonical_sig_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig.signature_hex, expected_sig_hex)


def issue_gate_3_evidence_certificate(
    evidence: Any,
    expected_source_sha: str,
    verifier_identity: str = GATE3_AUTHORITY_IDENTITY,
) -> Any:
    """Gate 3 Authority: Produces an authentic, Ed25519-signed EvidenceTrustCertificate.
    
    Private key is acquired exclusively from the protected Gate3AuthorityKeyStore boundary.
    Provider keys are acquired exclusively from Gate3ProviderKeyStore.
    Nonces are reserved atomically across processes AFTER provider signature + digest + provenance validation.
    Timestamp is bound to authoritative execution time.
    """
    from policy.models import EvidenceTrustCertificate

    private_key = Gate3AuthorityKeyStore.get_private_key()
    public_key = private_key.public_key()
    pub_bytes = public_key.public_bytes_raw()
    pub_fingerprint = hashlib.sha256(pub_bytes).hexdigest()

    # Authoritative execution timestamp from evidence provenance or current UTC
    timestamp_iso = getattr(getattr(evidence, "provenance", None), "timestamp", None) or datetime.now(timezone.utc).isoformat()

    # 1. Source SHA verification
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

    # 2. Cryptographic Digest, Provider Signature, and Provenance Verification (BEFORE nonce reservation)
    computed_digest = compute_gate3_evidence_digest(evidence)
    claimed_digest = getattr(evidence.signature, "raw_stdout_digest", None)
    digest_verified = bool(claimed_digest and hmac.compare_digest(claimed_digest, computed_digest))

    signature_verified = verify_provider_evidence_signature(evidence)

    prov = evidence.provenance
    provenance_verified = bool(
        prov
        and prov.engine_name
        and not any(f in prov.engine_name.lower() for f in ["synthetic", "simulation", "untrusted"])
        and prov.environment_hash
        and len(prov.environment_hash) == 64
        and prov.timestamp
    )

    # If verification failed (invalid signature, bad digest, corrupt provenance), DO NOT reserve nonce; fail closed
    if not (digest_verified and signature_verified and provenance_verified):
        rejection_reason = "Evidence verification failed."
        if not digest_verified:
            rejection_reason = "Evidence digest mismatch."
        elif not signature_verified:
            rejection_reason = "Invalid provider signature."
        elif not provenance_verified:
            rejection_reason = "Untrusted or invalid provenance."

        cert_data = {
            "evidence_id": evidence.evidence_id,
            "source_sha": evidence.source_sha,
            "is_verified": False,
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
            is_verified=False,
            digest_verified=digest_verified,
            signature_verified=signature_verified,
            provenance_verified=provenance_verified,
            verifier_identity=verifier_identity,
            timestamp=timestamp_iso,
            certificate_hash=payload_digest,
            authority_signature=authority_sig,
            rejection_reason=rejection_reason,
        )

    # 3. D0 Single-Use Nonce Anti-Replay Reservation (AFTER successful validation, immediately before issuance)
    evidence_nonce = getattr(getattr(evidence, "signature", None), "nonce", None)
    if not evidence_nonce or not Gate3NonceTracker.consume_nonce(evidence_nonce):
        cert_data = {
            "evidence_id": evidence.evidence_id,
            "source_sha": evidence.source_sha,
            "is_verified": False,
            "digest_verified": digest_verified,
            "signature_verified": False,
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
            is_verified=False,
            digest_verified=digest_verified,
            signature_verified=False,
            provenance_verified=provenance_verified,
            verifier_identity=verifier_identity,
            timestamp=timestamp_iso,
            certificate_hash=payload_digest,
            authority_signature=authority_sig,
            rejection_reason="Replay detected: evidence nonce has already been consumed under D0 single-use rule.",
        )

    # 4. Valid Certificate Issuance
    cert_data = {
        "evidence_id": evidence.evidence_id,
        "source_sha": evidence.source_sha,
        "is_verified": True,
        "digest_verified": True,
        "signature_verified": True,
        "provenance_verified": True,
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
        is_verified=True,
        digest_verified=True,
        signature_verified=True,
        provenance_verified=True,
        verifier_identity=verifier_identity,
        timestamp=timestamp_iso,
        certificate_hash=payload_digest,
        authority_signature=authority_sig,
    )
