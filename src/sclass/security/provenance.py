"""
S-Class Security: Sigstore Cryptographic Provenance Engine (RC.15).
Uses official Sigstore Python API where practical and CLI/provider execution where required.
Keyless signing and verification for evidence receipts and ledger checkpoints.
Unavailable tools produce UNKNOWN/UNVERIFIED evidence and never fabricate success (Law L5).
"""

from __future__ import annotations
import os
import json
import time
import shutil
import hashlib
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple, Union

from sclass.security.supply_chain import ToolHealth


@dataclass(frozen=True)
class ProvenanceReceipt:
    """Cryptographically anchored provenance statement issued by Sigstore or local keys."""
    receipt_id: str
    status: str  # SUCCESS | UNKNOWN | ERROR
    is_verified: bool
    digest: str
    signature: str = ""
    certificate: str = ""
    identity: str = ""
    bundle_json: Optional[str] = None
    tool_version: str = "unknown"
    signed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "status": self.status,
            "is_verified": self.is_verified,
            "digest": self.digest,
            "signature": self.signature,
            "certificate": self.certificate,
            "identity": self.identity,
            "tool_version": self.tool_version,
            "signed_at": self.signed_at,
            "error": self.error,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class ProvenanceVerificationResult:
    """Result of verifying a cryptographic provenance receipt."""
    is_valid: bool
    status: str  # SUCCESS | UNKNOWN | ERROR
    identity: str = ""
    verified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "status": self.status,
            "identity": self.identity,
            "verified_at": self.verified_at,
            "error": self.error,
            "details": self.details,
        }


class SigstoreProvider:
    """
    Cryptographic provenance provider integrating official Sigstore API and cosign CLI.
    Enforces Law L5: Evidence has provenance.
    Unavailable tools produce UNKNOWN/UNVERIFIED evidence and never fabricate success.
    """

    def __init__(self, cli_path: Optional[str] = None):
        self.cli_path = (
            cli_path
            or os.environ.get("COSIGN_BIN")
            or shutil.which("cosign")
            or shutil.which("sigstore")
        )
        self._has_python_sigstore = False
        try:
            import sigstore
            self._has_python_sigstore = True
        except ImportError:
            self._has_python_sigstore = False

    @property
    def is_available(self) -> bool:
        return self._has_python_sigstore or (self.cli_path is not None and os.path.isfile(self.cli_path))

    def health(self) -> ToolHealth:
        """Discovers capabilities, version, and execution health."""
        if self._has_python_sigstore:
            try:
                import sigstore
                ver = getattr(sigstore, "__version__", "python-sigstore-available")
                return ToolHealth(
                    name="sigstore",
                    available=True,
                    version=f"python-sigstore-{ver}",
                    status="HEALTHY",
                    capabilities=["keyless.sign", "keyless.verify", "in-toto.attestation", "python.native"],
                )
            except Exception as ex:
                pass

        if self.cli_path and shutil.which(self.cli_path):
            try:
                res = subprocess.run([self.cli_path, "version"], capture_output=True, text=True, timeout=5.0)
                ver = res.stdout.strip().splitlines()[0] if res.stdout else "cosign-cli"
                return ToolHealth(
                    name="sigstore",
                    available=True,
                    version=ver,
                    executable_path=self.cli_path,
                    status="HEALTHY",
                    capabilities=["keyless.sign", "keyless.verify", "cli.cosign"],
                )
            except Exception as ex:
                return ToolHealth(
                    name="sigstore",
                    available=False,
                    version="error",
                    executable_path=self.cli_path,
                    status="DEGRADED",
                    capabilities=[],
                    error=str(ex),
                )

        return ToolHealth(
            name="sigstore",
            available=False,
            version="unavailable",
            status="UNAVAILABLE",
            capabilities=[],
            error="Neither Sigstore Python SDK nor cosign binary available in environment.",
        )

    def sign_payload(
        self,
        payload: Union[str, bytes, Dict[str, Any]],
        identity: Optional[str] = None,
        timeout: float = 30.0,
    ) -> ProvenanceReceipt:
        """
        Signs evidence receipt or ledger checkpoint.
        If tools unavailable, produces UNKNOWN/UNVERIFIED evidence. Never fabricates success.
        """
        # Canonical bytes and SHA-256 digest
        if isinstance(payload, dict):
            raw_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        elif isinstance(payload, str):
            raw_bytes = payload.encode("utf-8")
        else:
            raw_bytes = payload

        digest = hashlib.sha256(raw_bytes).hexdigest()
        health = self.health()

        if not health.available:
            return ProvenanceReceipt(
                receipt_id=f"sig_unavailable_{digest[:12]}",
                status="REAL_SIGSTORE_UNAVAILABLE",
                is_verified=False,
                digest=digest,
                identity=identity or "unspecified",
                tool_version="unavailable",
                error="Sigstore unavailable. Provenance is UNVERIFIED (Law L5).",
                provenance={"provider": "sigstore", "status": "REAL_SIGSTORE_UNAVAILABLE"},
            )

        # Python SDK signing via official sigstore
        if self._has_python_sigstore:
            try:
                import sigstore
                from sigstore.oidc import Issuer
                from sigstore.sign import SigningContext

                # Real keyless signing requires OIDC identity token
                issuer = Issuer.production()
                oidc_token = issuer.identity_token()
                ctx = SigningContext.production()
                with ctx.signer(oidc_token) as signer:
                    bundle = signer.sign_artifact(raw_bytes)
                    bundle_json = bundle.to_json()
                    return ProvenanceReceipt(
                        receipt_id=f"sig_real_{digest[:12]}",
                        status="REAL_SIGSTORE_SUCCESS",
                        is_verified=True,
                        digest=digest,
                        signature=bundle_json,
                        bundle_json=bundle_json,
                        identity=identity or "sigstore-signer",
                        tool_version=health.version,
                        provenance={"provider": "sigstore-python", "mode": "native"},
                    )
            except Exception as ex:
                return ProvenanceReceipt(
                    receipt_id=f"sig_err_{digest[:12]}",
                    status="REAL_SIGSTORE_ERROR",
                    is_verified=False,
                    digest=digest,
                    error=f"Real Sigstore signing error: {ex}",
                    provenance={"provider": "sigstore-python", "status": "REAL_SIGSTORE_ERROR"},
                )

        # CLI execution via cosign
        if self.cli_path and shutil.which(self.cli_path):
            import tempfile
            temp_in = None
            temp_sig = None
            try:
                with tempfile.NamedTemporaryFile(delete=False) as f_in:
                    f_in.write(raw_bytes)
                    temp_in = f_in.name
                temp_sig = temp_in + ".sig"

                cmd = [self.cli_path, "sign-blob", "--yes", "--output-signature", temp_sig, temp_in]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                if proc.returncode == 0 and os.path.isfile(temp_sig):
                    with open(temp_sig, "r", encoding="utf-8") as f_s:
                        real_sig = f_s.read().strip()
                    return ProvenanceReceipt(
                        receipt_id=f"sig_real_{digest[:12]}",
                        status="REAL_SIGSTORE_SUCCESS",
                        is_verified=True,
                        digest=digest,
                        signature=real_sig,
                        identity=identity or "cosign_signer",
                        tool_version=health.version,
                        provenance={"provider": "cosign", "mode": "cli"},
                    )
                else:
                    return ProvenanceReceipt(
                        receipt_id=f"sig_err_{digest[:12]}",
                        status="REAL_SIGSTORE_ERROR",
                        is_verified=False,
                        digest=digest,
                        error=proc.stderr.strip() or f"cosign failed with exit code {proc.returncode}",
                        provenance={"provider": "cosign", "status": "REAL_SIGSTORE_ERROR"},
                    )
            except Exception as ex:
                return ProvenanceReceipt(
                    receipt_id=f"sig_err_{digest[:12]}",
                    status="REAL_SIGSTORE_ERROR",
                    is_verified=False,
                    digest=digest,
                    error=str(ex),
                    provenance={"provider": "cosign", "status": "REAL_SIGSTORE_ERROR"},
                )
            finally:
                if temp_in and os.path.exists(temp_in):
                    try:
                        os.unlink(temp_in)
                    except OSError:
                        pass
                if temp_sig and os.path.exists(temp_sig):
                    try:
                        os.unlink(temp_sig)
                    except OSError:
                        pass

        return ProvenanceReceipt(
            receipt_id=f"sig_unavailable_{digest[:12]}",
            status="REAL_SIGSTORE_UNAVAILABLE",
            is_verified=False,
            digest=digest,
            error="No supported signing provider resolved.",
            provenance={"provider": "sigstore", "status": "REAL_SIGSTORE_UNAVAILABLE"},
        )

    def verify_provenance(
        self,
        payload: Union[str, bytes, Dict[str, Any]],
        receipt: ProvenanceReceipt,
        timeout: float = 30.0,
    ) -> ProvenanceVerificationResult:
        """
        Cryptographically verifies provenance signature against receipt content,
        digest, and cryptographic trust anchors. Never merely compares digest.
        """
        if receipt.status != "REAL_SIGSTORE_SUCCESS" or not receipt.is_verified:
            return ProvenanceVerificationResult(
                is_valid=False,
                status=receipt.status if receipt.status in ("REAL_SIGSTORE_UNAVAILABLE", "REAL_SIGSTORE_ERROR") else "UNKNOWN",
                error=f"Cannot verify receipt marked {receipt.status}/UNVERIFIED.",
            )

        if isinstance(payload, dict):
            raw_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        elif isinstance(payload, str):
            raw_bytes = payload.encode("utf-8")
        else:
            raw_bytes = payload

        current_digest = hashlib.sha256(raw_bytes).hexdigest()
        if current_digest != receipt.digest:
            return ProvenanceVerificationResult(
                is_valid=False,
                status="REAL_SIGSTORE_ERROR",
                error=f"Digest mismatch: payload hash {current_digest} != receipt digest {receipt.digest}. Tampering detected.",
            )

        # Real cryptographic verification via Python Sigstore SDK
        if receipt.bundle_json and self._has_python_sigstore:
            try:
                import sigstore
                from sigstore.models import Bundle
                from sigstore.verify import Verifier, Policy
                from sigstore.verify.policy import Identity

                verifier = Verifier.production()
                bundle = Bundle.from_json(receipt.bundle_json)
                policy = Policy(Identity(receipt.identity)) if receipt.identity else Policy.unconstrained()
                result = verifier.verify_artifact(raw_bytes, bundle, policy)
                if result:
                    return ProvenanceVerificationResult(
                        is_valid=True,
                        status="REAL_SIGSTORE_SUCCESS",
                        identity=receipt.identity,
                        details={"tool_version": receipt.tool_version, "engine": "sigstore-python"},
                    )
            except Exception as ex:
                return ProvenanceVerificationResult(
                    is_valid=False,
                    status="REAL_SIGSTORE_ERROR",
                    error=f"Sigstore cryptographic verification failed: {ex}",
                )

        # Real cryptographic verification via cosign CLI
        if receipt.signature and self.cli_path and shutil.which(self.cli_path):
            import tempfile
            temp_in = None
            temp_sig = None
            try:
                with tempfile.NamedTemporaryFile(delete=False) as f_in:
                    f_in.write(raw_bytes)
                    temp_in = f_in.name
                with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as f_s:
                    f_s.write(receipt.signature)
                    temp_sig = f_s.name

                cmd = [self.cli_path, "verify-blob", "--signature", temp_sig, temp_in]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                if proc.returncode == 0:
                    return ProvenanceVerificationResult(
                        is_valid=True,
                        status="REAL_SIGSTORE_SUCCESS",
                        identity=receipt.identity,
                        details={"signature": receipt.signature, "tool_version": receipt.tool_version, "engine": "cosign"},
                    )
                else:
                    return ProvenanceVerificationResult(
                        is_valid=False,
                        status="REAL_SIGSTORE_ERROR",
                        error=proc.stderr.strip() or f"cosign verify-blob failed with exit code {proc.returncode}",
                    )
            except Exception as ex:
                return ProvenanceVerificationResult(
                    is_valid=False,
                    status="REAL_SIGSTORE_ERROR",
                    error=f"CLI verification exception: {ex}",
                )
            finally:
                if temp_in and os.path.exists(temp_in):
                    try:
                        os.unlink(temp_in)
                    except OSError:
                        pass
                if temp_sig and os.path.exists(temp_sig):
                    try:
                        os.unlink(temp_sig)
                    except OSError:
                        pass

        return ProvenanceVerificationResult(
            is_valid=False,
            status="REAL_SIGSTORE_ERROR",
            error="No valid cryptographic verification engine could corroborate the signature.",
        )
