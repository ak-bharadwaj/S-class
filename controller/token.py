"""
S-Class EOS V11.2 - D5 Cryptographic Execution Token (§8.1, §8.3).
Immutable, Ed25519-signed single-use execution tokens.
Reuses D2 durable storage for atomic single-use nonce reservation.
Binds token_id, obligation_id, proposal_id, source_sha, policy_version, execution_nonce, timestamps, and signature.
Domain Separator: SCLASS_EXECUTION_TOKEN_V1:
Controller holds the ONLY issuance path.
"""

from __future__ import annotations
import uuid
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Any
from domain.models import AsymmetricAuthoritySignature, _validate_pattern, _validate_iso8601
from domain.types import HEX_40_PATTERN, HEX_64_PATTERN
from events.serializer import canonicalize_json
from events.store import D2NonceStore
from policy.models import AuthoritySignerProtocol


TOKEN_ID_PREFIX = "TOK-"
SCLASS_EXECUTION_TOKEN_DOMAIN_SEPARATOR = "SCLASS_EXECUTION_TOKEN_V1:"


@dataclass(frozen=True)
class ExecutionToken:
    """Immutable single-use execution token issued exclusively by D5 Controller upon authorization."""
    token_id: str
    obligation_id: str
    proposal_id: str
    source_sha: str
    policy_version: int
    execution_nonce: str
    issued_at: str
    expires_at: str
    signature: AsymmetricAuthoritySignature

    def __post_init__(self):
        if not self.token_id or not self.token_id.startswith(TOKEN_ID_PREFIX):
            raise ValueError(f"Invalid token_id: '{self.token_id}' must start with '{TOKEN_ID_PREFIX}'")
        if not self.obligation_id:
            raise ValueError("obligation_id cannot be empty.")
        if not self.proposal_id:
            raise ValueError("proposal_id cannot be empty.")
        _validate_pattern(self.source_sha, HEX_40_PATTERN, "source_sha")
        if not isinstance(self.policy_version, int) or self.policy_version < 1:
            raise ValueError("policy_version must be an integer >= 1.")
        if not self.execution_nonce:
            raise ValueError("execution_nonce cannot be empty.")
        _validate_iso8601(self.issued_at, "issued_at")
        _validate_iso8601(self.expires_at, "expires_at")
        if not isinstance(self.signature, AsymmetricAuthoritySignature):
            raise TypeError("signature must be an AsymmetricAuthoritySignature instance.")


def _build_token_payload(
    token_id: str,
    obligation_id: str,
    proposal_id: str,
    source_sha: str,
    policy_version: int,
    execution_nonce: str,
    issued_at: str,
    expires_at: str,
) -> dict:
    return {
        "token_id": token_id,
        "obligation_id": obligation_id,
        "proposal_id": proposal_id,
        "source_sha": source_sha,
        "policy_version": policy_version,
        "execution_nonce": execution_nonce,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }


def _compute_token_canonical_bytes(payload: dict) -> bytes:
    """Computes canonical RFC 8785 JSON bytes prefixed with the frozen domain separator."""
    return SCLASS_EXECUTION_TOKEN_DOMAIN_SEPARATOR.encode("utf-8") + canonicalize_json(payload)


def _mint_execution_token(
    token_id: str,
    obligation_id: str,
    proposal_id: str,
    source_sha: str,
    policy_version: int,
    issued_at: str,
    expires_at: str,
    authority_signer: AuthoritySignerProtocol,
    execution_nonce: Optional[str] = None,
    signer_identity: str = "Gate3AuthoritativeVerifier",
) -> ExecutionToken:
    """Internal Controller token issuance function with domain separator binding."""
    if not isinstance(authority_signer, AuthoritySignerProtocol):
        raise TypeError("authority_signer must implement AuthoritySignerProtocol.")
    if not issued_at or not expires_at:
        raise ValueError("issued_at and expires_at timestamps are required.")

    nonce = execution_nonce or f"NONCE-TOK-{uuid.uuid4().hex[:12].upper()}"

    payload = _build_token_payload(
        token_id=token_id,
        obligation_id=obligation_id,
        proposal_id=proposal_id,
        source_sha=source_sha,
        policy_version=policy_version,
        execution_nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )

    canonical_bytes = _compute_token_canonical_bytes(payload)
    authority_sig = authority_signer.sign_payload(
        canonical_bytes=canonical_bytes,
        verifier_identity=signer_identity,
        timestamp_iso=issued_at,
    )

    return ExecutionToken(
        token_id=token_id,
        obligation_id=obligation_id,
        proposal_id=proposal_id,
        source_sha=source_sha,
        policy_version=policy_version,
        execution_nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
        signature=authority_sig,
    )


def verify_and_consume_execution_token(
    token: ExecutionToken,
    expected_obligation_id: str,
    expected_source_sha: str,
    expected_policy_version: int,
    current_time_iso: str,
    authority_signer: AuthoritySignerProtocol,
    nonce_store: Optional[D2NonceStore] = None,
) -> bool:
    """Cryptographically verifies token, checks bindings & time validity, and atomically reserves nonce in D2 store.
    
    Validates current_time >= issued_at and current_time <= expires_at.
    """
    if not isinstance(token, ExecutionToken):
        return False
    if not isinstance(authority_signer, AuthoritySignerProtocol):
        return False

    # 1. Structural Binding Verification
    if token.obligation_id != expected_obligation_id:
        return False
    if token.source_sha != expected_source_sha:
        return False
    if token.policy_version != expected_policy_version:
        return False

    # 2. Time Boundary Verification (current_time >= issued_at and current_time <= expires_at)
    try:
        t_current = datetime.fromisoformat(current_time_iso.replace("Z", "+00:00"))
        t_issued = datetime.fromisoformat(token.issued_at.replace("Z", "+00:00"))
        t_expiry = datetime.fromisoformat(token.expires_at.replace("Z", "+00:00"))
        if t_current < t_issued:
            # Future-issued token rejected
            return False
        if t_current > t_expiry:
            # Expired token rejected
            return False
    except Exception:
        return False

    # 3. Cryptographic Signature Verification with Domain Separator
    payload = _build_token_payload(
        token_id=token.token_id,
        obligation_id=token.obligation_id,
        proposal_id=token.proposal_id,
        source_sha=token.source_sha,
        policy_version=token.policy_version,
        execution_nonce=token.execution_nonce,
        issued_at=token.issued_at,
        expires_at=token.expires_at,
    )
    try:
        canonical_bytes = _compute_token_canonical_bytes(payload)
        is_sig_valid = authority_signer.verify_signature(canonical_bytes, token.signature)
        if not is_sig_valid:
            return False
    except (ValueError, TypeError, KeyError):
        return False

    # 4. Atomic D2 Single-Use Nonce Reservation (BEFORE D6 execution)
    store = nonce_store or D2NonceStore()
    try:
        reserved = store.reserve_nonce(token.execution_nonce)
        return reserved
    except Exception:
        return False
