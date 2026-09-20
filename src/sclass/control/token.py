"""
S-Class EOS V11.2 - D5 Cryptographic Execution Token, Admission, ActionBinding & ExecutionContext (Â§8.1, Â§8.3).
Mandatory ExecutionEnvelope model for D5 -> D6 boundary.
Reuses D2 durable storage for atomic single-use nonce reservation and lifecycle state tracking.
Domain Separators:
- SCLASS_ACTION_BINDING_V1:
- SCLASS_EXECUTION_CONTEXT_V1:
- SCLASS_EXECUTION_TOKEN_V1:
- SCLASS_EXECUTION_ADMISSION_V1:
Controller holds the ONLY issuance path.
"""

from __future__ import annotations
import os
import re
import uuid
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
import copyreg
from types import MappingProxyType
from typing import Mapping, Optional, Sequence, Tuple, Any, Set
import json

AsymmetricAuthoritySignature = str
HEX_40_PATTERN = r"^[0-9a-fA-F]{40}$"
HEX_64_PATTERN = r"^[0-9a-fA-F]{64}$"

def _reconstruct_mapping_proxy(d: dict) -> MappingProxyType:
    return MappingProxyType(d)

def _pickle_mappingproxy(mp: MappingProxyType) -> Tuple[Any, Tuple[dict]]:
    return (_reconstruct_mapping_proxy, (dict(mp),))

copyreg.pickle(MappingProxyType, _pickle_mappingproxy)

def _validate_pattern(val: str, pattern: Any, name: str) -> None:
    if not isinstance(val, str):
        raise ValueError(f"Invalid {name}: must be a string.")
    if isinstance(pattern, str):
        if not re.match(pattern, val):
            raise ValueError(f"Invalid {name}: '{val}' does not match required pattern '{pattern}'.")
    elif hasattr(pattern, "match"):
        if not pattern.match(val):
            raise ValueError(f"Invalid {name}: '{val}' does not match required pattern.")
    else:
        raise ValueError(f"Invalid pattern type: {type(pattern)}")

def _validate_iso8601(val: str, name: str) -> None:
    if not isinstance(val, str):
        raise ValueError(f"Invalid {name}: must be an ISO 8601 string.")
    try:
        if val.endswith("Z"):
            datetime.fromisoformat(val[:-1] + "+00:00")
        else:
            datetime.fromisoformat(val)
    except Exception as e:
        raise ValueError(f"Invalid {name}: '{val}' is not a valid ISO 8601 string.") from e

def _freeze_nested(val: Any) -> Any:
    """Recursively converts dicts to MappingProxyType and sequences to tuples."""
    if isinstance(val, (dict, Mapping)):
        return MappingProxyType({k: _freeze_nested(v) for k, v in val.items()})
    elif isinstance(val, (list, tuple, set)):
        return tuple(_freeze_nested(x) for x in val)
    return val

def canonicalize_json(x: Any) -> bytes:
    def _default(obj: Any) -> Any:
        if isinstance(obj, (dict, Mapping)):
            return dict(obj)
        if isinstance(obj, (tuple, set, list)):
            return list(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
    return json.dumps(x, sort_keys=True, default=_default).encode("utf-8")

class D2NonceStore:
    def __init__(
        self,
        workspace_dir: Optional[str] = None,
        file_path: Optional[str] = None,
    ):
        import threading
        self._local_lock = threading.Lock()
        self._process_cache: Set[str] = set()
        self._file_path: Optional[str] = None
        if file_path:
            self._file_path = os.path.abspath(file_path)
        elif workspace_dir:
            from sclass.storage.paths import WorkspacePaths
            paths = WorkspacePaths(workspace_dir)
            paths.ensure_directories()
            self._file_path = os.path.join(paths.trust_dir, "d2_nonces.jsonl")

    def reserve_nonce(self, nonce: str) -> bool:
        """Atomically reserves a single-use nonce. Returns True on success, False if already consumed."""
        if not nonce or not isinstance(nonce, str):
            raise ValueError("Nonce must be a non-empty string.")
        with self._local_lock:
            if self._file_path:
                from sclass.core.errors import SecurityViolationError
                os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
                try:
                    if os.path.exists(self._file_path):
                        with open(self._file_path, "r", encoding="utf-8") as f:
                            for line_num, line in enumerate(f, start=1):
                                line_str = line.strip()
                                if not line_str:
                                    continue
                                try:
                                    rec = json.loads(line_str)
                                    rec_nonce = rec.get("nonce") or rec.get("envelope_id")
                                    if not rec_nonce or not isinstance(rec_nonce, str):
                                        raise SecurityViolationError(f"Corrupt nonce record at line {line_num}: missing 'nonce'")
                                    self._process_cache.add(rec_nonce)
                                    if "nonce" in rec and isinstance(rec["nonce"], str):
                                        self._process_cache.add(rec["nonce"])
                                    if "envelope_id" in rec and isinstance(rec["envelope_id"], str):
                                        self._process_cache.add(rec["envelope_id"])
                                        self._process_cache.add(f"ADMIT:{rec['envelope_id']}")
                                except json.JSONDecodeError as err:
                                    raise SecurityViolationError(f"Corrupt JSON in nonce store at line {line_num}: {err}") from err
                    if (nonce in self._process_cache or 
                        f"ADMIT:{nonce}" in self._process_cache or 
                        (nonce.startswith("ADMIT:") and nonce[6:] in self._process_cache)):
                        return False
                    record = {
                        "nonce": nonce,
                        "envelope_id": nonce[6:] if nonce.startswith("ADMIT:") else nonce,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    line_bytes = canonicalize_json(record) + b"\n"
                    with open(self._file_path, "ab") as f:
                        f.write(line_bytes)
                        f.flush()
                        os.fsync(f.fileno())
                    self._process_cache.add(nonce)
                    if nonce.startswith("ADMIT:"):
                        self._process_cache.add(nonce[6:])
                    else:
                        self._process_cache.add(f"ADMIT:{nonce}")
                    return True
                except SecurityViolationError:
                    raise
                except Exception as e:
                    raise SecurityViolationError(f"I/O failure in nonce store: {e}") from e
            else:
                if (nonce in self._process_cache or 
                    f"ADMIT:{nonce}" in self._process_cache or 
                    (nonce.startswith("ADMIT:") and nonce[6:] in self._process_cache)):
                    return False
                self._process_cache.add(nonce)
                if nonce.startswith("ADMIT:"):
                    self._process_cache.add(nonce[6:])
                else:
                    self._process_cache.add(f"ADMIT:{nonce}")
                return True

    def is_nonce_consumed(self, nonce: str) -> bool:
        """Queries whether a nonce is already consumed."""
        if not nonce or not isinstance(nonce, str):
            return False
        with self._local_lock:
            if self._file_path and os.path.exists(self._file_path):
                from sclass.core.errors import SecurityViolationError
                try:
                    with open(self._file_path, "r", encoding="utf-8") as f:
                        for line_num, line in enumerate(f, start=1):
                            line_str = line.strip()
                            if not line_str:
                                continue
                            try:
                                rec = json.loads(line_str)
                                rec_nonce = rec.get("nonce") or rec.get("envelope_id")
                                if not rec_nonce or not isinstance(rec_nonce, str):
                                    raise SecurityViolationError(f"Corrupt nonce record at line {line_num}: missing 'nonce'")
                                self._process_cache.add(rec_nonce)
                                if "nonce" in rec and isinstance(rec["nonce"], str):
                                    self._process_cache.add(rec["nonce"])
                                if "envelope_id" in rec and isinstance(rec["envelope_id"], str):
                                    self._process_cache.add(rec["envelope_id"])
                                    self._process_cache.add(f"ADMIT:{rec['envelope_id']}")
                            except json.JSONDecodeError as err:
                                raise SecurityViolationError(f"Corrupt JSON in nonce store at line {line_num}: {err}") from err
                except SecurityViolationError:
                    raise
                except Exception as e:
                    raise SecurityViolationError(f"I/O failure reading nonce store: {e}") from e
            return (
                nonce in self._process_cache or 
                f"ADMIT:{nonce}" in self._process_cache or 
                (nonce.startswith("ADMIT:") and nonce[6:] in self._process_cache)
            )

    def clear(self) -> None:
        with self._local_lock:
            self._process_cache.clear()
            if self._file_path and os.path.exists(self._file_path):
                try:
                    os.remove(self._file_path)
                except OSError:
                    pass

class AuthoritySignerProtocol:
    def __init__(self, secret_key: Optional[bytes] = None):
        if secret_key is not None:
            self.secret_key = secret_key
        else:
            from sclass.policy.authorization_service import get_authorization_secret
            self.secret_key = get_authorization_secret()

    def sign_payload(self, canonical_bytes: bytes, verifier_identity: str, timestamp_iso: str) -> str:
        import hashlib, hmac
        return hmac.new(self.secret_key, canonical_bytes, hashlib.sha256).hexdigest()

    def verify_signature(self, canonical_bytes: bytes, signature: str) -> bool:
        import hashlib, hmac
        expected = hmac.new(self.secret_key, canonical_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)


TOKEN_ID_PREFIX = "TOK-"
SCLASS_ACTION_BINDING_DOMAIN_SEPARATOR = "SCLASS_ACTION_BINDING_V1:"
SCLASS_EXECUTION_CONTEXT_DOMAIN_SEPARATOR = "SCLASS_EXECUTION_CONTEXT_V1:"
SCLASS_EXECUTION_TOKEN_DOMAIN_SEPARATOR = "SCLASS_EXECUTION_TOKEN_V1:"
SCLASS_EXECUTION_ADMISSION_DOMAIN_SEPARATOR = "SCLASS_EXECUTION_ADMISSION_V1:"
SCLASS_SESSION_BINDING_DOMAIN_SEPARATOR = "SCLASS_SESSION_BINDING_V1:"


def compute_action_digest(
    action_type: str,
    target: str,
    purpose: str,
    parameters: Optional[Mapping[str, Any]] = None,
) -> str:
    """Computes the canonical SHA-256 action digest using domain separator SCLASS_ACTION_BINDING_V1:."""
    if not action_type:
        raise ValueError("action_type cannot be empty.")
    if not target:
        raise ValueError("target cannot be empty.")
    if not purpose:
        raise ValueError("purpose cannot be empty.")

    payload = {
        "action_type": action_type,
        "target": target,
        "purpose": purpose,
        "parameters": dict(parameters or {}),
    }
    canonical_bytes = SCLASS_ACTION_BINDING_DOMAIN_SEPARATOR.encode("utf-8") + canonicalize_json(payload)
    return hashlib.sha256(canonical_bytes).hexdigest()


@dataclass(frozen=True)
class ActionBinding:
    """Immutable exact action specification and cryptographic digest (Â§8.1)."""
    action_type: str
    target: str
    purpose: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    action_digest: str = ""

    def __post_init__(self):
        if not self.action_type:
            raise ValueError("action_type cannot be empty.")
        if not self.target:
            raise ValueError("target cannot be empty.")
        if not self.purpose:
            raise ValueError("purpose cannot be empty.")
        object.__setattr__(self, "parameters", _freeze_nested(self.parameters))

        expected_digest = compute_action_digest(
            action_type=self.action_type,
            target=self.target,
            purpose=self.purpose,
            parameters=self.parameters,
        )
        if not self.action_digest:
            object.__setattr__(self, "action_digest", expected_digest)
        elif self.action_digest != expected_digest:
            raise ValueError(f"action_digest mismatch: '{self.action_digest}' != '{expected_digest}'")
        _validate_pattern(self.action_digest, HEX_64_PATTERN, "action_digest")


def compute_context_digest(
    provider_id: str,
    sandbox_profile_id: str,
    workspace_id: str,
    resource_profile_id: str,
    capability_set: Sequence[str],
) -> tuple[str, str]:
    """Computes (capability_set_digest, context_digest) with domain separator SCLASS_EXECUTION_CONTEXT_V1:."""
    if not provider_id:
        raise ValueError("provider_id cannot be empty.")
    if not sandbox_profile_id:
        raise ValueError("sandbox_profile_id cannot be empty.")
    if not workspace_id:
        raise ValueError("workspace_id cannot be empty.")
    if not resource_profile_id:
        raise ValueError("resource_profile_id cannot be empty.")

    sorted_caps = sorted(list(capability_set))
    cap_bytes = canonicalize_json({"capabilities": sorted_caps})
    cap_digest = hashlib.sha256(cap_bytes).hexdigest()

    payload = {
        "provider_id": provider_id,
        "sandbox_profile_id": sandbox_profile_id,
        "workspace_id": workspace_id,
        "resource_profile_id": resource_profile_id,
        "capability_set_digest": cap_digest,
    }
    canonical_bytes = SCLASS_EXECUTION_CONTEXT_DOMAIN_SEPARATOR.encode("utf-8") + canonicalize_json(payload)
    ctx_digest = hashlib.sha256(canonical_bytes).hexdigest()
    return cap_digest, ctx_digest


@dataclass(frozen=True)
class ExecutionContext:
    """Immutable, authority-relevant execution environment properties (Â§8.1)."""
    provider_id: str
    sandbox_profile_id: str
    workspace_id: str
    resource_profile_id: str
    capability_set: Tuple[str, ...] = field(default_factory=tuple)
    capability_set_digest: str = ""
    context_digest: str = ""

    def __post_init__(self):
        if not self.provider_id:
            raise ValueError("provider_id cannot be empty.")
        if not self.sandbox_profile_id:
            raise ValueError("sandbox_profile_id cannot be empty.")
        if not self.workspace_id:
            raise ValueError("workspace_id cannot be empty.")
        if not self.resource_profile_id:
            raise ValueError("resource_profile_id cannot be empty.")
        object.__setattr__(self, "capability_set", tuple(sorted(self.capability_set)))

        cap_digest, expected_ctx_digest = compute_context_digest(
            provider_id=self.provider_id,
            sandbox_profile_id=self.sandbox_profile_id,
            workspace_id=self.workspace_id,
            resource_profile_id=self.resource_profile_id,
            capability_set=self.capability_set,
        )
        if not self.capability_set_digest:
            object.__setattr__(self, "capability_set_digest", cap_digest)
        elif self.capability_set_digest != cap_digest:
            raise ValueError(f"capability_set_digest mismatch: '{self.capability_set_digest}' != '{cap_digest}'")

        if not self.context_digest:
            object.__setattr__(self, "context_digest", expected_ctx_digest)
        elif self.context_digest != expected_ctx_digest:
            raise ValueError(f"context_digest mismatch: '{self.context_digest}' != '{expected_ctx_digest}'")

        _validate_pattern(self.capability_set_digest, HEX_64_PATTERN, "capability_set_digest")
        _validate_pattern(self.context_digest, HEX_64_PATTERN, "context_digest")


@dataclass(frozen=True)
class ExecutionToken:
    """Immutable single-use execution token issued exclusively by D5 Controller upon authorization."""
    token_id: str
    decision_id: str
    obligation_id: str
    proposal_id: str
    action_digest: str
    context_digest: str
    source_sha: str
    policy_version: int
    execution_nonce: str
    issued_at: str
    expires_at: str
    signature: AsymmetricAuthoritySignature
    owner_id: str = ""
    fencing_token: int = 0
    lease_epoch: int = 0
    state_version: int = 0
    state_digest: str = ""
    authority_context_digest: str = ""

    def __post_init__(self):
        if not self.token_id or not self.token_id.startswith(TOKEN_ID_PREFIX):
            raise ValueError(f"Invalid token_id: '{self.token_id}' must start with '{TOKEN_ID_PREFIX}'")
        if not self.decision_id:
            raise ValueError("decision_id cannot be empty.")
        if not self.obligation_id:
            raise ValueError("obligation_id cannot be empty.")
        if not self.proposal_id:
            raise ValueError("proposal_id cannot be empty.")
        _validate_pattern(self.action_digest, HEX_64_PATTERN, "action_digest")
        _validate_pattern(self.context_digest, HEX_64_PATTERN, "context_digest")
        _validate_pattern(self.source_sha, HEX_40_PATTERN, "source_sha")
        if not isinstance(self.policy_version, int) or self.policy_version < 1:
            raise ValueError("policy_version must be an integer >= 1.")
        if not self.execution_nonce:
            raise ValueError("execution_nonce cannot be empty.")
        _validate_iso8601(self.issued_at, "issued_at")
        _validate_iso8601(self.expires_at, "expires_at")
        if not isinstance(self.signature, AsymmetricAuthoritySignature):
            raise TypeError("signature must be an AsymmetricAuthoritySignature instance.")
        if not isinstance(self.fencing_token, int) or self.fencing_token < 0:
            raise ValueError("fencing_token must be an integer >= 0.")
        if not isinstance(self.lease_epoch, int) or self.lease_epoch < 0:
            raise ValueError("lease_epoch must be an integer >= 0.")
        if not isinstance(self.state_version, int) or self.state_version < 0:
            raise ValueError("state_version must be an integer >= 0.")
        if self.state_digest:
            _validate_pattern(self.state_digest, HEX_64_PATTERN, "state_digest")
        if self.authority_context_digest:
            _validate_pattern(self.authority_context_digest, HEX_64_PATTERN, "authority_context_digest")


@dataclass(frozen=True)
class ExecutionAdmissionResult:
    """Immutable, signed result of admitting an ExecutionToken BEFORE D6 execution."""
    token_id: str
    execution_nonce: str
    obligation_id: str
    action_digest: str
    context_digest: str
    source_sha: str
    policy_version: int
    decision_id: str
    admitted_at: str
    is_admitted: bool
    signature: Optional[AsymmetricAuthoritySignature] = None
    error_message: Optional[str] = None
    owner_id: str = ""
    fencing_token: int = 0
    lease_epoch: int = 0
    state_version: int = 0
    state_digest: str = ""
    authority_context_digest: str = ""

    def __post_init__(self):
        if self.is_admitted:
            if not self.token_id:
                raise ValueError("token_id cannot be empty for admitted result.")
            if not self.execution_nonce:
                raise ValueError("execution_nonce cannot be empty for admitted result.")
            if not self.obligation_id:
                raise ValueError("obligation_id cannot be empty for admitted result.")
            _validate_pattern(self.action_digest, HEX_64_PATTERN, "action_digest")
            _validate_pattern(self.context_digest, HEX_64_PATTERN, "context_digest")
            _validate_pattern(self.source_sha, HEX_40_PATTERN, "source_sha")
            if not isinstance(self.policy_version, int) or self.policy_version < 1:
                raise ValueError("policy_version must be an integer >= 1.")
            if not self.decision_id:
                raise ValueError("decision_id cannot be empty for admitted result.")
            _validate_iso8601(self.admitted_at, "admitted_at")
            if not isinstance(self.signature, AsymmetricAuthoritySignature):
                raise TypeError("signature must be an AsymmetricAuthoritySignature instance for admitted result.")
            if not isinstance(self.fencing_token, int) or self.fencing_token < 0:
                raise ValueError("fencing_token must be an integer >= 0.")
            if not isinstance(self.lease_epoch, int) or self.lease_epoch < 0:
                raise ValueError("lease_epoch must be an integer >= 0.")
            if not isinstance(self.state_version, int) or self.state_version < 0:
                raise ValueError("state_version must be an integer >= 0.")
            if self.state_digest:
                _validate_pattern(self.state_digest, HEX_64_PATTERN, "state_digest")
            if self.authority_context_digest:
                _validate_pattern(self.authority_context_digest, HEX_64_PATTERN, "authority_context_digest")


@dataclass(frozen=True)
class ExecutionEnvelope:
    """Mandatory immutable container delivered to D6 executor (Â§8.1, Â§8.3).
    
    Contains: ExecutionToken, ExecutionAdmissionResult, ActionBinding, ExecutionContext.
    """
    token: ExecutionToken
    admission: ExecutionAdmissionResult
    action_binding: ActionBinding
    execution_context: ExecutionContext

    def __post_init__(self):
        if not isinstance(self.token, ExecutionToken):
            raise TypeError("token must be an ExecutionToken instance.")
        if not isinstance(self.admission, ExecutionAdmissionResult):
            raise TypeError("admission must be an ExecutionAdmissionResult instance.")
        if not isinstance(self.action_binding, ActionBinding):
            raise TypeError("action_binding must be an ActionBinding instance.")
        if not isinstance(self.execution_context, ExecutionContext):
            raise TypeError("execution_context must be an ExecutionContext instance.")

        # Mandatory exact binding invariants
        if not (self.token.action_digest == self.admission.action_digest == self.action_binding.action_digest):
            raise ValueError("Action digest mismatch across token, admission, and action_binding.")
        if not (self.token.context_digest == self.admission.context_digest == self.execution_context.context_digest):
            raise ValueError("Context digest mismatch across token, admission, and execution_context.")
        if self.token.token_id != self.admission.token_id:
            raise ValueError("Token ID mismatch between token and admission.")
        if self.token.execution_nonce != self.admission.execution_nonce:
            raise ValueError("Execution nonce mismatch between token and admission.")
        if self.token.obligation_id != self.admission.obligation_id:
            raise ValueError("Obligation ID mismatch between token and admission.")
        if self.token.source_sha != self.admission.source_sha:
            raise ValueError("Source SHA mismatch between token and admission.")
        if self.token.policy_version != self.admission.policy_version:
            raise ValueError("Policy version mismatch between token and admission.")
        if self.token.decision_id != self.admission.decision_id:
            raise ValueError("Decision ID mismatch between token and admission.")
        if self.token.owner_id != self.admission.owner_id:
            raise ValueError("Owner ID mismatch between token and admission.")
        if self.token.fencing_token != self.admission.fencing_token:
            raise ValueError("Fencing token mismatch between token and admission.")
        if self.token.lease_epoch != self.admission.lease_epoch:
            raise ValueError("Lease epoch mismatch between token and admission.")
        if self.token.state_version != self.admission.state_version:
            raise ValueError("State version mismatch between token and admission.")
        if self.token.state_digest != self.admission.state_digest:
            raise ValueError("State digest mismatch between token and admission.")
        if self.token.authority_context_digest != self.admission.authority_context_digest:
            raise ValueError("Authority context digest mismatch between token and admission.")

    @property
    def envelope_id(self) -> str:
        return self.token.execution_nonce

    @property
    def task_id(self) -> str:
        return self.token.proposal_id


def _build_token_payload(
    token_id: str,
    decision_id: str,
    obligation_id: str,
    proposal_id: str,
    action_digest: str,
    context_digest: str,
    source_sha: str,
    policy_version: int,
    execution_nonce: str,
    issued_at: str,
    expires_at: str,
    owner_id: str = "",
    fencing_token: int = 0,
    lease_epoch: int = 0,
    state_version: int = 0,
    state_digest: str = "",
    authority_context_digest: str = "",
) -> dict:
    return {
        "token_id": token_id,
        "decision_id": decision_id,
        "obligation_id": obligation_id,
        "proposal_id": proposal_id,
        "action_digest": action_digest,
        "context_digest": context_digest,
        "source_sha": source_sha,
        "policy_version": policy_version,
        "execution_nonce": execution_nonce,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "owner_id": owner_id,
        "fencing_token": fencing_token,
        "lease_epoch": lease_epoch,
        "state_version": state_version,
        "state_digest": state_digest,
        "authority_context_digest": authority_context_digest,
    }


def _build_admission_payload(
    token_id: str,
    execution_nonce: str,
    obligation_id: str,
    action_digest: str,
    context_digest: str,
    source_sha: str,
    policy_version: int,
    decision_id: str,
    admitted_at: str,
    owner_id: str = "",
    fencing_token: int = 0,
    lease_epoch: int = 0,
    state_version: int = 0,
    state_digest: str = "",
    authority_context_digest: str = "",
) -> dict:
    return {
        "token_id": token_id,
        "execution_nonce": execution_nonce,
        "obligation_id": obligation_id,
        "action_digest": action_digest,
        "context_digest": context_digest,
        "source_sha": source_sha,
        "policy_version": policy_version,
        "decision_id": decision_id,
        "admitted_at": admitted_at,
        "owner_id": owner_id,
        "fencing_token": fencing_token,
        "lease_epoch": lease_epoch,
        "state_version": state_version,
        "state_digest": state_digest,
        "authority_context_digest": authority_context_digest,
    }


def _compute_token_canonical_bytes(payload: dict) -> bytes:
    """Computes canonical RFC 8785 JSON bytes prefixed with the frozen domain separator."""
    return SCLASS_EXECUTION_TOKEN_DOMAIN_SEPARATOR.encode("utf-8") + canonicalize_json(payload)


def _compute_admission_canonical_bytes(payload: dict) -> bytes:
    """Computes canonical RFC 8785 JSON bytes prefixed with the frozen admission domain separator."""
    return SCLASS_EXECUTION_ADMISSION_DOMAIN_SEPARATOR.encode("utf-8") + canonicalize_json(payload)


def _mint_execution_token(
    token_id: str,
    decision_id: str,
    obligation_id: str,
    proposal_id: str,
    action_digest: str,
    context_digest: str,
    source_sha: str,
    policy_version: int,
    issued_at: str,
    expires_at: str,
    authority_signer: AuthoritySignerProtocol,
    execution_nonce: Optional[str] = None,
    signer_identity: str = "Gate3AuthoritativeVerifier",
    owner_id: str = "",
    fencing_token: int = 0,
    lease_epoch: int = 0,
    state_version: int = 0,
    state_digest: str = "",
    authority_context_digest: str = "",
) -> ExecutionToken:
    """Internal Controller token issuance function with domain separator binding."""
    if not isinstance(authority_signer, AuthoritySignerProtocol):
        raise TypeError("authority_signer must implement AuthoritySignerProtocol.")
    if not issued_at or not expires_at:
        raise ValueError("issued_at and expires_at timestamps are required.")

    nonce = execution_nonce or f"NONCE-TOK-{uuid.uuid4().hex[:12].upper()}"

    payload = _build_token_payload(
        token_id=token_id,
        decision_id=decision_id,
        obligation_id=obligation_id,
        proposal_id=proposal_id,
        action_digest=action_digest,
        context_digest=context_digest,
        source_sha=source_sha,
        policy_version=policy_version,
        execution_nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
        owner_id=owner_id,
        fencing_token=fencing_token,
        lease_epoch=lease_epoch,
        state_version=state_version,
        state_digest=state_digest,
        authority_context_digest=authority_context_digest,
    )

    canonical_bytes = _compute_token_canonical_bytes(payload)
    authority_sig = authority_signer.sign_payload(
        canonical_bytes=canonical_bytes,
        verifier_identity=signer_identity,
        timestamp_iso=issued_at,
    )

    return ExecutionToken(
        token_id=token_id,
        decision_id=decision_id,
        obligation_id=obligation_id,
        proposal_id=proposal_id,
        action_digest=action_digest,
        context_digest=context_digest,
        source_sha=source_sha,
        policy_version=policy_version,
        execution_nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
        signature=authority_sig,
        owner_id=owner_id,
        fencing_token=fencing_token,
        lease_epoch=lease_epoch,
        state_version=state_version,
        state_digest=state_digest,
        authority_context_digest=authority_context_digest,
    )


def verify_execution_token_signature(
    token: ExecutionToken,
    authority_signer: AuthoritySignerProtocol,
) -> bool:
    """Cryptographically verifies Ed25519 signature of ExecutionToken."""
    if not isinstance(token, ExecutionToken) or not isinstance(authority_signer, AuthoritySignerProtocol):
        return False
    payload = _build_token_payload(
        token_id=token.token_id,
        decision_id=token.decision_id,
        obligation_id=token.obligation_id,
        proposal_id=token.proposal_id,
        action_digest=token.action_digest,
        context_digest=token.context_digest,
        source_sha=token.source_sha,
        policy_version=token.policy_version,
        execution_nonce=token.execution_nonce,
        issued_at=token.issued_at,
        expires_at=token.expires_at,
        owner_id=token.owner_id,
        fencing_token=token.fencing_token,
        lease_epoch=token.lease_epoch,
        state_version=token.state_version,
        state_digest=token.state_digest,
        authority_context_digest=token.authority_context_digest,
    )
    try:
        canonical_bytes = _compute_token_canonical_bytes(payload)
        return authority_signer.verify_signature(canonical_bytes, token.signature)
    except (ValueError, TypeError, KeyError):
        return False


def verify_admission_signature(
    admission: ExecutionAdmissionResult,
    authority_signer: AuthoritySignerProtocol,
) -> bool:
    """Cryptographically verifies Ed25519 signature of ExecutionAdmissionResult."""
    if not isinstance(admission, ExecutionAdmissionResult) or not admission.is_admitted:
        return False
    if not admission.signature or not isinstance(authority_signer, AuthoritySignerProtocol):
        return False
    payload = _build_admission_payload(
        token_id=admission.token_id,
        execution_nonce=admission.execution_nonce,
        obligation_id=admission.obligation_id,
        action_digest=admission.action_digest,
        context_digest=admission.context_digest,
        source_sha=admission.source_sha,
        policy_version=admission.policy_version,
        decision_id=admission.decision_id,
        admitted_at=admission.admitted_at,
        owner_id=admission.owner_id,
        fencing_token=admission.fencing_token,
        lease_epoch=admission.lease_epoch,
        state_version=admission.state_version,
        state_digest=admission.state_digest,
        authority_context_digest=admission.authority_context_digest,
    )
    try:
        canonical_bytes = _compute_admission_canonical_bytes(payload)
        return authority_signer.verify_signature(canonical_bytes, admission.signature)
    except (ValueError, TypeError, KeyError):
        return False


def verify_execution_token(
    token: ExecutionToken,
    expected_obligation_id: str,
    expected_source_sha: str,
    expected_policy_version: int,
    expected_action_digest: str,
    expected_context_digest: str,
    current_time_iso: str,
    authority_signer: AuthoritySignerProtocol,
    expected_owner_id: Optional[str] = None,
    expected_fencing_token: Optional[int] = None,
    expected_lease_epoch: Optional[int] = None,
    expected_state_version: Optional[int] = None,
    expected_state_digest: Optional[str] = None,
    expected_authority_context_digest: Optional[str] = None,
) -> bool:
    """PURE verification of ExecutionToken. NO D2 MUTATION."""
    if not isinstance(token, ExecutionToken):
        return False
    if not isinstance(authority_signer, AuthoritySignerProtocol):
        return False

    # 1. Mandatory Exact Field Bindings
    if token.obligation_id != expected_obligation_id:
        return False
    if token.source_sha != expected_source_sha:
        return False
    if token.policy_version != expected_policy_version:
        return False
    if token.action_digest != expected_action_digest:
        return False
    if token.context_digest != expected_context_digest:
        return False
    if expected_owner_id is not None and token.owner_id != expected_owner_id:
        return False
    if expected_fencing_token is not None and token.fencing_token != expected_fencing_token:
        return False
    if expected_lease_epoch is not None and token.lease_epoch != expected_lease_epoch:
        return False
    if expected_state_version is not None and token.state_version != expected_state_version:
        return False
    if expected_state_digest is not None and token.state_digest != expected_state_digest:
        return False
    if expected_authority_context_digest is not None and token.authority_context_digest != expected_authority_context_digest:
        return False

    # 2. Time Boundary Verification (issued_at <= current_time <= expires_at)
    try:
        t_current = datetime.fromisoformat(current_time_iso.replace("Z", "+00:00"))
        t_issued = datetime.fromisoformat(token.issued_at.replace("Z", "+00:00"))
        t_expiry = datetime.fromisoformat(token.expires_at.replace("Z", "+00:00"))
        if t_current < t_issued or t_current > t_expiry:
            return False
    except Exception:
        return False

    # 3. Cryptographic Signature Verification
    if not verify_execution_token_signature(token, authority_signer):
        return False

    return True


def commit_admission(
    execution_nonce: str,
    nonce_store: D2NonceStore,
) -> bool:
    """The ONLY operation allowed to reserve ADMIT:<nonce> in D2 store."""
    if not execution_nonce or not isinstance(nonce_store, D2NonceStore):
        return False
    try:
        return nonce_store.reserve_nonce(f"ADMIT:{execution_nonce}")
    except Exception:
        return False


def verify_execution_envelope(
    envelope: ExecutionEnvelope,
    expected_source_sha: str,
    expected_policy_version: int,
    current_time_iso: str,
    authority_signer: AuthoritySignerProtocol,
    nonce_store: Optional[D2NonceStore] = None,
) -> bool:
    token = envelope.token
    admission = envelope.admission
    action_binding = envelope.action_binding
    ctx = envelope.execution_context
    if not admission.is_admitted: return False
    if not (token.action_digest == admission.action_digest == action_binding.action_digest): return False
    if not (token.context_digest == admission.context_digest == ctx.context_digest): return False
    if token.token_id != admission.token_id: return False
    if token.execution_nonce != admission.execution_nonce: return False
    if token.obligation_id != admission.obligation_id: return False
    if token.source_sha != expected_source_sha or admission.source_sha != expected_source_sha: return False
    if token.policy_version != expected_policy_version or admission.policy_version != expected_policy_version: return False
    if token.decision_id != admission.decision_id: return False
    if token.owner_id != admission.owner_id: return False
    if token.fencing_token != admission.fencing_token: return False
    if token.lease_epoch != admission.lease_epoch: return False
    if token.state_version != admission.state_version: return False
    if token.state_digest != admission.state_digest: return False
    if token.authority_context_digest != admission.authority_context_digest: return False
    try:
        t_current = datetime.fromisoformat(current_time_iso.replace("Z", "+00:00"))
        t_issued = datetime.fromisoformat(token.issued_at.replace("Z", "+00:00"))
        t_expiry = datetime.fromisoformat(token.expires_at.replace("Z", "+00:00"))
        if t_current < t_issued or t_current > t_expiry: return False
    except Exception: return False
    if not verify_execution_token_signature(token, authority_signer): return False
    if not verify_admission_signature(admission, authority_signer): return False
    if nonce_store is not None and nonce_store.is_nonce_consumed(token.execution_nonce):
        return False
    return True


@dataclass(frozen=True)
class AuthorizedSessionExecutionBinding:
    """
    Cryptographically signed authority artifact issued by D3/D5 authority boundary (Â§8.1, Â§8.3).
    Binds an ExecutionContext to a specific session, repository, commit SHA, task, and capability set.
    """
    session_id: str
    repository_id: str
    source_sha: str
    task_id: str
    execution_context_digest: str
    granted_capabilities: Tuple[str, ...]
    signature: AsymmetricAuthoritySignature
    binding_id: str = ""

    def __post_init__(self):
        if not self.session_id or not isinstance(self.session_id, str):
            raise ValueError("session_id must be a non-empty string.")
        if not self.repository_id or not isinstance(self.repository_id, str):
            raise ValueError("repository_id must be a non-empty string.")
        _validate_pattern(self.source_sha, HEX_40_PATTERN, "source_sha")
        if not self.task_id or not isinstance(self.task_id, str):
            raise ValueError("task_id must be a non-empty string.")
        _validate_pattern(self.execution_context_digest, HEX_64_PATTERN, "execution_context_digest")
        if not isinstance(self.signature, AsymmetricAuthoritySignature):
            raise TypeError("signature must be an instance of AsymmetricAuthoritySignature.")
        sorted_caps = tuple(sorted(set(self.granted_capabilities)))
        object.__setattr__(self, "granted_capabilities", sorted_caps)


def _build_session_binding_payload(
    session_id: str,
    repository_id: str,
    source_sha: str,
    task_id: str,
    execution_context_digest: str,
    granted_capabilities: Sequence[str],
) -> Mapping[str, Any]:
    return {
        "session_id": session_id,
        "repository_id": repository_id,
        "source_sha": source_sha,
        "task_id": task_id,
        "execution_context_digest": execution_context_digest,
        "granted_capabilities": sorted(list(granted_capabilities)),
    }


def _compute_session_binding_canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return SCLASS_SESSION_BINDING_DOMAIN_SEPARATOR.encode("utf-8") + canonicalize_json(payload)


def _issue_authorized_session_binding(
    session_id: str,
    repository_id: str,
    source_sha: str,
    task_id: str,
    execution_context: ExecutionContext,
    authority_signer: AuthoritySignerProtocol,
) -> AuthorizedSessionExecutionBinding:
    """
    Issues a cryptographically signed AuthorizedSessionExecutionBinding.
    Controller / Authority boundary holds the ONLY issuance path.
    """
    if not isinstance(execution_context, ExecutionContext):
        raise TypeError("execution_context must be an instance of ExecutionContext.")
    if not isinstance(authority_signer, AuthoritySignerProtocol):
        raise TypeError("authority_signer must implement AuthoritySignerProtocol.")

    payload = _build_session_binding_payload(
        session_id=session_id,
        repository_id=repository_id,
        source_sha=source_sha,
        task_id=task_id,
        execution_context_digest=execution_context.context_digest,
        granted_capabilities=execution_context.capability_set,
    )
    canonical_bytes = _compute_session_binding_canonical_bytes(payload)
    now_iso = datetime.now(timezone.utc).isoformat()
    sig = authority_signer.sign_payload(
        canonical_bytes=canonical_bytes,
        verifier_identity="Gate3AuthoritativeVerifier",
        timestamp_iso=now_iso,
    )

    return AuthorizedSessionExecutionBinding(
        session_id=session_id,
        repository_id=repository_id,
        source_sha=source_sha,
        task_id=task_id,
        execution_context_digest=execution_context.context_digest,
        granted_capabilities=execution_context.capability_set,
        signature=sig,
        binding_id=f"BIND-{uuid.uuid4().hex[:8].upper()}",
    )


def verify_authorized_session_binding(
    binding: AuthorizedSessionExecutionBinding,
    authority_signer: AuthoritySignerProtocol,
) -> bool:
    """Cryptographically verifies Ed25519 signature of AuthorizedSessionExecutionBinding."""
    if not isinstance(binding, AuthorizedSessionExecutionBinding) or not isinstance(authority_signer, AuthoritySignerProtocol):
        return False
    payload = _build_session_binding_payload(
        session_id=binding.session_id,
        repository_id=binding.repository_id,
        source_sha=binding.source_sha,
        task_id=binding.task_id,
        execution_context_digest=binding.execution_context_digest,
        granted_capabilities=binding.granted_capabilities,
    )
    try:
        canonical_bytes = _compute_session_binding_canonical_bytes(payload)
        return authority_signer.verify_signature(canonical_bytes, binding.signature)
    except Exception:
        return False
