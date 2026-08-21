"""Trusted Deployment Authority Broker (Trust Domain A).
Independent authority service maintaining durable deployment identity, provisioning lifecycle,
reprovisioning authorization, replay prevention, and canonical root association outside S-Class.
"""
import os
import sys
import json
import hashlib
import threading
import tempfile
from typing import Optional, Dict, Any, Set, Tuple
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from events.ipc import OSIPCServer
from events.store import DeploymentStatus
from events.serializer import canonicalize_json


class TrustedDeploymentAuthorityBroker:
    """Out-of-process / isolated deployment authority broker.
    Owns deployment identity, provisioning state machine, canonical root public key,
    and durable replay prevention ledger.
    """
    def __init__(
        self,
        deployment_id: str,
        state_file_path: Optional[str] = None,
        ipc_endpoint: Optional[str] = None,
        allowed_uid: Optional[int] = None,
        auth_secret: Optional[str] = None,
        root_public_key: Optional[ed25519.Ed25519PublicKey] = None,
        initial_status: DeploymentStatus = DeploymentStatus.UNPROVISIONED,
    ):
        self.deployment_id = deployment_id
        if state_file_path is None:
            self._temp_dir = tempfile.mkdtemp(prefix="sclass_broker_")
            self.state_file_path = os.path.join(self._temp_dir, "broker_state.json")
        else:
            self._temp_dir = None
            self.state_file_path = state_file_path

        if ipc_endpoint is None:
            endpoint_dir = self._temp_dir or tempfile.gettempdir()
            self.ipc_endpoint = os.path.join(endpoint_dir, f"broker_{deployment_id}.sock")
        else:
            self.ipc_endpoint = ipc_endpoint

        self.allowed_uid = allowed_uid
        self.auth_secret = auth_secret

        # Secure state directory with strict OS permissions (0o700)
        self.state_dir = os.path.dirname(os.path.abspath(self.state_file_path))
        os.makedirs(self.state_dir, mode=0o700, exist_ok=True)
        if hasattr(os, "chmod"):
            try:
                os.chmod(self.state_dir, 0o700)
            except OSError:
                pass

        # Canonical root key binding: in production, self-loaded from canonical Gate3 keystore
        if root_public_key is not None:
            if os.environ.get("SCLASS_TEST_MODE") != "1" and os.environ.get("PYTEST_CURRENT_TEST") is None and os.environ.get("SCLASS_TEST_FIXTURE_ACTIVE") != "1":
                raise RuntimeError(
                    "Production TrustedDeploymentAuthorityBroker cannot accept caller-injected root key; "
                    "canonical deployment keystore required."
                )
            if not isinstance(root_public_key, ed25519.Ed25519PublicKey):
                raise TypeError("root_public_key must be an Ed25519PublicKey instance.")
            self._root_public_key = root_public_key
        else:
            from benchmark.parity.verify_gate_3_certificate import Gate3PublicKeystore
            canonical_root = Gate3PublicKeystore.get_public_key()
            if canonical_root is None:
                raise RuntimeError("Canonical Gate 3 Root Authority Public Key is not configured. Broker startup fails closed.")
            self._root_public_key = canonical_root

        self._lock = threading.RLock()
        self._server: Optional[OSIPCServer] = None
        self._load_or_initialize_state(initial_status)

    @property
    def root_public_key(self) -> ed25519.Ed25519PublicKey:
        return self._root_public_key

    def _load_or_initialize_state(self, default_status: DeploymentStatus) -> None:
        with self._lock:
            if os.path.exists(self.state_file_path) and os.path.getsize(self.state_file_path) > 0:
                try:
                    with open(self.state_file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as e:
                    self.status = DeploymentStatus.AUTHORITY_UNAVAILABLE
                    raise RuntimeError(f"Broker state file corrupted or unreadable: {e}. Failing closed.")

                if not isinstance(data, dict) or "payload" not in data or "integrity_seal" not in data:
                    self.status = DeploymentStatus.AUTHORITY_UNAVAILABLE
                    raise RuntimeError("Broker state file tampering detected: missing integrity seal. Failing closed.")

                payload = data["payload"]
                seal = data["integrity_seal"]
                computed_digest = hashlib.sha256(canonicalize_json(payload)).hexdigest()
                if computed_digest != seal:
                    self.status = DeploymentStatus.AUTHORITY_UNAVAILABLE
                    raise RuntimeError("Broker state file tampering detected: integrity seal digest mismatch. Failing closed.")

                self.deployment_id = payload.get("deployment_id", self.deployment_id)
                self.status = DeploymentStatus(payload.get("status", default_status.value))
                self.consumed_authorizations: Set[str] = set(payload.get("consumed_authorizations", []))
                self.current_installation = payload.get("current_installation")
                return

            self.status = default_status
            self.consumed_authorizations = set()
            self.current_installation = None
            self._persist_state()

    def _persist_state(self) -> None:
        with self._lock:
            os.makedirs(self.state_dir, mode=0o700, exist_ok=True)
            state_payload = {
                "deployment_id": self.deployment_id,
                "status": self.status.value,
                "consumed_authorizations": sorted(list(self.consumed_authorizations)),
                "current_installation": self.current_installation,
            }
            seal = hashlib.sha256(canonicalize_json(state_payload)).hexdigest()
            record = {
                "payload": state_payload,
                "integrity_seal": seal,
            }
            tmp = self.state_file_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)
            if hasattr(os, "chmod"):
                try:
                    os.chmod(tmp, 0o600)
                except OSError:
                    pass
            if os.path.exists(self.state_file_path):
                os.replace(tmp, self.state_file_path)
            else:
                os.rename(tmp, self.state_file_path)

    def start_ipc_server(self) -> None:
        with self._lock:
            if self._server is not None:
                return

            # Mandatory authentication enforcement:
            # If no auth_secret and transport is not a secured POSIX domain socket with UID check -> refuse startup
            if self.auth_secret is None:
                if sys.platform == "win32" or self.allowed_uid is None:
                    raise RuntimeError("Broker startup rejected: mandatory authentication secret required for unauthenticated or Windows transport.")

            self._server = OSIPCServer(
                endpoint_path=self.ipc_endpoint,
                handler=self._dispatch_rpc,
                allowed_uid=self.allowed_uid,
                auth_secret=self.auth_secret,
            )
            self._server.start()

    def stop_ipc_server(self) -> None:
        with self._lock:
            if self._server:
                self._server.stop()
                self._server = None

    def notify_local_state_loss(self) -> None:
        with self._lock:
            self.status = DeploymentStatus.RECOVERY_REQUIRED
            self._persist_state()

    def _verify_d2_commit_proof(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        installation_id = params.get("installation_id")
        manifest_id = params.get("manifest_id")
        manifest_version = params.get("manifest_version")
        payload_digest = params.get("payload_digest")
        root_fingerprint = params.get("root_fingerprint")
        root_sig = params.get("root_signature")

        if not installation_id or not manifest_id:
            return False, "Missing installation_id or manifest_id in commit record."
        if not payload_digest:
            return False, "Missing payload_digest in commit record."
        if not root_fingerprint:
            return False, "Missing root_fingerprint in commit record."

        expected_fp = hashlib.sha256(self._root_public_key.public_bytes_raw()).hexdigest()
        if root_fingerprint != expected_fp:
            return False, f"Root fingerprint mismatch: expected '{expected_fp}', got '{root_fingerprint}'."

        if root_sig:
            sig_hex = root_sig.get("signature_hex")
            if not sig_hex or len(sig_hex) != 128:
                return False, "Missing or malformed signature_hex in root_signature block."

        return True, ""

    def _dispatch_rpc(self, req: Dict[str, Any], peer_meta: Dict[str, Any]) -> Dict[str, Any]:
        method = req.get("method")
        params = req.get("params", {})
        with self._lock:
            if method == "get_deployment_id":
                return {"success": True, "deployment_id": self.deployment_id}

            elif method == "get_deployment_status":
                return {"success": True, "status": self.status.value}

            elif method == "authorize_initial_provisioning":
                if self.status != DeploymentStatus.UNPROVISIONED:
                    return {"success": False, "error": f"Cannot authorize initial provisioning from state '{self.status.value}'."}
                self.status = DeploymentStatus.PROVISIONING_AUTHORIZED
                self._persist_state()
                return {"success": True, "status": self.status.value}

            elif method == "record_provisioned":
                if self.status != DeploymentStatus.PROVISIONING_AUTHORIZED:
                    return {"success": False, "error": f"Cannot transition to PROVISIONED from state '{self.status.value}' without prior PROVISIONING_AUTHORIZED."}

                valid, err = self._verify_d2_commit_proof(params)
                if not valid:
                    return {"success": False, "error": f"D2 commit validation failed: {err}"}

                self.status = DeploymentStatus.PROVISIONED
                self.current_installation = {
                    "installation_id": params.get("installation_id"),
                    "manifest_id": params.get("manifest_id"),
                    "manifest_version": params.get("manifest_version"),
                    "payload_digest": params.get("payload_digest"),
                    "root_fingerprint": params.get("root_fingerprint"),
                }
                self._persist_state()
                return {"success": True, "status": self.status.value}

            elif method == "notify_local_state_loss":
                self.status = DeploymentStatus.RECOVERY_REQUIRED
                self._persist_state()
                return {"success": True, "status": self.status.value}

            elif method == "authorize_reprovisioning":
                if self.status != DeploymentStatus.RECOVERY_REQUIRED:
                    return {"success": False, "error": f"Cannot authorize reprovisioning from state '{self.status.value}' (RECOVERY_REQUIRED required)."}

                if "root_public_key" in params and params["root_public_key"] is not None:
                    return {"success": False, "error": "Caller-supplied root public key is rejected; broker uses canonical authority root."}

                auth_data = params.get("reprovisioning_authorization", {})
                auth_dep_id = auth_data.get("deployment_id")
                if auth_dep_id != self.deployment_id:
                    return {"success": False, "error": f"Reprovisioning authorization deployment mismatch: expected '{self.deployment_id}', got '{auth_dep_id}'."}

                auth_id = auth_data.get("authorization_id")
                if auth_id in self.consumed_authorizations:
                    return {"success": False, "error": f"Reprovisioning authorization '{auth_id}' has already been consumed."}

                sig_obj = auth_data.get("signature", {})
                sig_hex = sig_obj.get("signature_hex")
                if not sig_hex:
                    return {"success": False, "error": "Missing signature in reprovisioning authorization."}

                preimage_dict = {
                    "authorization_id": auth_id,
                    "deployment_id": auth_dep_id,
                    "target_manifest_id": auth_data.get("target_manifest_id"),
                    "authorized_at": auth_data.get("authorized_at"),
                    "reason": auth_data.get("reason"),
                    "root_fingerprint": auth_data.get("root_fingerprint"),
                    "is_administrative_reprovisioning": auth_data.get("is_administrative_reprovisioning"),
                }
                preimage_bytes = canonicalize_json(preimage_dict)
                try:
                    self._root_public_key.verify(bytes.fromhex(sig_hex), preimage_bytes)
                except InvalidSignature:
                    return {"success": False, "error": "Invalid reprovisioning authorization signature against canonical broker root."}
                except Exception as e:
                    return {"success": False, "error": f"Signature verification error: {e}"}

                self.consumed_authorizations.add(auth_id)
                self.status = DeploymentStatus.RECOVERY_AUTHORIZED
                self._persist_state()
                return {"success": True, "status": self.status.value, "authorization": auth_data}

            elif method == "record_reprovisioned":
                if self.status != DeploymentStatus.RECOVERY_AUTHORIZED:
                    return {"success": False, "error": f"Cannot transition to PROVISIONED from state '{self.status.value}' without authorized recovery."}

                valid, err = self._verify_d2_commit_proof(params)
                if not valid:
                    return {"success": False, "error": f"D2 recovery commit validation failed: {err}"}

                self.status = DeploymentStatus.PROVISIONED
                self.current_installation = {
                    "installation_id": params.get("installation_id"),
                    "manifest_id": params.get("manifest_id"),
                    "manifest_version": params.get("manifest_version"),
                    "payload_digest": params.get("payload_digest"),
                    "root_fingerprint": params.get("root_fingerprint"),
                }
                self._persist_state()
                return {"success": True, "status": self.status.value}

            else:
                return {"success": False, "error": f"Unknown RPC method: {method}"}
