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
        d2_store_path: Optional[str] = None,
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
        if d2_store_path is not None:
            if os.environ.get("SCLASS_TEST_MODE") != "1" and not os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("SCLASS_TEST_FIXTURE_ACTIVE") != "1":
                raise RuntimeError(
                    "Production TrustedDeploymentAuthorityBroker cannot accept caller-injected d2_store_path; "
                    "canonical deployment store configuration required."
                )
            self.d2_store_path = os.path.abspath(d2_store_path)
        else:
            from events.store import get_canonical_d2_event_store_path
            self.d2_store_path = get_canonical_d2_event_store_path()

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
            if os.environ.get("SCLASS_TEST_MODE") != "1" and not os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("SCLASS_TEST_FIXTURE_ACTIVE") != "1":
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

                if "canonical_d2_store_path" in payload:
                    persisted_d2_path = payload["canonical_d2_store_path"]
                    if persisted_d2_path != self.d2_store_path:
                        self.status = DeploymentStatus.AUTHORITY_UNAVAILABLE
                        raise RuntimeError(
                            f"Broker D2 store binding mismatch on restart: state was bound to '{persisted_d2_path}', "
                            f"current configuration is '{self.d2_store_path}'. Failing closed."
                        )

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
                "canonical_d2_store_path": self.d2_store_path,
                "status": self.status.value,
                "consumed_authorizations": sorted(list(self.consumed_authorizations)),
                "current_installation": self.current_installation,
            }
            seal = hashlib.sha256(canonicalize_json(state_payload)).hexdigest()
            wrapper = {
                "payload": state_payload,
                "integrity_seal": seal,
            }
            raw = canonicalize_json(wrapper)

            # Atomic write + sync
            tmp_path = f"{self.state_file_path}.tmp_{os.getpid()}_{threading.get_ident()}"
            with open(tmp_path, "wb") as f:
                f.write(raw + b"\n")
                f.flush()
                os.fsync(f.fileno())

            if hasattr(os, "chmod"):
                try:
                    os.chmod(tmp_path, 0o600)
                except OSError:
                    pass

            os.replace(tmp_path, self.state_file_path)

    def start_ipc_server(self) -> None:
        with self._lock:
            if self._server is not None:
                return

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
        from cryptography.exceptions import InvalidSignature
        from events.serializer import canonicalize_json
        from domain.types import EventType

        if not isinstance(params, dict):
            return False, "Malformed RPC parameters: must be a JSON object."

        proof = params.get("commit_proof")
        if hasattr(proof, "to_dict"):
            proof = proof.to_dict()
            params["commit_proof"] = proof
        if not proof or not isinstance(proof, dict):
            return False, "Missing required 'commit_proof' object in RPC parameters. Single canonical schema D2CommitProofV1 required."

        # Strict Schema Validation: Allowed and Required Fields for D2CommitProofV1
        required_fields = [
            "proof_version",
            "deployment_id",
            "installation_id",
            "manifest_id",
            "manifest_version",
            "manifest_digest",
            "event_type",
            "event_id",
            "sequence_number",
            "parent_digest",
            "event_digest",
            "head_digest",
            "root_fingerprint",
            "installed_at",
            "status",
            "signature",
        ]
        for field in required_fields:
            if field not in proof or proof[field] is None:
                return False, f"D2CommitProofV1 schema violation: missing required field '{field}'."

        allowed_fields = set(required_fields)
        extra_fields = set(proof.keys()) - allowed_fields
        if extra_fields:
            return False, f"D2CommitProofV1 schema violation: unexpected extraneous fields {sorted(list(extra_fields))}."

        if proof["proof_version"] != "D2CommitProofV1":
            return False, f"Unsupported proof_version '{proof['proof_version']}': expected 'D2CommitProofV1'."

        if proof["status"] != "SEALED":
            return False, f"Invalid proof status '{proof['status']}': expected 'SEALED'."

        if proof["event_type"] != EventType.AUTHORITY_MANIFEST_COMMITTED.value:
            return False, f"Invalid proof event_type '{proof['event_type']}': expected '{EventType.AUTHORITY_MANIFEST_COMMITTED.value}'."

        if proof["deployment_id"] != self.deployment_id:
            return False, f"Deployment ID mismatch: proof is for deployment '{proof['deployment_id']}', but broker is for '{self.deployment_id}'."

        # Signature Block Validation
        root_sig = proof["signature"]
        if not isinstance(root_sig, dict):
            return False, "Missing or invalid signature block in D2CommitProofV1."

        sig_req_fields = ["algorithm", "signer_identity", "public_key_fingerprint", "payload_digest", "signature_hex", "timestamp"]
        for f_name in sig_req_fields:
            if f_name not in root_sig:
                return False, f"D2CommitProofV1 signature block missing required field '{f_name}'."

        expected_fp = hashlib.sha256(self._root_public_key.public_bytes_raw()).hexdigest()
        if proof["root_fingerprint"] != expected_fp:
            return False, f"Root fingerprint mismatch: expected '{expected_fp}', got '{proof['root_fingerprint']}'."

        if root_sig.get("public_key_fingerprint") != expected_fp:
            return False, f"Signature public_key_fingerprint mismatch: expected '{expected_fp}', got '{root_sig.get('public_key_fingerprint')}'."

        if root_sig.get("algorithm") != "ED25519":
            return False, f"Invalid signature algorithm: expected ED25519, got '{root_sig.get('algorithm')}'."

        sig_hex = root_sig.get("signature_hex", "")
        if not sig_hex or len(sig_hex) != 128:
            return False, "Missing or malformed signature_hex in signature block (must be 128 hex chars)."

        # Canonical Preimage Construction & Digest Verification
        preimage_dict = {
            "proof_version": "D2CommitProofV1",
            "deployment_id": str(proof["deployment_id"]),
            "installation_id": str(proof["installation_id"]),
            "manifest_id": str(proof["manifest_id"]),
            "manifest_version": int(proof["manifest_version"]),
            "manifest_digest": str(proof["manifest_digest"]),
            "event_type": str(proof["event_type"]),
            "event_id": str(proof["event_id"]),
            "sequence_number": int(proof["sequence_number"]),
            "parent_digest": str(proof["parent_digest"]),
            "event_digest": str(proof["event_digest"]),
            "head_digest": str(proof["head_digest"]),
            "root_fingerprint": str(expected_fp),
            "installed_at": str(proof["installed_at"]),
            "status": "SEALED",
        }
        preimage_bytes = canonicalize_json(preimage_dict)
        calc_digest = hashlib.sha256(preimage_bytes).hexdigest()
        if root_sig.get("payload_digest") != calc_digest:
            return False, f"Payload digest substitution detected: signature payload_digest '{root_sig.get('payload_digest')}' does not match canonical preimage digest '{calc_digest}'."

        try:
            self._root_public_key.verify(bytes.fromhex(sig_hex), preimage_bytes)
        except InvalidSignature:
            return False, "Ed25519 signature verification failed against broker canonical root authority key."
        except Exception as e:
            return False, f"Cryptographic verification error: {e}"

        # Independent Authoritative D2 Event Store Inspection & Binding
        if not os.path.exists(self.d2_store_path) or os.path.getsize(self.d2_store_path) == 0:
            return False, f"Canonical D2 event store missing or empty at '{self.d2_store_path}'; commit rejected (non-existent D2 commit)."

        from events.store import FileAppendEventStore
        try:
            event_store = FileAppendEventStore(self.d2_store_path)
            events = event_store.get_events()
        except Exception as e:
            return False, f"Failed to read canonical D2 event store: {e}"

        if not events:
            return False, f"No committed events found in canonical D2 event store at '{self.d2_store_path}'."

        latest_event = events[-1]
        proof_seq = int(proof["sequence_number"])

        if proof_seq != latest_event.sequence_number:
            return False, f"Stale or superseded D2 commit: proof sequence {proof_seq} does not match current D2 head sequence {latest_event.sequence_number}."

        matching_events = [e for e in events if e.sequence_number == proof_seq]
        if not matching_events:
            return False, f"Commit event with sequence {proof_seq} does not exist in D2 event store."
        target_event = matching_events[0]

        # Exact Authority Event Type Verification (E149, E150)
        if target_event.event_type != EventType.AUTHORITY_MANIFEST_COMMITTED:
            return False, f"Invalid D2 event type: expected '{EventType.AUTHORITY_MANIFEST_COMMITTED.value}', got '{target_event.event_type.value}' (impersonation rejected)."

        if target_event.event_id != str(proof["event_id"]):
            return False, f"Event ID mismatch in D2 commit proof: expected '{target_event.event_id}', got '{proof['event_id']}'."

        if target_event.parent_digest != str(proof["parent_digest"]):
            return False, f"Parent digest mismatch in D2 commit proof: expected '{target_event.parent_digest}', got '{proof['parent_digest']}'."

        if target_event.digest != str(proof["event_digest"]):
            return False, f"Event digest mismatch in D2 commit proof: expected '{target_event.digest}', got '{proof['event_digest']}'."

        if latest_event.digest != str(proof["head_digest"]):
            return False, f"Head digest mismatch in D2 commit proof: expected '{latest_event.digest}', got '{proof['head_digest']}'."

        # Exact Manifest Payload Verification
        evt_payload = target_event.payload
        if evt_payload.get("manifest_id") != str(proof["manifest_id"]):
            return False, f"Manifest ID mismatch between D2 event payload '{evt_payload.get('manifest_id')}' and commit proof '{proof['manifest_id']}'."
        if evt_payload.get("manifest_version") != int(proof["manifest_version"]):
            return False, f"Manifest version mismatch between D2 event payload '{evt_payload.get('manifest_version')}' and commit proof '{proof['manifest_version']}'."
        if evt_payload.get("payload_digest") != str(proof["manifest_digest"]):
            return False, f"Manifest digest mismatch: D2 event payload digest '{evt_payload.get('payload_digest')}' does not match proof manifest digest '{proof['manifest_digest']}'."

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

                from file_lock import FileLock
                d2_lock_path = self.d2_store_path + ".lock"
                try:
                    with FileLock(d2_lock_path, timeout=10.0):
                        # Atomic D2 authority admission transaction
                        valid, err = self._verify_d2_commit_proof(params)
                        if not valid:
                            return {"success": False, "error": f"D2 commit validation failed: {err}"}

                        proof = params["commit_proof"]
                        self.status = DeploymentStatus.PROVISIONED
                        self.current_installation = {
                            "installation_id": proof["installation_id"],
                            "manifest_id": proof["manifest_id"],
                            "manifest_version": proof["manifest_version"],
                            "payload_digest": proof["manifest_digest"],
                            "root_fingerprint": proof["root_fingerprint"],
                        }
                        self._persist_state()
                        return {"success": True, "status": self.status.value}
                except Exception as e:
                    return {"success": False, "error": f"D2 admission transaction error: {e}"}

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

                from file_lock import FileLock
                d2_lock_path = self.d2_store_path + ".lock"
                try:
                    with FileLock(d2_lock_path, timeout=10.0):
                        # Atomic D2 authority admission transaction
                        valid, err = self._verify_d2_commit_proof(params)
                        if not valid:
                            return {"success": False, "error": f"D2 recovery commit validation failed: {err}"}

                        proof = params["commit_proof"]
                        self.status = DeploymentStatus.PROVISIONED
                        self.current_installation = {
                            "installation_id": proof["installation_id"],
                            "manifest_id": proof["manifest_id"],
                            "manifest_version": proof["manifest_version"],
                            "payload_digest": proof["manifest_digest"],
                            "root_fingerprint": proof["root_fingerprint"],
                        }
                        self._persist_state()
                        return {"success": True, "status": self.status.value}
                except Exception as e:
                    return {"success": False, "error": f"D2 recovery admission transaction error: {e}"}

            else:
                return {"success": False, "error": f"Unknown RPC method: {method}"}
