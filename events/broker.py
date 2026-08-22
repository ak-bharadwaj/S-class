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


class TrustedDeploymentBootstrap:
    """Trusted Deployment Bootstrap Boundary.
    Executes exclusively at installation / bootstrap time outside normal S-Class runtime
    to establish a virgin deployment identity in the NEVER_PROVISIONED state.
    """
    @classmethod
    def bootstrap_virgin_deployment(
        cls,
        deployment_id: str,
        state_file_path: str,
        d2_store_path: Optional[str] = None,
    ) -> str:
        """Establishes a genuine first-installation deployment in NEVER_PROVISIONED state.
        Fails closed if the deployment already has existing state or D2 history.
        """
        state_file_path = os.path.abspath(state_file_path)
        if os.path.exists(state_file_path) and os.path.getsize(state_file_path) > 0:
            raise RuntimeError(
                f"Trusted deployment bootstrap rejected: state file already exists at '{state_file_path}'."
            )

        if d2_store_path is not None:
            canonical_d2 = os.path.abspath(d2_store_path)
        else:
            from events.store import get_canonical_d2_event_store_path
            canonical_d2 = get_canonical_d2_event_store_path()

        if os.path.exists(canonical_d2) and os.path.getsize(canonical_d2) > 0:
            raise RuntimeError(
                f"Trusted deployment bootstrap rejected: D2 store already contains history at '{canonical_d2}'. "
                "Cannot bootstrap as NEVER_PROVISIONED."
            )

        state_dir = os.path.dirname(state_file_path)
        os.makedirs(state_dir, mode=0o700, exist_ok=True)
        if hasattr(os, "chmod"):
            try:
                os.chmod(state_dir, 0o700)
            except OSError:
                pass

        payload = {
            "deployment_id": deployment_id,
            "status": DeploymentStatus.NEVER_PROVISIONED.value,
            "canonical_d2_store_path": canonical_d2,
            "consumed_authorizations": [],
            "current_installation": None,
            "pending_provisioning": None,
            "active_initial_authorization": None,
        }
        seal = hashlib.sha256(canonicalize_json(payload)).hexdigest()
        wrapped = {
            "payload": payload,
            "integrity_seal": seal,
            "bootstrap_provenance": "TRUSTED_DEPLOYMENT_BOOTSTRAP",
        }

        with open(state_file_path, "w", encoding="utf-8") as f:
            json.dump(wrapped, f, indent=2)

        return state_file_path


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
        initial_status: DeploymentStatus = DeploymentStatus.CATASTROPHIC_LOSS,
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
        if initial_status != DeploymentStatus.CATASTROPHIC_LOSS:
            if os.environ.get("SCLASS_TEST_MODE") != "1" and not os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("SCLASS_TEST_FIXTURE_ACTIVE") != "1":
                raise RuntimeError(
                    "Production TrustedDeploymentAuthorityBroker cannot accept caller-selected initial_status; "
                    "authority state is strictly managed by canonical broker lifecycle."
                )
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
            if not os.path.exists(self.state_file_path) or os.path.getsize(self.state_file_path) == 0:
                if os.path.exists(self.d2_store_path) and os.path.getsize(self.d2_store_path) > 0:
                    # Missing broker state on established deployment with D2 history -> AUTHORITY_UNAVAILABLE
                    self.status = DeploymentStatus.AUTHORITY_UNAVAILABLE
                    self.consumed_authorizations = set()
                    self.current_installation = None
                    self.pending_provisioning = None
                    self.active_initial_authorization = None
                    self._persist_state()
                    return

                # Option B: Complete local authority loss (broker state absent + D2 store absent) -> CATASTROPHIC_LOSS
                self.status = default_status
                self.consumed_authorizations = set()
                self.current_installation = None
                self.pending_provisioning = None
                self.active_initial_authorization = None
                self._persist_state()
                return

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
            persisted_status = DeploymentStatus(payload.get("status", default_status.value))

            # Anti-fabrication check: D2 store with events can never have NEVER_PROVISIONED or UNPROVISIONED status
            if (
                persisted_status in (DeploymentStatus.NEVER_PROVISIONED, DeploymentStatus.UNPROVISIONED)
                and os.path.exists(self.d2_store_path)
                and os.path.getsize(self.d2_store_path) > 0
            ):
                self.status = DeploymentStatus.AUTHORITY_UNAVAILABLE
                self.consumed_authorizations = set(payload.get("consumed_authorizations", []))
                self.current_installation = None
                self.pending_provisioning = None
                self.active_initial_authorization = None
                self._persist_state()
                raise RuntimeError(
                    "Broker state tampering or fabricated NEVER_PROVISIONED/UNPROVISIONED state detected on established deployment with D2 history. "
                    "Failing closed into AUTHORITY_UNAVAILABLE."
                )


            self.status = persisted_status
            self.consumed_authorizations = set(payload.get("consumed_authorizations", []))
            self.current_installation = payload.get("current_installation")
            self.pending_provisioning = payload.get("pending_provisioning")
            self.active_initial_authorization = payload.get("active_initial_authorization")

            from domain.types import EventType
            from events.store import FileAppendEventStore

            # Recovery Matrix: PENDING states (PROVISIONING_PENDING, BROKER_COMMIT_PENDING, RECOVERY_PENDING)
            if self.status in (DeploymentStatus.PROVISIONING_PENDING, DeploymentStatus.BROKER_COMMIT_PENDING, DeploymentStatus.RECOVERY_PENDING):
                pending = self.pending_provisioning or self.current_installation
                if not pending or not isinstance(pending, dict):
                    # Non-authoritative deterministic recovery
                    if self.status == DeploymentStatus.RECOVERY_PENDING:
                        self.status = DeploymentStatus.RECOVERY_AUTHORIZED
                    else:
                        self.status = DeploymentStatus.PROVISIONING_AUTHORIZED
                    self.pending_provisioning = None
                    self.current_installation = None
                    self._persist_state()
                    return

                if not os.path.exists(self.d2_store_path) or os.path.getsize(self.d2_store_path) == 0:
                    # PENDING + no matching D2 commit -> non-authoritative recovery
                    if self.status == DeploymentStatus.RECOVERY_PENDING:
                        self.status = DeploymentStatus.RECOVERY_AUTHORIZED
                    else:
                        self.status = DeploymentStatus.PROVISIONING_AUTHORIZED
                    self.pending_provisioning = None
                    self.current_installation = None
                    self._persist_state()
                    return

                try:
                    event_store = FileAppendEventStore(self.d2_store_path)
                    events = event_store.get_events()
                except Exception as e:
                    self.status = DeploymentStatus.AUTHORITY_UNAVAILABLE
                    raise RuntimeError(f"Cannot recover from pending state: D2 store unreadable or corrupt: {e}. Failing closed.")

                # Look for exact matching D2 commit
                m_id = str(pending.get("manifest_id", ""))
                m_ver = int(pending.get("manifest_version", 1))
                m_dig = str(pending.get("manifest_digest", pending.get("payload_digest", "")))
                target_seq = pending.get("sequence_number")
                target_eid = pending.get("event_id")

                matching_events = [
                    e for e in events
                    if e.event_type == EventType.AUTHORITY_MANIFEST_COMMITTED
                    and str(e.payload.get("manifest_id", "")) == m_id
                    and int(e.payload.get("manifest_version", 1)) == m_ver
                    and str(e.payload.get("payload_digest", "")) == m_dig
                    and (target_seq is None or e.sequence_number == target_seq)
                    and (target_eid is None or e.event_id == target_eid)
                ]

                if matching_events:
                    # PENDING + exact matching D2 commit -> PROVISIONED
                    target_event = matching_events[-1]
                    self.status = DeploymentStatus.PROVISIONED
                    self.current_installation = {
                        "installation_id": str(pending.get("installation_id", "")),
                        "manifest_id": str(target_event.payload.get("manifest_id")),
                        "manifest_version": int(target_event.payload.get("manifest_version", 1)),
                        "payload_digest": str(target_event.payload.get("payload_digest")),
                        "event_id": str(target_event.event_id),
                        "sequence_number": int(target_event.sequence_number),
                        "event_digest": str(target_event.digest),
                        "head_digest": str(target_event.digest),
                        "root_fingerprint": str(pending.get("root_fingerprint", "")),
                    }
                    self.pending_provisioning = None
                    self._persist_state()
                    return
                else:
                    # PENDING + no matching D2 commit -> non-authoritative recovery
                    if self.status == DeploymentStatus.RECOVERY_PENDING:
                        self.status = DeploymentStatus.RECOVERY_AUTHORIZED
                    else:
                        self.status = DeploymentStatus.PROVISIONING_AUTHORIZED
                    self.pending_provisioning = None
                    self.current_installation = None
                    self._persist_state()
                    return

            elif self.status == DeploymentStatus.PROVISIONED and self.current_installation:
                if os.path.exists(self.d2_store_path) and os.path.getsize(self.d2_store_path) > 0:
                    try:
                        event_store = FileAppendEventStore(self.d2_store_path)
                        events = event_store.get_events()
                        target_seq = self.current_installation.get("sequence_number")
                        matching = [e for e in events if e.sequence_number == target_seq] if target_seq is not None else []
                        if matching:
                            target_event = matching[0]
                            if (
                                target_event.event_id != str(self.current_installation.get("event_id", target_event.event_id))
                                or target_event.digest != str(self.current_installation.get("event_digest", target_event.digest))
                            ):
                                self.status = DeploymentStatus.AUTHORITY_UNAVAILABLE
                                raise RuntimeError(f"Accepted D2 authority event {target_seq} was altered or corrupted on disk. Failing closed.")
                        elif target_seq is not None:
                            self.status = DeploymentStatus.AUTHORITY_UNAVAILABLE
                            raise RuntimeError(f"Accepted D2 authority event sequence {target_seq} missing from D2 store. Failing closed.")
                    except RuntimeError:
                        raise
                    except Exception as e:
                        self.status = DeploymentStatus.AUTHORITY_UNAVAILABLE
                        raise RuntimeError(f"Authoritative D2 store corrupted on restart: {e}. Failing closed.")
                else:
                    self.status = DeploymentStatus.AUTHORITY_UNAVAILABLE
                    raise RuntimeError(f"Authoritative D2 store missing at '{self.d2_store_path}' on restart. Failing closed.")

    def _persist_state(self) -> None:
        with self._lock:
            os.makedirs(self.state_dir, mode=0o700, exist_ok=True)
            state_payload = {
                "deployment_id": self.deployment_id,
                "canonical_d2_store_path": self.d2_store_path,
                "status": self.status.value,
                "consumed_authorizations": sorted(list(self.consumed_authorizations)),
                "current_installation": self.current_installation,
                "pending_provisioning": getattr(self, "pending_provisioning", None),
                "active_initial_authorization": getattr(self, "active_initial_authorization", None),
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
                if self.status not in (DeploymentStatus.NEVER_PROVISIONED, DeploymentStatus.UNPROVISIONED):
                    return {"success": False, "error": f"Cannot authorize initial provisioning from state '{self.status.value}' (NEVER_PROVISIONED required)."}

                if "root_public_key" in params and params["root_public_key"] is not None:
                    return {"success": False, "error": "Caller-supplied root public key is rejected; broker uses canonical authority root."}

                auth_data = params.get("initial_authorization", params.get("authorization_data"))
                if not auth_data or not isinstance(auth_data, dict):
                    return {"success": False, "error": "Missing or invalid initial provisioning authorization; authenticated S-Class client cannot self-authorize."}

                auth_dep_id = auth_data.get("deployment_id")
                if auth_dep_id != self.deployment_id:
                    return {"success": False, "error": f"Initial provisioning authorization deployment mismatch: expected '{self.deployment_id}', got '{auth_dep_id}'."}

                auth_id = auth_data.get("authorization_id")
                if not auth_id:
                    return {"success": False, "error": "Missing authorization_id in initial provisioning authorization."}

                if auth_id in self.consumed_authorizations:
                    return {"success": False, "error": f"Initial provisioning authorization '{auth_id}' has already been consumed."}

                purpose = auth_data.get("purpose")
                if purpose != "INITIAL_PROVISIONING":
                    return {"success": False, "error": f"Invalid authorization purpose '{purpose}': 'INITIAL_PROVISIONING' required."}

                target_manifest_id = auth_data.get("target_manifest_id")
                if not target_manifest_id:
                    return {"success": False, "error": "Missing target_manifest_id in initial provisioning authorization."}

                target_manifest_digest = auth_data.get("target_manifest_digest")
                if not target_manifest_digest:
                    return {"success": False, "error": "Missing target_manifest_digest in initial provisioning authorization."}

                target_manifest_version = int(auth_data.get("target_manifest_version", 1))

                expected_fp = hashlib.sha256(self._root_public_key.public_bytes_raw()).hexdigest()
                root_fp = auth_data.get("root_fingerprint")
                if root_fp != expected_fp:
                    return {"success": False, "error": f"Initial provisioning authorization root fingerprint mismatch: expected '{expected_fp}', got '{root_fp}'."}

                sig_obj = auth_data.get("signature", {})
                sig_hex = sig_obj.get("signature_hex")
                if not sig_hex:
                    return {"success": False, "error": "Missing signature in initial provisioning authorization."}

                preimage_dict = {
                    "authorization_id": auth_id,
                    "deployment_id": auth_dep_id,
                    "target_manifest_id": target_manifest_id,
                    "target_manifest_version": target_manifest_version,
                    "target_manifest_digest": target_manifest_digest,
                    "authorized_at": auth_data.get("authorized_at"),
                    "purpose": purpose,
                    "root_fingerprint": root_fp,
                }
                preimage_bytes = canonicalize_json(preimage_dict)
                try:
                    self._root_public_key.verify(bytes.fromhex(sig_hex), preimage_bytes)
                except InvalidSignature:
                    return {"success": False, "error": "Invalid initial provisioning authorization signature against canonical broker root."}
                except Exception as e:
                    return {"success": False, "error": f"Signature verification error: {e}"}

                self.consumed_authorizations.add(auth_id)
                self.active_initial_authorization = dict(preimage_dict)
                self.status = DeploymentStatus.PROVISIONING_AUTHORIZED
                self._persist_state()
                return {"success": True, "status": self.status.value, "authorization": auth_data}

            elif method == "register_pending_provisioning":
                if self.status not in (DeploymentStatus.PROVISIONING_AUTHORIZED, DeploymentStatus.PROVISIONING_PENDING):
                    return {"success": False, "error": f"Cannot register pending provisioning from state '{self.status.value}' (PROVISIONING_AUTHORIZED required)."}

                params_dict = params or {}
                m_digest = str(params_dict.get("manifest_digest", params_dict.get("payload_digest", "")))
                if not m_digest:
                    return {"success": False, "error": "Missing manifest_digest/payload_digest for pending provisioning."}

                # Bind pending intent to active initial authorization if coming from PROVISIONING_AUTHORIZED
                if self.status == DeploymentStatus.PROVISIONING_AUTHORIZED and getattr(self, "active_initial_authorization", None) is not None:
                    auth = self.active_initial_authorization
                    if (
                        str(params_dict.get("manifest_id", "")) != str(auth.get("target_manifest_id", ""))
                        or int(params_dict.get("manifest_version", 1)) != int(auth.get("target_manifest_version", 1))
                        or m_digest != str(auth.get("target_manifest_digest", ""))
                        or (params_dict.get("root_fingerprint") and str(params_dict["root_fingerprint"]) != str(auth.get("root_fingerprint", "")))
                    ):
                        return {"success": False, "error": "Pending provisioning intent does not match authorized initial provisioning parameters."}

                if self.status == DeploymentStatus.PROVISIONING_PENDING and self.pending_provisioning is not None:
                    p = self.pending_provisioning
                    if (
                        str(params_dict.get("manifest_id", "")) != str(p.get("manifest_id", ""))
                        or int(params_dict.get("manifest_version", 1)) != int(p.get("manifest_version", 1))
                        or m_digest != str(p.get("manifest_digest", ""))
                        or (params_dict.get("root_fingerprint") and str(params_dict["root_fingerprint"]) != str(p.get("root_fingerprint", "")))
                        or (params_dict.get("installation_id") and str(params_dict["installation_id"]) != str(p.get("installation_id", "")))
                        or (params_dict.get("transaction_id") and str(params_dict["transaction_id"]) != str(p.get("transaction_id", "")))
                    ):
                        return {"success": False, "error": "Pending provisioning intent is immutable; differing second intent rejected."}
                    return {"success": True, "status": self.status.value, "pending_provisioning": self.pending_provisioning}

                self.status = DeploymentStatus.PROVISIONING_PENDING
                self.pending_provisioning = {
                    "deployment_id": self.deployment_id,
                    "installation_id": str(params_dict.get("installation_id", "")),
                    "manifest_id": str(params_dict.get("manifest_id", "")),
                    "manifest_version": int(params_dict.get("manifest_version", 1)),
                    "manifest_digest": m_digest,
                    "root_fingerprint": str(params_dict.get("root_fingerprint", "")),
                    "transaction_id": str(params_dict.get("transaction_id", params_dict.get("installation_id", ""))),
                }
                self._persist_state()
                return {"success": True, "status": self.status.value, "pending_provisioning": self.pending_provisioning}

            elif method == "record_provisioned":
                if self.status != DeploymentStatus.PROVISIONING_PENDING:
                    return {"success": False, "error": f"Cannot transition to PROVISIONED from state '{self.status.value}': PROVISIONING_PENDING required."}

                if self.pending_provisioning is None:
                    return {"success": False, "error": "Cannot transition to PROVISIONED: missing pending provisioning intent."}

                from file_lock import FileLock
                d2_lock_path = self.d2_store_path + ".lock"
                try:
                    with FileLock(d2_lock_path, timeout=10.0):
                        # Atomic D2 authority admission transaction
                        valid, err = self._verify_d2_commit_proof(params)
                        if not valid:
                            return {"success": False, "error": f"D2 commit validation failed: {err}"}

                        proof = params["commit_proof"]

                        p = self.pending_provisioning
                        if (
                            str(proof["manifest_id"]) != str(p.get("manifest_id", ""))
                            or int(proof["manifest_version"]) != int(p.get("manifest_version", 1))
                            or str(proof["manifest_digest"]) != str(p.get("manifest_digest", ""))
                            or (p.get("root_fingerprint") and str(proof["root_fingerprint"]) != str(p["root_fingerprint"]))
                            or (p.get("installation_id") and str(proof["installation_id"]) != str(p["installation_id"]))
                            or (p.get("deployment_id") and str(proof["deployment_id"]) != str(p["deployment_id"]))
                        ):
                            return {"success": False, "error": "Commit proof does not match pending provisioning intent."}

                        # Finalize to PROVISIONED
                        self.status = DeploymentStatus.PROVISIONED
                        self.current_installation = {
                            "installation_id": str(proof["installation_id"]),
                            "manifest_id": str(proof["manifest_id"]),
                            "manifest_version": int(proof["manifest_version"]),
                            "payload_digest": str(proof["manifest_digest"]),
                            "event_id": str(proof["event_id"]),
                            "sequence_number": int(proof["sequence_number"]),
                            "event_digest": str(proof["event_digest"]),
                            "head_digest": str(proof["head_digest"]),
                            "root_fingerprint": str(proof["root_fingerprint"]),
                        }
                        self.pending_provisioning = None
                        self._persist_state()
                        return {"success": True, "status": self.status.value}
                except Exception as e:
                    return {"success": False, "error": f"D2 admission transaction error: {e}"}

            elif method == "notify_local_state_loss":
                self.status = DeploymentStatus.RECOVERY_REQUIRED
                self._persist_state()
                return {"success": True, "status": self.status.value}

            elif method == "authorize_reprovisioning":
                auth_data = params.get("reprovisioning_authorization", {})
                auth_id = auth_data.get("authorization_id")
                if auth_id in self.consumed_authorizations:
                    return {"success": False, "error": f"Reprovisioning authorization '{auth_id}' has already been consumed."}

                if self.status not in (DeploymentStatus.RECOVERY_REQUIRED, DeploymentStatus.AUTHORITY_UNAVAILABLE, DeploymentStatus.CATASTROPHIC_LOSS):
                    return {"success": False, "error": f"Cannot authorize reprovisioning from state '{self.status.value}' (RECOVERY_REQUIRED, AUTHORITY_UNAVAILABLE, or CATASTROPHIC_LOSS required)."}

                if "root_public_key" in params and params["root_public_key"] is not None:
                    return {"success": False, "error": "Caller-supplied root public key is rejected; broker uses canonical authority root."}

                auth_dep_id = auth_data.get("deployment_id")
                if auth_dep_id != self.deployment_id:
                    return {"success": False, "error": f"Reprovisioning authorization deployment mismatch: expected '{self.deployment_id}', got '{auth_dep_id}'."}

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

            elif method == "register_pending_reprovisioning":
                if self.status not in (DeploymentStatus.RECOVERY_AUTHORIZED, DeploymentStatus.RECOVERY_PENDING):
                    return {"success": False, "error": f"Cannot register pending reprovisioning from state '{self.status.value}' (RECOVERY_AUTHORIZED required)."}

                params_dict = params or {}
                m_digest = str(params_dict.get("manifest_digest", params_dict.get("payload_digest", "")))
                if not m_digest:
                    return {"success": False, "error": "Missing manifest_digest/payload_digest for pending reprovisioning."}

                if self.status == DeploymentStatus.RECOVERY_PENDING and self.pending_provisioning is not None:
                    p = self.pending_provisioning
                    if (
                        str(params_dict.get("manifest_id", "")) != str(p.get("manifest_id", ""))
                        or int(params_dict.get("manifest_version", 1)) != int(p.get("manifest_version", 1))
                        or m_digest != str(p.get("manifest_digest", ""))
                        or (params_dict.get("root_fingerprint") and str(params_dict["root_fingerprint"]) != str(p.get("root_fingerprint", "")))
                        or (params_dict.get("installation_id") and str(params_dict["installation_id"]) != str(p.get("installation_id", "")))
                        or (params_dict.get("transaction_id") and str(params_dict["transaction_id"]) != str(p.get("transaction_id", "")))
                    ):
                        return {"success": False, "error": "Pending reprovisioning intent is immutable; differing second intent rejected."}
                    return {"success": True, "status": self.status.value, "pending_provisioning": self.pending_provisioning}

                self.status = DeploymentStatus.RECOVERY_PENDING
                self.pending_provisioning = {
                    "deployment_id": self.deployment_id,
                    "installation_id": str(params_dict.get("installation_id", "")),
                    "manifest_id": str(params_dict.get("manifest_id", "")),
                    "manifest_version": int(params_dict.get("manifest_version", 1)),
                    "manifest_digest": m_digest,
                    "root_fingerprint": str(params_dict.get("root_fingerprint", "")),
                    "transaction_id": str(params_dict.get("transaction_id", params_dict.get("installation_id", ""))),
                }
                self._persist_state()
                return {"success": True, "status": self.status.value, "pending_provisioning": self.pending_provisioning}

            elif method == "record_reprovisioned":
                if self.status != DeploymentStatus.RECOVERY_PENDING:
                    return {"success": False, "error": f"Cannot transition to PROVISIONED from state '{self.status.value}': RECOVERY_PENDING required."}

                if self.pending_provisioning is None:
                    return {"success": False, "error": "Cannot transition to PROVISIONED: missing pending reprovisioning intent."}

                from file_lock import FileLock
                d2_lock_path = self.d2_store_path + ".lock"
                try:
                    with FileLock(d2_lock_path, timeout=10.0):
                        # Atomic D2 authority admission transaction
                        valid, err = self._verify_d2_commit_proof(params)
                        if not valid:
                            return {"success": False, "error": f"D2 recovery commit validation failed: {err}"}

                        proof = params["commit_proof"]

                        p = self.pending_provisioning
                        if (
                            str(proof["manifest_id"]) != str(p.get("manifest_id", ""))
                            or int(proof["manifest_version"]) != int(p.get("manifest_version", 1))
                            or str(proof["manifest_digest"]) != str(p.get("manifest_digest", ""))
                            or (p.get("root_fingerprint") and str(proof["root_fingerprint"]) != str(p["root_fingerprint"]))
                            or (p.get("installation_id") and str(proof["installation_id"]) != str(p["installation_id"]))
                            or (p.get("deployment_id") and str(proof["deployment_id"]) != str(p["deployment_id"]))
                        ):
                            return {"success": False, "error": "Commit proof does not match pending reprovisioning intent."}

                        # Finalize to PROVISIONED
                        self.status = DeploymentStatus.PROVISIONED
                        self.current_installation = {
                            "installation_id": str(proof["installation_id"]),
                            "manifest_id": str(proof["manifest_id"]),
                            "manifest_version": int(proof["manifest_version"]),
                            "payload_digest": str(proof["manifest_digest"]),
                            "event_id": str(proof["event_id"]),
                            "sequence_number": int(proof["sequence_number"]),
                            "event_digest": str(proof["event_digest"]),
                            "head_digest": str(proof["head_digest"]),
                            "root_fingerprint": str(proof["root_fingerprint"]),
                        }
                        self.pending_provisioning = None
                        self._persist_state()
                        return {"success": True, "status": self.status.value}
                except Exception as e:
                    return {"success": False, "error": f"D2 recovery admission transaction error: {e}"}

            else:
                return {"success": False, "error": f"Unknown RPC method: {method}"}
