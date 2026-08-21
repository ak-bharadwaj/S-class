"""Pure Deterministic Policy Evaluator for S-Class D3."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import math
import re
import os
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

from domain.models import (
    Policy,
    PolicyRule,
    PolicyExpression,
    Obligation,
    Claim,
    Evidence,
    EvidenceScope,
    EvidenceObservation,
    Provenance,
    HmacSessionSignature,
)
from domain.types import (
    PolicyScope,
    RuleType,
    CombinatorType,
    ClaimTier,
    ClaimStatus,
    EvidencePolarity,
    EvidenceValidity,
    RawStatus,
)
from policy.models import (
    PolicyDecision,
    PolicyDecisionType,
    PolicyEvaluationContext,
    PolicyException,
    RuleEvaluationResult,
    EvidenceTrustCertificate,
)
from policy.exceptions import (
    PolicyEngineError,
    PolicyValidationError,
    InvalidExceptionError,
    ExpiredExceptionError,
)


class CoverageTrustPredicate:
    """Narrow trust consumer interface for S-Class D3 Policy Engine.
    
    Consumes external verifier-produced EvidenceTrustCertificate (Gate-3):
    1. Exact expected revision binding (expected_source_sha is mandatory for policy decisions)
    2. Valid schema and lifecycle state (VALID + SUPPORTS + PASS)
    3. Provider capability matches coverage authorization
    4. Provider identity non-synthetic
    5. Provenance engine non-synthetic
    6. Verified issuer-authenticated cryptographic trust certificate via Gate-3 verifier:
       verify_gate_3_evidence_trust_certificate(cert, expected_source_sha=context.expected_source_sha)
    """

    TRUSTED_COVERAGE_CAPABILITIES: Set[str] = {
        "CODE_COVERAGE",
        "COVERAGE_ANALYSIS",
        "STATIC_AST_ANALYSIS",
        "PROPERTY_TESTING",
        "API_CONTRACT_FUZZING",
        "TEST_EXECUTION",
    }

    FORBIDDEN_ENGINES: Set[str] = {
        "synthetic",
        "simulation",
        "untrusted",
        "fake",
        "mock",
        "dummy",
    }

    @classmethod
    def is_trusted(
        cls,
        evidence: Evidence,
        context: PolicyEvaluationContext,
    ) -> bool:
        # 1. Exact revision binding is MANDATORY for policy decisions (missing revision fails closed)
        if not context.expected_source_sha:
            return False

        # 2. Schema and lifecycle verification
        if not isinstance(evidence, Evidence):
            return False
        if evidence.validity != EvidenceValidity.VALID or evidence.polarity != EvidencePolarity.SUPPORTS:
            return False
        if not isinstance(evidence.observation, EvidenceObservation) or evidence.observation.raw_status != RawStatus.PASS:
            return False

        # 3. Capability matches coverage authorization
        if evidence.capability not in cls.TRUSTED_COVERAGE_CAPABILITIES:
            return False

        # 4. Provider identity non-synthetic
        prov_id = (evidence.provider_id or "").lower()
        if not prov_id or any(f in prov_id for f in cls.FORBIDDEN_ENGINES):
            return False

        # 5. Provenance non-synthetic
        prov = evidence.provenance
        if not isinstance(prov, Provenance):
            return False
        engine_name = (prov.engine_name or "").lower()
        if not engine_name or any(f in engine_name for f in cls.FORBIDDEN_ENGINES):
            return False

        # 6. Consume issuer-authenticated cryptographic trust certificate via Gate-3 verifier interface
        cert = context.trust_certificates.get(evidence.evidence_id)
        if cert is None:
            return False

        from benchmark.parity.verify_gate_3_certificate import verify_gate_3_evidence_trust_certificate

        if not verify_gate_3_evidence_trust_certificate(cert, expected_source_sha=context.expected_source_sha):
            return False

        if cert.evidence_id != evidence.evidence_id:
            return False

        return True


from types import MappingProxyType
from typing import Protocol, runtime_checkable, Mapping


@dataclass(frozen=True)
class ActorKeyRecord:
    """Enrolled actor authority record in D3 keystore."""
    actor_id: str
    actor_role: str
    public_key_fingerprint: str
    public_key: Any
    is_active: bool = True


@runtime_checkable
class PolicyActorAuthorityResolver(Protocol):
    """Read-only authority resolver protocol consumed by D3 Policy Evaluator."""

    def lookup_actor(self, fingerprint: str) -> Optional[ActorKeyRecord]:
        """Read-only lookup of enrolled actor record by public key fingerprint."""
        ...

    def is_revoked(self, fingerprint: str) -> bool:
        """Checks whether a public key fingerprint is revoked."""
        ...


class ReadOnlyActorAuthorityResolver:
    """Immutable, read-only actor authority resolver.
    
    Can only be created by the cryptographically verified SignedAuthorityManifestLoader
    or isolated test bootstrap helpers.
    """
    def __init__(
        self,
        actors: Dict[str, ActorKeyRecord],
        revoked_fingerprints: Set[str],
        manifest_id: str = "MANIFEST-ROOT-001",
        manifest_version: int = 1,
    ) -> None:
        self._manifest_id = manifest_id
        self._manifest_version = manifest_version
        self._actors: MappingProxyType[str, ActorKeyRecord] = MappingProxyType(dict(actors))
        self._revoked_fingerprints: frozenset[str] = frozenset(revoked_fingerprints)

    @property
    def manifest_id(self) -> str:
        return self._manifest_id

    @property
    def manifest_version(self) -> int:
        return self._manifest_version

    def lookup_actor(self, fingerprint: str) -> Optional[ActorKeyRecord]:
        """Read-only lookup of enrolled actor record."""
        return self._actors.get(fingerprint)

    def is_revoked(self, fingerprint: str) -> bool:
        """Checks whether an actor key fingerprint is revoked."""
        return fingerprint in self._revoked_fingerprints


def canonicalize_authority_manifest_preimage(manifest_dict: Dict[str, Any]) -> bytes:
    """Produces canonical RFC 8785 (JCS) byte sequence over authority manifest body
    binding manifest_id, manifest_version, issued_at, actors, and revoked_fingerprints.
    """
    from events.serializer import canonicalize_json

    root_sig = manifest_dict.get("root_signature")
    sig_meta = {}
    if isinstance(root_sig, dict):
        sig_meta = {
            "algorithm": str(root_sig.get("algorithm", "ED25519")),
            "signer_identity": str(root_sig.get("signer_identity", "Gate3AuthoritativeVerifier")),
            "public_key_fingerprint": str(root_sig.get("public_key_fingerprint", "")),
        }
    elif hasattr(root_sig, "algorithm"):
        sig_meta = {
            "algorithm": str(root_sig.algorithm),
            "signer_identity": str(root_sig.signer_identity),
            "public_key_fingerprint": str(root_sig.public_key_fingerprint),
        }

    payload = {
        "manifest_id": str(manifest_dict.get("manifest_id", "")),
        "manifest_version": int(manifest_dict.get("manifest_version", 1)),
        "issued_at": str(manifest_dict.get("issued_at", "")),
        "actors": manifest_dict.get("actors", {}),
        "revoked_fingerprints": sorted(list(manifest_dict.get("revoked_fingerprints", []))),
        "signature_metadata": sig_meta,
    }
    return canonicalize_json(payload)


class SignedAuthorityManifestLoader:
    """Cryptographically authenticates signed authority manifests against trusted root authority."""

    @classmethod
    def get_canonical_root_public_key(cls) -> Any:
        """Retrieves the canonical Gate 3 Root Authority Public Key from the established trust boundary."""
        from benchmark.parity.verify_gate_3_certificate import Gate3PublicKeystore
        pub = Gate3PublicKeystore.get_public_key()
        if pub is not None:
            return pub
        raise RuntimeError("Canonical Gate 3 Root Authority Public Key is not configured in protected keystore boundary.")

    @classmethod
    def clear_for_testing(cls) -> None:
        """Controlled teardown of manifest loader state strictly for test fixtures."""
        if os.environ.get("SCLASS_TEST_FIXTURE_ACTIVE") != "1" and os.environ.get("PYTEST_CURRENT_TEST") is None:
            raise RuntimeError("Monotonic authority state cannot be reset outside active test fixture harness.")
        from events.store import D2AuthorityManifestStore, D2InstallationProvisioning
        store = D2AuthorityManifestStore()
        store.clear()
        D2InstallationProvisioning.clear_for_testing()
        with open(store.file_path, "wb") as f:
            pass

    @classmethod
    def sign_manifest(
        cls,
        manifest_id: str,
        manifest_version: int,
        issued_at: str,
        actors: Dict[str, Dict[str, Any]],
        revoked_fingerprints: List[str],
        root_private_key: Any,
        signer_identity: str = "Gate3AuthoritativeVerifier",
    ) -> Dict[str, Any]:
        """Cryptographically signs an authority manifest with Ed25519 root private key."""
        timestamp = issued_at
        fp = hashlib.sha256(root_private_key.public_key().public_bytes_raw()).hexdigest()

        dummy_sig = {
            "algorithm": "ED25519",
            "signer_identity": signer_identity,
            "public_key_fingerprint": fp,
            "payload_digest": "0" * 64,
            "signature_hex": "0" * 128,
            "timestamp": timestamp,
        }
        manifest_dict = {
            "manifest_id": manifest_id,
            "manifest_version": manifest_version,
            "issued_at": issued_at,
            "actors": actors,
            "revoked_fingerprints": sorted(revoked_fingerprints),
            "root_signature": dummy_sig,
        }
        canonical_bytes = canonicalize_authority_manifest_preimage(manifest_dict)
        payload_digest = hashlib.sha256(canonical_bytes).hexdigest()
        sig_bytes = root_private_key.sign(canonical_bytes)

        real_sig = {
            "algorithm": "ED25519",
            "signer_identity": signer_identity,
            "public_key_fingerprint": fp,
            "payload_digest": payload_digest,
            "signature_hex": sig_bytes.hex(),
            "timestamp": timestamp,
        }
        manifest_dict["root_signature"] = real_sig
        return manifest_dict

    @classmethod
    def _load_from_dict_internal(
        cls,
        data: Dict[str, Any],
        trusted_root_public_key: Any,
        min_version: Optional[int] = None,
    ) -> ReadOnlyActorAuthorityResolver:
        """Internal manifest verification implementation."""
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.exceptions import InvalidSignature
        from events.store import D2AuthorityManifestStore
        from policy.exceptions import (
            InvalidManifestSignatureError,
            CorruptManifestError,
            ManifestRollbackError,
        )

        if not isinstance(data, dict):
            raise CorruptManifestError("Authority manifest data must be a dictionary.")

        manifest_id = data.get("manifest_id")
        if not manifest_id or not isinstance(manifest_id, str):
            raise CorruptManifestError("Authority manifest missing valid 'manifest_id'.")

        try:
            manifest_version = int(data.get("manifest_version", 1))
        except (ValueError, TypeError):
            raise CorruptManifestError("Authority manifest version must be an integer.")

        if manifest_version <= 0:
            raise ManifestRollbackError("Manifest version must be a positive non-zero integer.")

        if manifest_version > 1_000_000:
            raise ManifestRollbackError(f"Manifest version {manifest_version} exceeds maximum allowable epoch window.")

        # Minimum required version check
        if min_version is not None and manifest_version < min_version:
            raise ManifestRollbackError(
                f"Manifest version {manifest_version} is older than minimum required version {min_version} (rollback rejected)."
            )

        root_sig = data.get("root_signature")
        if not root_sig or not isinstance(root_sig, dict):
            raise InvalidManifestSignatureError("Authority manifest missing 'root_signature' block.")

        sig_hex = root_sig.get("signature_hex", "")
        if not sig_hex or len(sig_hex) != 128:
            raise InvalidManifestSignatureError("Authority manifest root signature hex is malformed or invalid length.")

        signer_identity = root_sig.get("signer_identity", "")
        if signer_identity != "Gate3AuthoritativeVerifier":
            raise InvalidManifestSignatureError(
                f"Manifest root signer identity '{signer_identity}' does not match authoritative root 'Gate3AuthoritativeVerifier'."
            )

        if not isinstance(trusted_root_public_key, ed25519.Ed25519PublicKey):
            raise TypeError(f"Expected Ed25519PublicKey instance for root key, got {type(trusted_root_public_key).__name__}")

        expected_root_fp = hashlib.sha256(trusted_root_public_key.public_bytes_raw()).hexdigest()
        sig_root_fp = root_sig.get("public_key_fingerprint", "")
        if sig_root_fp != expected_root_fp:
            raise InvalidManifestSignatureError(
                f"Manifest root key fingerprint '{sig_root_fp}' does not match trusted root key '{expected_root_fp}'."
            )

        # Verify canonical preimage
        canonical_bytes = canonicalize_authority_manifest_preimage(data)
        expected_digest = hashlib.sha256(canonical_bytes).hexdigest()
        recorded_digest = root_sig.get("payload_digest", "")
        if recorded_digest != expected_digest:
            raise InvalidManifestSignatureError(
                f"Manifest payload digest mismatch: recorded '{recorded_digest}', computed '{expected_digest}'."
            )

        try:
            trusted_root_public_key.verify(bytes.fromhex(sig_hex), canonical_bytes)
        except InvalidSignature:
            raise InvalidManifestSignatureError("Authority manifest Ed25519 root signature verification failed.")

        # Durable monotonic version validation via D2 store (fails closed if missing or corrupt)
        store = D2AuthorityManifestStore()
        highest_ver, active_id, active_digest = store.get_highest_version(allow_uninitialized=False)

        # Verify state agreement between authenticated installation seal and canonical D2 store
        from events.store import D2InstallationProvisioning
        D2InstallationProvisioning.verify_state_agreement()

        if active_id is not None and manifest_id != active_id:
            raise CorruptManifestError(
                f"Manifest identity substitution rejected: expected '{active_id}', got '{manifest_id}'."
            )

        if highest_ver > 0:
            if manifest_version < highest_ver:
                raise ManifestRollbackError(
                    f"Manifest version {manifest_version} is older than highest durable accepted version {highest_ver} (rollback rejected)."
                )

        # Same-version replay / substitution check
        if manifest_version == highest_ver and active_digest is not None:
            if expected_digest != active_digest:
                raise ManifestRollbackError(
                    f"Same-version manifest substitution rejected for version {manifest_version}."
                )

        # Parse and validate actor records
        raw_actors = data.get("actors", {})
        if not isinstance(raw_actors, dict):
            raise CorruptManifestError("Manifest 'actors' field must be a dictionary.")

        actors: Dict[str, ActorKeyRecord] = {}
        for fp, item in raw_actors.items():
            if not isinstance(item, dict):
                raise CorruptManifestError(f"Actor record for '{fp}' must be a dictionary.")
            actor_id = item.get("actor_id")
            actor_role = item.get("actor_role")
            pub_hex = item.get("public_key_hex", "")
            if not actor_id or not isinstance(actor_id, str):
                raise CorruptManifestError("Actor record missing valid 'actor_id'.")
            if not actor_role or not isinstance(actor_role, str):
                raise CorruptManifestError("Actor record missing valid 'actor_role'.")
            if not pub_hex or len(pub_hex) != 64:
                raise CorruptManifestError(f"Actor '{actor_id}' has malformed or missing public_key_hex.")

            try:
                pub_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
            except Exception as e:
                raise CorruptManifestError(f"Actor '{actor_id}' public key bytes are invalid: {e}")

            computed_fp = hashlib.sha256(pub_key.public_bytes_raw()).hexdigest()
            if computed_fp != fp or computed_fp != item.get("public_key_fingerprint"):
                raise CorruptManifestError(
                    f"Actor '{actor_id}' fingerprint mismatch: expected '{fp}', computed '{computed_fp}'."
                )

            actors[fp] = ActorKeyRecord(
                actor_id=actor_id,
                actor_role=actor_role,
                public_key_fingerprint=fp,
                public_key=pub_key,
                is_active=item.get("is_active", True),
            )

        revoked = set(data.get("revoked_fingerprints", []))

        # Commit monotonic version update to durable D2 store
        store.commit_epoch(
            manifest_id=manifest_id,
            manifest_version=manifest_version,
            payload_digest=expected_digest,
            signer_identity=signer_identity,
            root_fingerprint=sig_root_fp,
        )

        return ReadOnlyActorAuthorityResolver(
            actors=actors,
            revoked_fingerprints=revoked,
            manifest_id=manifest_id,
            manifest_version=manifest_version,
        )

    @classmethod
    def load_from_dict(
        cls,
        data: Dict[str, Any],
        min_version: Optional[int] = None,
    ) -> ReadOnlyActorAuthorityResolver:
        """Production manifest loader: strictly validates authority manifest against the canonical Gate 3 root public key.
        Caller-supplied root override is prohibited in the production API surface.
        """
        canonical_root = cls.get_canonical_root_public_key()
        return cls._load_from_dict_internal(data, trusted_root_public_key=canonical_root, min_version=min_version)

    _bootstrap_lock = threading.RLock()

    @classmethod
    def bootstrap_genesis_manifest(
        cls,
        data: Dict[str, Any],
    ) -> ReadOnlyActorAuthorityResolver:
        """Explicit, isolated first-install composition root bootstrap with 3-phase crash consistency:
        Stage 1: FIRST_INSTALL_PREPARED
        Stage 2: D2 GENESIS EVENT DURABLY COMMITTED
        Stage 3: FIRST_INSTALL_SEALED
        """
        with cls._bootstrap_lock:
            from events.store import (
                D2AuthorityManifestStore,
                D2InstallationProvisioning,
                DeploymentProvisionerRegistry,
                DeploymentStatus,
            )
            from policy.exceptions import ManifestRollbackError, InvalidManifestSignatureError, CorruptManifestError
            from cryptography.exceptions import InvalidSignature

            # If D2 store already has events, reject genesis bootstrap
            store = D2AuthorityManifestStore()
            if os.path.exists(store.file_path) and os.path.getsize(store.file_path) > 0:
                raise RuntimeError(f"Genesis bootstrap rejected: canonical D2 authority store already contains history at '{store.file_path}'.")

            # If installation is already sealed, reject genesis bootstrap
            if D2InstallationProvisioning.is_installed():
                raise RuntimeError("Genesis bootstrap rejected: system has already been provisioned/installed. Authority reset prohibited.")

            provisioner = DeploymentProvisionerRegistry.get_provisioner()
            status = provisioner.get_deployment_status()
            if status == DeploymentStatus.AUTHORITY_UNAVAILABLE:
                raise RuntimeError(
                    "Genesis bootstrap rejected: external deployment authority is AUTHORITY_UNAVAILABLE. "
                    "Explicit trusted deployment bootstrap required."
                )
            if status == DeploymentStatus.RECOVERY_REQUIRED:
                raise RuntimeError(
                    "Genesis bootstrap rejected: deployment is in RECOVERY_REQUIRED state after complete local-state loss. "
                    "Explicit root-signed external administrative reprovisioning required."
                )
            if status == DeploymentStatus.PROVISIONED:
                raise RuntimeError("Genesis bootstrap rejected: system has already been provisioned/installed. Authority reset prohibited.")

            # Authorize initial provisioning with external deployment authority if not already recovery-authorized
            if status != DeploymentStatus.RECOVERY_AUTHORIZED:
                provisioner.authorize_initial_provisioning()

            if not isinstance(data, dict):
                raise CorruptManifestError("Authority manifest data must be a dictionary.")

            manifest_id = data.get("manifest_id")
            if not manifest_id or not isinstance(manifest_id, str):
                raise CorruptManifestError("Authority manifest missing valid 'manifest_id'.")

            try:
                manifest_version = int(data.get("manifest_version", 1))
            except (ValueError, TypeError):
                raise CorruptManifestError("Authority manifest version must be an integer.")

            if manifest_version != 1:
                raise ManifestRollbackError("Genesis authority manifest must be version 1.")

            canonical_root = cls.get_canonical_root_public_key()
            root_sig = data.get("root_signature")
            if not root_sig or not isinstance(root_sig, dict):
                raise InvalidManifestSignatureError("Authority manifest missing 'root_signature' block.")

            sig_hex = root_sig.get("signature_hex", "")
            if not sig_hex or len(sig_hex) != 128:
                raise InvalidManifestSignatureError("Authority manifest root signature hex is malformed or invalid length.")

            signer_identity = root_sig.get("signer_identity", "")
            if signer_identity != "Gate3AuthoritativeVerifier":
                raise InvalidManifestSignatureError(
                    f"Manifest root signer identity '{signer_identity}' does not match authoritative root 'Gate3AuthoritativeVerifier'."
                )

            expected_root_fp = hashlib.sha256(canonical_root.public_bytes_raw()).hexdigest()
            sig_root_fp = root_sig.get("public_key_fingerprint", "")
            if sig_root_fp != expected_root_fp:
                raise InvalidManifestSignatureError(
                    f"Manifest root key fingerprint '{sig_root_fp}' does not match trusted root key '{expected_root_fp}'."
                )

            canonical_bytes = canonicalize_authority_manifest_preimage(data)
            expected_digest = hashlib.sha256(canonical_bytes).hexdigest()
            recorded_digest = root_sig.get("payload_digest", "")
            if recorded_digest != expected_digest:
                raise InvalidManifestSignatureError(
                    f"Manifest payload digest mismatch: recorded '{recorded_digest}', computed '{expected_digest}'."
                )

            try:
                canonical_root.verify(bytes.fromhex(sig_hex), canonical_bytes)
            except InvalidSignature:
                raise InvalidManifestSignatureError("Authority manifest Ed25519 root signature verification failed.")

            # Stage 1: FIRST_INSTALL_PREPARED
            inst_id = D2InstallationProvisioning.prepare_first_installation(
                manifest_id=manifest_id,
                manifest_version=manifest_version,
                payload_digest=expected_digest,
                signer_identity=signer_identity,
                root_fingerprint=sig_root_fp,
            )

            # Stage 2: D2 GENESIS EVENT DURABLY COMMITTED
            if not os.path.exists(store.file_path):
                with open(store.file_path, "wb") as f:
                    pass

            store.commit_epoch(
                manifest_id=manifest_id,
                manifest_version=manifest_version,
                payload_digest=expected_digest,
                signer_identity=signer_identity,
                root_fingerprint=sig_root_fp,
            )

            # Stage 3: FIRST_INSTALL_SEALED (and recorded as PROVISIONED in external provisioner)
            D2InstallationProvisioning.seal_first_installation(
                manifest_id=manifest_id,
                manifest_version=manifest_version,
                payload_digest=expected_digest,
                signer_identity=signer_identity,
                root_fingerprint=sig_root_fp,
                installation_id=inst_id,
            )

            return cls.load_from_dict(data)

    @classmethod
    def reprovision_catastrophic_recovery(
        cls,
        data: Dict[str, Any],
        reprovisioning_authorization: Dict[str, Any],
    ) -> ReadOnlyActorAuthorityResolver:
        """Explicit, auditable catastrophic recovery reprovisioning.
        Requires a valid, root-signed DeploymentReprovisioningAuthorization verified by the external authority.
        Fails closed on signature mismatch, deployment mismatch, or replay.
        """
        with cls._bootstrap_lock:
            from events.store import (
                D2AuthorityManifestStore,
                D2InstallationProvisioning,
                DeploymentProvisionerRegistry,
                DeploymentStatus,
            )

            provisioner = DeploymentProvisionerRegistry.get_provisioner()

            # 1. External deployment authority cryptographically verifies and consumes reprovisioning authorization
            auth = provisioner.authorize_reprovisioning(reprovisioning_authorization)

            manifest_id = data.get("manifest_id") if isinstance(data, dict) else None
            if manifest_id != auth.get("target_manifest_id"):
                raise RuntimeError(
                    f"Reprovisioning authorization target '{auth.get('target_manifest_id')}' does not match manifest '{manifest_id}'."
                )

            # 2. Controlled teardown of broken/partial local state
            marker = D2InstallationProvisioning.get_marker_path()
            stage = D2InstallationProvisioning.get_stage_path()
            store = D2AuthorityManifestStore()
            for p in [marker, stage, store.file_path]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                lock_p = p + ".lock"
                if os.path.exists(lock_p):
                    try:
                        os.remove(lock_p)
                    except OSError:
                        pass

            # 3. Bootstrap fresh genesis manifest under external provisioning authority (which is now in RECOVERY_AUTHORIZED state)
            return cls.bootstrap_genesis_manifest(data)

    @classmethod
    def clear_for_testing(cls) -> None:
        """Controlled teardown strictly for unit test fixtures."""
        if os.environ.get("SCLASS_TEST_FIXTURE_ACTIVE") != "1" and os.environ.get("PYTEST_CURRENT_TEST") is None:
            raise RuntimeError("Monotonic authority state cannot be reset outside active test fixture harness.")
        with cls._bootstrap_lock:
            from events.store import (
                D2AuthorityManifestStore,
                D2InstallationProvisioning,
                DeploymentProvisionerRegistry,
                InMemoryTestDeploymentProvisioner,
                SClassApplication,
            )
            D2InstallationProvisioning.clear_for_testing()
            store = D2AuthorityManifestStore()
            for p in [store.file_path, store.file_path + ".lock"]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            DeploymentProvisionerRegistry.reset_for_testing()
            test_prov = InMemoryTestDeploymentProvisioner()
            SClassApplication(provisioner=test_prov)

    @classmethod
    def _load_from_dict_with_test_root_override(
        cls,
        data: Dict[str, Any],
        test_root_public_key: Any,
        min_version: Optional[int] = None,
    ) -> ReadOnlyActorAuthorityResolver:
        """Private test-only helper to verify rejection of non-canonical root keys."""
        return cls._load_from_dict_internal(data, trusted_root_public_key=test_root_public_key, min_version=min_version)


class PolicyActorKeyRegistry:
    """Certified actor authority registry boundary (lookup-only for D3 policy evaluation).
    
    D3 verification consumes an immutable/sealed authoritative resolver.
    Arbitrary runtime injection or mutation is prohibited and fails closed.
    """
    _sealed_resolver: Optional[PolicyActorAuthorityResolver] = None
    _is_sealed: bool = False

    @classmethod
    def bootstrap_sealed_resolver(cls, resolver: PolicyActorAuthorityResolver) -> None:
        """One-time bootstrap of the application-level sealed authority resolver.
        Fails closed if the resolver is already sealed.
        """
        if cls._is_sealed and cls._sealed_resolver is not None:
            raise RuntimeError("Authority resolver is already sealed and cannot be replaced or re-injected at runtime.")
        if not isinstance(resolver, PolicyActorAuthorityResolver):
            raise TypeError("resolver must implement PolicyActorAuthorityResolver protocol.")
        cls._sealed_resolver = resolver
        cls._is_sealed = True

    @classmethod
    def bootstrap_from_signed_manifest(
        cls,
        data: Dict[str, Any],
        min_version: Optional[int] = None,
    ) -> ReadOnlyActorAuthorityResolver:
        """Authoritative composition root bootstrap: validates signed manifest against Gate 3 root
        and seals the D3 policy authority resolver.
        """
        from events.store import D2InstallationProvisioning
        if not D2InstallationProvisioning.is_installed():
            resolver = SignedAuthorityManifestLoader.bootstrap_genesis_manifest(data)
        else:
            resolver = SignedAuthorityManifestLoader.load_from_dict(data, min_version=min_version)
        cls.bootstrap_sealed_resolver(resolver)
        return resolver

    @classmethod
    def get_sealed_resolver(cls) -> Optional[PolicyActorAuthorityResolver]:
        """Returns the currently sealed authority resolver."""
        return cls._sealed_resolver

    @classmethod
    def lookup_actor(cls, fingerprint: str) -> Optional[ActorKeyRecord]:
        """Read-only lookup of enrolled actor record."""
        if cls._sealed_resolver is not None:
            return cls._sealed_resolver.lookup_actor(fingerprint)
        return None

    @classmethod
    def is_revoked(cls, fingerprint: str) -> bool:
        """Read-only check if key is revoked."""
        if cls._sealed_resolver is not None:
            return cls._sealed_resolver.is_revoked(fingerprint)
        return False

    @classmethod
    def clear_for_testing(cls) -> None:
        """Controlled teardown of sealed resolver strictly for test fixtures."""
        if os.environ.get("SCLASS_TEST_FIXTURE_ACTIVE") != "1" and os.environ.get("PYTEST_CURRENT_TEST") is None:
            raise RuntimeError("Sealed authority cannot be cleared outside active test fixture harness.")
        cls._sealed_resolver = None
        cls._is_sealed = False
        SignedAuthorityManifestLoader.clear_for_testing()


def canonicalize_policy_exception_preimage(exception: PolicyException) -> bytes:
    """Produces the deterministic canonical JCS (RFC 8785) byte sequence binding
    both the exception payload AND the cryptographic signature provenance metadata
    (algorithm, signer_identity, public_key_fingerprint, timestamp).
    """
    from events.serializer import canonicalize_json

    sig = exception.signature
    payload = {
        "exception_id": exception.exception_id,
        "obligation_id": exception.obligation_id,
        "policy_id": exception.policy_id,
        "justification": exception.justification,
        "authorized_by": {
            "actor_id": exception.authorized_by.actor_id,
            "actor_role": exception.authorized_by.actor_role,
            "public_key_fingerprint": exception.authorized_by.public_key_fingerprint,
        },
        "compensating_controls": list(exception.compensating_controls),
        "expiry": exception.expiry,
        "signature_metadata": {
            "algorithm": sig.algorithm if sig else "",
            "signer_identity": sig.signer_identity if sig else "",
            "public_key_fingerprint": sig.public_key_fingerprint if sig else "",
            "timestamp": sig.timestamp if sig else "",
        },
    }
    return canonicalize_json(payload)


def _check_valid_exception(
    exception: PolicyException,
    obligation_id: str,
    policy_id: str,
    eval_timestamp: str,
    actor_resolver: Optional[PolicyActorAuthorityResolver] = None,
) -> None:
    """Validates that a PolicyException is active, unexpired, bound to obligation/policy,
    and cryptographically verified with an active Ed25519 signature binding provenance metadata.
    """
    import hmac

    # 1. Obligation binding
    if exception.obligation_id != obligation_id:
        raise InvalidExceptionError(
            f"Exception obligation mismatch: got '{exception.obligation_id}', expected '{obligation_id}'."
        )

    # 2. Policy binding
    if exception.policy_id != policy_id:
        raise InvalidExceptionError(
            f"Exception policy mismatch: got '{exception.policy_id}', expected '{policy_id}'."
        )

    # 3. Expiry verification
    if exception.expiry is not None:
        try:
            exp_dt = datetime.fromisoformat(exception.expiry.replace("Z", "+00:00"))
            eval_dt = datetime.fromisoformat(eval_timestamp.replace("Z", "+00:00"))
        except Exception as exc:
            raise InvalidExceptionError(f"Invalid timestamp format in PolicyException: {exc}") from exc
        if eval_dt > exp_dt:
            raise ExpiredExceptionError(
                f"PolicyException '{exception.exception_id}' expired at {exception.expiry} (evaluated at {eval_timestamp})."
            )

    # 4. Signature presence and algorithm
    sig = exception.signature
    if not sig or not sig.signature_hex:
        raise InvalidExceptionError(
            f"PolicyException '{exception.exception_id}' lacks valid cryptographic signature."
        )
    if sig.algorithm != "ED25519":
        raise InvalidExceptionError(
            f"Unsupported signature algorithm '{sig.algorithm}': expected 'ED25519'."
        )

    # 5. Fingerprint binding: signature fingerprint must match AuthorizedActor fingerprint
    actor = exception.authorized_by
    if not actor or not actor.public_key_fingerprint:
        raise InvalidExceptionError("PolicyException authorized_by missing public_key_fingerprint.")
    if not hmac.compare_digest(sig.public_key_fingerprint, actor.public_key_fingerprint):
        raise InvalidExceptionError(
            f"Signature public_key_fingerprint '{sig.public_key_fingerprint}' does not match "
            f"AuthorizedActor fingerprint '{actor.public_key_fingerprint}'."
        )

    # 6. Canonical payload digest verification (RFC 8785 JCS binding signature provenance metadata)
    canonical_bytes = canonicalize_policy_exception_preimage(exception)
    expected_digest = hashlib.sha256(canonical_bytes).hexdigest()
    if not hmac.compare_digest(sig.payload_digest, expected_digest):
        raise InvalidExceptionError(
            f"PolicyException payload digest mismatch: expected '{expected_digest}', got '{sig.payload_digest}'."
        )

    # 7. Actor Key Lookup, Revocation Check, and Role/Identity Binding
    actor_fp = actor.public_key_fingerprint
    resolver = actor_resolver or PolicyActorKeyRegistry.get_sealed_resolver()

    if resolver is not None and resolver.is_revoked(actor_fp):
        raise InvalidExceptionError(f"Authorized actor key '{actor_fp}' has been revoked.")

    enrolled = resolver.lookup_actor(actor_fp) if resolver is not None else None
    pub_key = None

    if enrolled is not None:
        if not enrolled.is_active:
            raise InvalidExceptionError(f"Authorized actor key '{actor_fp}' is inactive.")
        if enrolled.actor_id != actor.actor_id or enrolled.actor_role != actor.actor_role:
            raise InvalidExceptionError(
                f"Actor identity mismatch: registered as '{enrolled.actor_id}' ({enrolled.actor_role}), "
                f"got '{actor.actor_id}' ({actor.actor_role})."
            )
        pub_key = enrolled.public_key
    else:
        # Fallback check on Gate3 Authority Keystore
        g3_matched = False
        try:
            from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore
            g3_fp = Gate3AuthorityKeyStore.get_public_key_fingerprint()
            if hmac.compare_digest(actor_fp, g3_fp):
                g3_matched = True
                pub_key = Gate3AuthorityKeyStore.get_public_key()
        except Exception:
            pass

        if not g3_matched:
            try:
                from benchmark.parity.verify_gate_3_certificate import Gate3PublicKeystore
                g3_pub = Gate3PublicKeystore.get_public_key()
                if g3_pub is not None:
                    g3_fp = hashlib.sha256(g3_pub.public_bytes_raw()).hexdigest()
                    if hmac.compare_digest(actor_fp, g3_fp):
                        g3_matched = True
                        pub_key = g3_pub
            except Exception:
                pass

        if g3_matched:
            # Enforce strict Gate3 Root identity binding
            allowed_gate3_actors = {"Gate3AuthoritativeVerifier", "GATE3_AUTHORITY"}
            allowed_gate3_roles = {"CERTIFICATE_AUTHORITY", "SECURITY_AUTHORITY"}
            if actor.actor_id not in allowed_gate3_actors or actor.actor_role not in allowed_gate3_roles:
                raise InvalidExceptionError(
                    f"Actor identity '{actor.actor_id}' ({actor.actor_role}) does not match "
                    f"Gate 3 Authority Root identity."
                )

    if pub_key is None:
        raise InvalidExceptionError(
            f"Authorized actor public key for fingerprint '{actor_fp}' is not enrolled in authority registry."
        )

    # 8. Cryptographic Ed25519 signature verification over canonical bytes
    from cryptography.exceptions import InvalidSignature
    try:
        sig_bytes = bytes.fromhex(sig.signature_hex)
        pub_key.verify(sig_bytes, canonical_bytes)
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise InvalidExceptionError(
            f"Cryptographic Ed25519 signature verification failed for PolicyException '{exception.exception_id}': {exc}"
        ) from exc


def _extract_coverage_pct(
    evidence_item: Evidence,
    context: PolicyEvaluationContext,
) -> Optional[float]:
    """Extracts trusted structured code coverage percentage from an Evidence item.
    
    Enforces strict trust predicate before accepting coverage payload:
    - Valid schema & lifecycle state
    - Trusted provider identity
    - Provider capability matches coverage
    - Provenance present & valid
    - Target/revision binding valid
    - Consumes verified issuer-authenticated trust certificate via Gate 3 verifier interface
    
    Free-form text in observation.diagnostics is strictly rejected as unauthoritative.
    """
    if not CoverageTrustPredicate.is_trusted(evidence_item, context):
        return None

    obs = evidence_item.observation

    # Only accept structured, typed observation mapping from trusted provider
    if not obs.counterexample:
        return None

    for k in ("coverage_pct", "line_coverage", "coverage", "statement_coverage", "branch_coverage"):
        if k in obs.counterexample:
            val = obs.counterexample[k]
            try:
                if isinstance(val, (int, float)):
                    cov = float(val)
                    if math.isnan(cov) or math.isinf(cov) or cov < 0.0 or cov > 100.0:
                        raise PolicyValidationError(f"Invalid coverage range: {cov}")
                    return cov
                elif isinstance(val, str):
                    m = re.search(r"^([0-9]+(?:\.[0-9]+)?)\s*%?$", val.strip())
                    if m:
                        cov = float(m.group(1))
                        if cov < 0.0 or cov > 100.0:
                            raise PolicyValidationError(f"Invalid coverage range: {cov}")
                        return cov
                    else:
                        raise PolicyValidationError(f"Malformed coverage string: '{val}'")
                else:
                    raise PolicyValidationError(f"Malformed coverage type: '{type(val).__name__}'")
            except Exception as exc:
                if isinstance(exc, PolicyValidationError):
                    raise
                raise PolicyValidationError(f"Malformed code coverage value: {val}") from exc

    return None


def evaluate_rule(
    rule: PolicyRule,
    context: PolicyEvaluationContext,
) -> RuleEvaluationResult:
    """Evaluates a single PolicyRule against the PolicyEvaluationContext."""
    rtype = rule.rule_type
    params = dict(rule.parameters)

    # 1. REQUIRE_CAPABILITY
    if rtype == RuleType.REQUIRE_CAPABILITY:
        required_cap = params.get("capability")
        matching_evidence = [
            e for e in context.evidence
            if e.capability == required_cap
            and e.validity == EvidenceValidity.VALID
            and e.polarity == EvidencePolarity.SUPPORTS
            and e.observation.raw_status == RawStatus.PASS
        ]
        if matching_evidence:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason=f"Found {len(matching_evidence)} valid supporting evidence items with capability '{required_cap}'.",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"No valid supporting evidence with required capability '{required_cap}'.",
            )

    # 2. REQUIRE_TIER
    elif rtype == RuleType.REQUIRE_TIER:
        required_tier = params.get("tier")
        min_count = params.get("min_count", 1)

        # Mandatory Rule for V4 (Judgment / Adversarial Exploratory): Evidence for V4 claims can NEVER satisfy a mandatory obligation on its own
        if required_tier in (ClaimTier.V4_ADVERSARIAL_EXPLORATORY.value, "V4_JUDGMENT"):
            has_corroborating = any(
                c.tier in (ClaimTier.V0_OBSERVABLE, ClaimTier.V1_STRUCTURAL, ClaimTier.V2_BEHAVIORAL, ClaimTier.V3_PROPERTY)
                and c.status in (ClaimStatus.SUPPORTED, ClaimStatus.WAIVED)
                for c in context.claims
            )
            if not has_corroborating:
                return RuleEvaluationResult(
                    rule=rule,
                    passed=False,
                    requires_exception=True,
                    reason="Tier V4 cannot satisfy a mandatory obligation without corroborating V0-V3 evidence or signed exception.",
                )

        supporting_claims = [
            c for c in context.claims
            if c.tier.value == required_tier
            and c.status in (ClaimStatus.SUPPORTED, ClaimStatus.WAIVED)
        ]

        if len(supporting_claims) >= min_count:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason=f"Found {len(supporting_claims)} supporting claims for tier '{required_tier}' (>= {min_count}).",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"Insufficient supporting claims for tier '{required_tier}': found {len(supporting_claims)}, expected {min_count}.",
            )

    # 3. NO_CONFLICTS
    elif rtype == RuleType.NO_CONFLICTS:
        conflicts = [
            e for e in context.evidence
            if e.validity == EvidenceValidity.CONFLICTED
            or e.polarity == EvidencePolarity.REFUTES
            or e.observation.raw_status == RawStatus.FAIL
        ]
        if not conflicts:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason="No conflicting or refuting evidence detected.",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"Detected {len(conflicts)} conflicting/refuting evidence items.",
            )

    # 4. REQUIRE_INDEPENDENT_PROVIDERS
    elif rtype == RuleType.REQUIRE_INDEPENDENT_PROVIDERS:
        min_sources = params.get("min_independent_sources", 1)
        group_by = params.get("group_by", "PROVIDER_TYPE")

        valid_supporting = [
            e for e in context.evidence
            if e.validity == EvidenceValidity.VALID
            and e.polarity == EvidencePolarity.SUPPORTS
            and e.observation.raw_status == RawStatus.PASS
        ]

        if group_by == "PROVIDER_TYPE" or group_by == "AUTHOR":
            distinct_groups = set(e.provider_id for e in valid_supporting)
        elif group_by == "EXECUTION_PROCESS":
            distinct_groups = set(e.execution_id for e in valid_supporting)
        else:
            distinct_groups = set(e.independence_group for e in valid_supporting)

        if len(distinct_groups) >= min_sources:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason=f"Found {len(distinct_groups)} distinct provider groups (>= required {min_sources}).",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"Insufficient independent provider sources: found {len(distinct_groups)}, required {min_sources}.",
            )

    # 5. FORBID_SYNTHETIC
    elif rtype == RuleType.FORBID_SYNTHETIC:
        synthetic_evidence = [
            e for e in context.evidence
            if "synthetic" in e.provider_id.lower() or "simulation" in e.provenance.engine_name.lower()
        ]
        if not synthetic_evidence:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason="No synthetic/simulation evidence detected.",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"Detected {len(synthetic_evidence)} synthetic evidence items violating FORBID_SYNTHETIC.",
            )

    # 6. MAX_STALENESS_COMMITS
    elif rtype == RuleType.MAX_STALENESS_COMMITS:
        stale = [e for e in context.evidence if e.validity == EvidenceValidity.STALE]
        if not stale:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason="No stale evidence detected.",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"Detected {len(stale)} stale evidence items.",
            )

    # 7. REQUIRE_MIN_TRIALS
    elif rtype == RuleType.REQUIRE_MIN_TRIALS:
        min_trials = params.get("min_trials", 1)
        valid_supporting = [
            e for e in context.evidence
            if e.validity == EvidenceValidity.VALID
            and e.polarity == EvidencePolarity.SUPPORTS
            and e.observation.raw_status == RawStatus.PASS
        ]
        if len(valid_supporting) >= min_trials:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason=f"Found {len(valid_supporting)} trial evidence items (>= {min_trials}).",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"Insufficient trial evidence: found {len(valid_supporting)}, expected {min_trials}.",
            )

    # 8. REQUIRE_CODE_COVERAGE
    elif rtype == RuleType.REQUIRE_CODE_COVERAGE:
        min_cov = float(params.get("min_coverage_pct", 85.0))
        extracted_coverages: List[float] = []

        for e in context.evidence:
            cov = _extract_coverage_pct(e, context)
            if cov is not None:
                extracted_coverages.append(cov)

        if not extracted_coverages:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason="Missing trusted structured code coverage evidence in evaluation context.",
            )

        max_actual_coverage = max(extracted_coverages)
        if max_actual_coverage >= min_cov:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason=f"Actual code coverage {max_actual_coverage:.2f}% satisfies required threshold {min_cov:.2f}%.",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"Actual code coverage {max_actual_coverage:.2f}% < required threshold {min_cov:.2f}%.",
            )

    raise PolicyValidationError(f"Unsupported rule type: {rtype}")


def evaluate_expression(
    expression: PolicyExpression,
    context: PolicyEvaluationContext,
) -> Tuple[bool, bool, List[RuleEvaluationResult], List[str]]:
    """Evaluates a PolicyExpression tree recursively.
    
    Returns:
        Tuple of (passed: bool, requires_exception: bool, evaluated_rules, unmet_reasons)
    """
    comb = expression.combinator
    results: List[RuleEvaluationResult] = []
    unmet: List[str] = []

    # Conditional branching
    if comb == CombinatorType.CONDITIONAL:
        cond = dict(expression.condition or {})
        pred = cond.get("predicate")
        val = cond.get("value")

        condition_matched = False
        if pred == "criticality":
            condition_matched = (context.obligation.criticality.value == val)
        elif pred == "category":
            condition_matched = (context.obligation.category.value == val)

        sub_expr = expression.then_expression if condition_matched else expression.else_expression
        if sub_expr is None:
            raise PolicyValidationError("CONDITIONAL branch expression is null.")
        return evaluate_expression(sub_expr, context)

    # Flat rule combinators
    for r in expression.rules:
        res = evaluate_rule(r, context)
        results.append(res)
        if not res.passed:
            unmet.append(res.reason)

    if comb == CombinatorType.ALL:
        passed = all(r.passed for r in results)
        req_exc = any(r.requires_exception for r in results)
        return passed, req_exc, results, unmet

    elif comb == CombinatorType.ANY:
        passed = any(r.passed for r in results)
        req_exc = False if passed else any(r.requires_exception for r in results)
        return passed, req_exc, results, unmet

    elif comb == CombinatorType.AT_LEAST:
        min_c = expression.min_count or 1
        pass_count = sum(1 for r in results if r.passed)
        passed = (pass_count >= min_c)
        req_exc = False if passed else any(r.requires_exception for r in results)
        return passed, req_exc, results, unmet

    raise PolicyValidationError(f"Unsupported combinator: {comb}")


def evaluate_policy(
    policy: Policy,
    context: PolicyEvaluationContext,
    actor_resolver: Optional[PolicyActorAuthorityResolver] = None,
) -> PolicyDecision:
    """Pure, side-effect free, deterministic evaluation of an effective policy against an evaluation context."""
    if not isinstance(policy, Policy):
        raise TypeError("Expected Policy instance.")
    if not isinstance(context, PolicyEvaluationContext):
        raise TypeError("Expected PolicyEvaluationContext instance.")

    passed, req_exc, rule_results, unmet = evaluate_expression(policy.expression, context)
    exceptions_applied: List[str] = []

    if passed:
        decision = PolicyDecisionType.ALLOW
        rationale = "All policy constraints successfully satisfied."
    else:
        # Check if valid matching exceptions exist for unmet rules
        applicable_exceptions = []
        for exc in context.exceptions:
            try:
                _check_valid_exception(
                    exc,
                    context.obligation.obligation_id,
                    policy.policy_id,
                    context.evaluation_timestamp,
                    actor_resolver=actor_resolver,
                )
                applicable_exceptions.append(exc)
            except (ExpiredExceptionError, InvalidExceptionError):
                raise

        if applicable_exceptions:
            decision = PolicyDecisionType.ALLOW
            exceptions_applied = [e.exception_id for e in applicable_exceptions]
            rationale = f"Policy satisfied via authorized exceptions: {', '.join(exceptions_applied)}."
        elif req_exc:
            decision = PolicyDecisionType.REQUIRE_EXCEPTION
            rationale = f"Policy requires explicit exception authorization: {'; '.join(unmet)}."
        else:
            decision = PolicyDecisionType.DENY
            rationale = f"Policy evaluation failed: {'; '.join(unmet)}."

    return PolicyDecision(
        decision=decision,
        scope_evaluated=policy.scope_level,
        rules_evaluated=tuple(rule_results),
        unmet_requirements=tuple(unmet),
        exceptions_applied=tuple(exceptions_applied),
        rationale=rationale,
    )
