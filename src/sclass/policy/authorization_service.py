"""
S-Class Policy: Authoritative Authorization Service.
Governs non-forgeable, request-bound AuthorizationDecision issuance,
HMAC integrity token sealing, and cryptographic decision verification.

Invariants Enforced:
1. NO VALID AUTH SECRET -> NO EXECUTION (Fail-closed in strict mode; zero hardcoded secrets).
2. NO AUTHORITATIVE CAPABILITY -> NO EXECUTION (Every action must resolve to a valid capability).
3. DECISION BOUND TO CURRENT REQUEST + CAPABILITY + POLICY (All canonical hashes sealed into HMAC).
"""

from __future__ import annotations
import os
import time
import base64
import secrets
import hmac
import json
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union, Tuple

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.capability import Capability, CapabilityEvaluator, CapabilityDecision
from sclass.policy.capability_resolver import CapabilityRegistry, CapabilityResolver
from sclass.core.errors import SecurityViolationError

# Global ephemeral secret generated per-process in dev mode (never hardcoded in source)
_DEV_EPHEMERAL_SECRET: bytes = secrets.token_bytes(32)


def get_authorization_secret(allow_ephemeral_dev: bool = True) -> bytes:
    """
    Authoritatively resolves the S-Class HMAC authorization secret.
    In strict security mode (SCLASS_STRICT_SECURITY=1 or SCLASS_ENVIRONMENT=production):
        A missing SCLASS_AUTH_SECRET fails closed and raises SecurityViolationError.
    In development mode:
        A high-entropy, per-session ephemeral secret is used. Zero hardcoded secrets in source.
    """
    env_secret = os.environ.get("SCLASS_AUTH_SECRET")
    if env_secret:
        return env_secret.encode("utf-8")

    is_strict = (
        os.environ.get("SCLASS_STRICT_SECURITY", "").lower() in ("1", "true", "yes")
        or os.environ.get("SCLASS_ENVIRONMENT", "").lower() == "production"
    )
    if is_strict or not allow_ephemeral_dev:
        raise SecurityViolationError(
            "NO VALID AUTH SECRET -> NO EXECUTION: SCLASS_AUTH_SECRET environment variable is missing "
            "in strict security / production mode. Fail-closed: refusing execution without authoritative secret."
        )

    return _DEV_EPHEMERAL_SECRET


def compute_canonical_request_hash(request: Union[ActionRequest, Any]) -> str:
    """
    Computes deterministic SHA-256 hash across canonical ActionRequest fields.
    Guarantees that an authorization decision cannot be transplanted across requests.
    """
    if request is None:
        return ""

    actor = getattr(request, "actor", None) or getattr(request, "agent", "unknown_actor")
    session = getattr(request, "session", None) or getattr(request, "task_id", "")
    capability = getattr(request, "capability", None) or getattr(request, "tool", "")
    action = getattr(request, "action", "unknown_action")
    target = getattr(request, "target", "") or ""
    parameters = getattr(request, "parameters", {}) or {}
    workspace = getattr(request, "workspace", "") or ""

    # Sort parameters deterministically
    try:
        sorted_params = json.loads(json.dumps(parameters, sort_keys=True, default=str))
    except Exception:
        sorted_params = {str(k): str(v) for k, v in sorted(parameters.items())}

    canonical_repr = {
        "action": str(action),
        "actor": str(actor),
        "capability": str(capability),
        "parameters": sorted_params,
        "session": str(session),
        "target": str(target),
        "workspace": os.path.normpath(workspace).replace("\\", "/") if workspace else "",
    }
    canonical_bytes = json.dumps(canonical_repr, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def compute_canonical_capability_hash(capability: Optional[Capability]) -> str:
    """Computes deterministic SHA-256 hash of an authoritative Capability object."""
    if capability is None:
        return ""
    try:
        cap_dict = capability.to_dict()
        canonical_bytes = json.dumps(cap_dict, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()
    except Exception:
        return ""


def generate_integrity_token(
    issuer: str,
    request_hash: str,
    capability_hash: str,
    policy_id: str,
    policy_version: str,
    outcome: str,
    risk_level: str,
    evaluated_at: str,
    capability_id: str = "",
    capability_version: str = "1.0.0",
    registry_generation: int = 0,
    secret_key: Optional[bytes] = None,
) -> str:
    """Computes HMAC-SHA256 integrity token sealing decision parameters."""
    key = secret_key or get_authorization_secret()
    payload = f"{issuer}:{request_hash}:{capability_hash}:{capability_id}:{capability_version}:{registry_generation}:{policy_id}:{policy_version}:{outcome}:{risk_level}:{evaluated_at}"
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_decision_integrity(
    decision: Any,
    request: Union[ActionRequest, Any],
    capability: Optional[Capability] = None,
    expected_capability_hash: Optional[str] = None,
    expected_capability_id: Optional[str] = None,
    expected_capability_version: Optional[str] = None,
    expected_registry_generation: Optional[int] = None,
    expected_policy_version: Optional[str] = None,
    secret_key: Optional[bytes] = None,
    max_age_seconds: float = 3600.0,
) -> Tuple[bool, str]:
    """
    Authoritatively verifies that an AuthorizationDecision:
    1. Was issued by S-Class (issuer == 'S_CLASS')
    2. Is bound to the exact canonical ActionRequest (request_hash matches)
    3. Is bound to the exact authoritative Capability (capability_hash, capability_id, capability_version match)
    4. Is bound to the active registry generation (capability_registry_generation matches)
    5. Is bound to the active policy version (policy_version matches)
    6. Has not been forged or tampered with (valid HMAC integrity_token)
    7. Is not stale (within max_age_seconds)
    8. Is allowed (outcome in 'allow', 'warn')
    """
    if decision is None:
        return False, "Authorization decision is None"

    issuer = getattr(decision, "issuer", None)
    if issuer != "S_CLASS":
        return False, f"Untrusted issuer '{issuer}': only S-Class issued decisions are authoritative"

    # 1. Request Hash Binding
    req_hash = compute_canonical_request_hash(request)
    decision_req_hash = getattr(decision, "request_hash", None)
    if not decision_req_hash or not hmac.compare_digest(decision_req_hash, req_hash):
        return False, f"Request hash mismatch: decision bound to '{decision_req_hash}', but request hash is '{req_hash}'"

    # 2. Capability Hash, ID, and Version Binding
    target_cap_hash = expected_capability_hash or (compute_canonical_capability_hash(capability) if capability else None)
    if target_cap_hash is not None:
        decision_cap_hash = getattr(decision, "capability_hash", "") or ""
        if not decision_cap_hash or not hmac.compare_digest(decision_cap_hash, target_cap_hash):
            return False, f"Capability hash mismatch: decision bound to '{decision_cap_hash}', but expected capability hash is '{target_cap_hash}'"

    target_cap_id = expected_capability_id or (getattr(capability, "id", None) if capability else None)
    if target_cap_id is not None:
        decision_cap_id = getattr(decision, "capability_id", "") or ""
        if decision_cap_id != target_cap_id:
            return False, f"Capability ID mismatch: decision bound to ID '{decision_cap_id}', but expected capability ID is '{target_cap_id}'"

    target_cap_ver = expected_capability_version or (getattr(capability, "version", None) if capability else None)
    if target_cap_ver is not None:
        decision_cap_ver = getattr(decision, "capability_version", "1.0.0") or "1.0.0"
        if decision_cap_ver != target_cap_ver:
            return False, f"Capability version mismatch: decision bound to version '{decision_cap_ver}', but active capability version is '{target_cap_ver}'"

    # 3. Registry Generation Freshness
    decision_gen = getattr(decision, "capability_registry_generation", 0)
    if expected_registry_generation is not None:
        if decision_gen != expected_registry_generation:
            return False, f"Registry generation mismatch: decision bound to registry generation {decision_gen}, but active registry generation is {expected_registry_generation}"

    # 4. Policy Version Freshness
    pol_ver = getattr(decision, "policy_version", "1.0.0")
    if expected_policy_version is not None:
        if pol_ver != expected_policy_version:
            return False, f"Policy version mismatch: decision bound to version '{pol_ver}', but active policy version is '{expected_policy_version}'"

    token = getattr(decision, "integrity_token", None)
    if not token:
        return False, "Missing integrity token on authorization decision"

    outcome_str = getattr(decision.outcome, "value", str(decision.outcome)).lower()
    risk_str = getattr(decision, "risk_level", "")
    cap_hash = getattr(decision, "capability_hash", "") or ""
    cap_id = getattr(decision, "capability_id", "") or ""
    cap_ver = getattr(decision, "capability_version", "1.0.0") or "1.0.0"
    pol_id = getattr(decision, "policy_id", "")
    eval_at = getattr(decision, "evaluated_at", "")

    key = secret_key or get_authorization_secret()
    expected_token = generate_integrity_token(
        issuer=issuer,
        request_hash=decision_req_hash,
        capability_hash=cap_hash,
        capability_id=cap_id,
        capability_version=cap_ver,
        registry_generation=decision_gen,
        policy_id=pol_id,
        policy_version=pol_ver,
        outcome=outcome_str,
        risk_level=risk_str,
        evaluated_at=eval_at,
        secret_key=key,
    )

    if not hmac.compare_digest(token, expected_token):
        return False, "Integrity token verification failed: decision has been forged or tampered with"

    # 5. Check Staleness
    if eval_at:
        try:
            dt = datetime.fromisoformat(eval_at)
            now = datetime.now(timezone.utc)
            if (now - dt).total_seconds() > max_age_seconds:
                return False, f"Authorization decision is stale (age exceeds {max_age_seconds}s)"
        except Exception:
            pass

    if not getattr(decision, "is_allowed", False):
        return False, f"Decision outcome '{outcome_str}' does not permit execution"

    return True, "Authorized and verified"


class AuthorizationService:
    """
    Central S-Class Authoritative Authorization Service.
    Owns the full pipeline:
    ActionRequest -> Authoritative Capability -> Capability evaluation -> Policy evaluation -> Sealed Decision.
    """

    def __init__(
        self,
        secret_key: Optional[bytes] = None,
        policy_version: str = "1.0.0",
        capability_registry: Optional[CapabilityRegistry] = None,
        policy_provider: Optional[Any] = None,
    ):
        self._secret_key = secret_key or get_authorization_secret()
        self.policy_version = policy_version
        self.capability_registry = capability_registry or CapabilityResolver.get_global_registry()
        self.policy_provider = policy_provider

    def mint_approval_token(
        self,
        request: ActionRequest,
        approver: str = "operator",
        ttl_seconds: float = 300.0,
    ) -> str:
        """
        Mints a verifiable, URL-safe base64 approval token for a specific ActionRequest.
        Supports ISO timestamps without colon delimiter collision bugs and enforces expiration.
        Format: <base64url_payload>.<hmac_signature>
        """
        req_hash = compute_canonical_request_hash(request)
        now_ts = round(time.time(), 3)
        exp_ts = round(now_ts + float(ttl_seconds), 3)
        now_iso = datetime.now(timezone.utc).isoformat()

        payload_dict = {
            "approver": approver,
            "req_hash": req_hash,
            "created_at": now_iso,
            "iat": now_ts,
            "exp": exp_ts,
        }
        payload_bytes = json.dumps(payload_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")

        sig = hmac.new(self._secret_key, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{payload_b64}.{sig}"

    def verify_approval_token(self, token: str, request: ActionRequest) -> bool:
        """
        Verifies that an approval token was genuinely minted by S-Class for this exact request,
        has not expired, and has not been tampered with.
        """
        if not token or not isinstance(token, str) or "." not in token:
            return False

        parts = token.split(".")
        if len(parts) != 2:
            return False

        payload_b64, sig = parts

        # 1. Cryptographic HMAC verification
        expected_sig = hmac.new(self._secret_key, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return False

        # 2. Decode payload
        try:
            padded = payload_b64 + "=" * (-len(payload_b64) % 4)
            payload_bytes = base64.urlsafe_b64decode(padded)
            data = json.loads(payload_bytes.decode("utf-8"))
        except Exception:
            return False

        # 3. Verify request hash binding
        req_hash = compute_canonical_request_hash(request)
        token_req_hash = data.get("req_hash", "")
        if not token_req_hash or not hmac.compare_digest(token_req_hash, req_hash):
            return False

        # 4. Verify TTL expiration
        now_ts = time.time()
        if now_ts > float(data.get("exp", 0.0)):
            return False

        return True

    def seal_decision(
        self,
        request: ActionRequest,
        outcome: DecisionOutcome,
        policy_id: str,
        risk_level: str,
        reason: str,
        remediation: Optional[str] = None,
        capability: Optional[Capability] = None,
        registry_generation: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuthorizationDecision:
        """Constructs and cryptographically seals a canonical AuthorizationDecision."""
        now_iso = datetime.now(timezone.utc).isoformat()
        req_hash = compute_canonical_request_hash(request)
        cap_hash = compute_canonical_capability_hash(capability)
        cap_id = getattr(capability, "id", "") if capability else ""
        cap_ver = getattr(capability, "version", "1.0.0") if capability else "1.0.0"
        reg_gen = registry_generation if registry_generation is not None else getattr(self.capability_registry, "generation", 0)
        outcome_str = outcome.value if isinstance(outcome, DecisionOutcome) else str(outcome)

        token = generate_integrity_token(
            issuer="S_CLASS",
            request_hash=req_hash,
            capability_hash=cap_hash,
            capability_id=cap_id,
            capability_version=cap_ver,
            registry_generation=reg_gen,
            policy_id=policy_id,
            policy_version=self.policy_version,
            outcome=outcome_str,
            risk_level=risk_level,
            evaluated_at=now_iso,
            secret_key=self._secret_key,
        )

        meta = dict(metadata or {})
        return AuthorizationDecision(
            outcome=outcome,
            policy_id=policy_id,
            risk_level=risk_level,
            reason=reason,
            remediation=remediation,
            evaluated_at=now_iso,
            metadata=meta,
            issuer="S_CLASS",
            request_hash=req_hash,
            capability_hash=cap_hash,
            capability_id=cap_id,
            capability_version=cap_ver,
            capability_registry_generation=reg_gen,
            policy_version=self.policy_version,
            integrity_token=token,
        )

    def authorize(
        self,
        request: ActionRequest,
        capability: Optional[Capability] = None,
        workspace_dir: str = "",
        policy_engine: Optional[Any] = None,
        policy_provider: Optional[Any] = None,
    ) -> AuthorizationDecision:
        """
        Authoritatively evaluates an ActionRequest across Capability, Policy, and Invariants.
        Enforces:
        1. NO AUTHORITATIVE CAPABILITY -> NO EXECUTION
        2. NO CALLER-SUPPLIED CAPABILITY MAY BECOME AUTHORITY
        Returns a sealed, non-forgeable AuthorizationDecision.
        """
        if request is None:
            raise SecurityViolationError("NO AUTHORIZATION -> NO EXECUTION: ActionRequest cannot be None.")

        ws = os.path.abspath(workspace_dir or request.workspace or os.getcwd())

        # 1. Resolve Authoritative Capability exclusively from registry
        reg_cap = self.capability_registry.resolve(request, workspace_dir=ws)

        # Invariant: NO CALLER-SUPPLIED CAPABILITY MAY BECOME AUTHORITY
        if capability is not None:
            if reg_cap is None or (capability is not reg_cap and capability != reg_cap):
                return self.seal_decision(
                    request=request,
                    outcome=DecisionOutcome.DENY,
                    policy_id="FORGED-CAPABILITY",
                    risk_level="critical",
                    reason="NO CALLER-SUPPLIED CAPABILITY MAY BECOME AUTHORITY: Caller-supplied capability rejected. "
                           "Capabilities must resolve exclusively from the authoritative registry.",
                    remediation="Do not pass external capabilities to authorize(); register capabilities in CapabilityRegistry.",
                    capability=None,
                )

        if reg_cap is None:
            return self.seal_decision(
                request=request,
                outcome=DecisionOutcome.DENY,
                policy_id="NO-CAPABILITY",
                risk_level="critical",
                reason="NO AUTHORITATIVE CAPABILITY -> NO EXECUTION: No capability granted to actor for this action in authoritative registry.",
                remediation="Register an authoritative capability covering this actor, operation, and resource.",
                capability=None,
            )

        target_cap = reg_cap

        # 2. Evaluate all 11 dimensions of the Capability
        cap_decision = target_cap.evaluate_request(request, ws)
        if not cap_decision.allowed:
            return self.seal_decision(
                request=request,
                outcome=DecisionOutcome.DENY,
                policy_id=cap_decision.matched_policy,
                risk_level=str(target_cap.risk),
                reason=f"Capability constraint violation: {cap_decision.explanation}",
                remediation="Request requires a capability with expanded privileges or valid approval.",
                capability=target_cap,
                metadata={"failed_constraints": cap_decision.failed_constraints},
            )

        # 3. Evaluate Policy Engine / Policy Provider
        active_provider = policy_provider or self.policy_provider
        if active_provider is not None:
            raw_decision = active_provider.evaluate(
                request=request,
                workspace_dir=ws,
                capability=target_cap,
                expected_policy_version=self.policy_version,
            )
        elif policy_engine is not None:
            raw_decision = policy_engine.evaluate(request, ws)
        else:
            from sclass.control.policy import DefaultPolicyEngine
            raw_decision = DefaultPolicyEngine().evaluate(request, ws)

        if raw_decision is None:
            return self.seal_decision(
                request=request,
                outcome=DecisionOutcome.DENY,
                policy_id="POLICY-UNKNOWN",
                risk_level="critical",
                reason="UNKNOWN POLICY STATE -> NO EXECUTION: Policy engine returned no decision.",
                capability=target_cap,
            )

        # Enforce Policy Version Binding if provider returned a policy version
        dec_pol_ver = None
        if hasattr(raw_decision, "policy_version"):
            dec_pol_ver = getattr(raw_decision, "policy_version")
        elif hasattr(raw_decision, "metadata") and isinstance(raw_decision.metadata, dict):
            dec_pol_ver = raw_decision.metadata.get("policy_version")

        if dec_pol_ver is not None and str(dec_pol_ver) != str(self.policy_version):
            return self.seal_decision(
                request=request,
                outcome=DecisionOutcome.DENY,
                policy_id="OPA-VERSION-MISMATCH",
                risk_level="critical",
                reason=f"POLICY VERSION MISMATCH: Policy evaluated under version '{dec_pol_ver}', but active S-Class policy version is '{self.policy_version}'. Fail-closed policy denies execution.",
                capability=target_cap,
                metadata={"expected_policy_version": self.policy_version, "received_policy_version": dec_pol_ver},
            )

        raw_outcome = getattr(raw_decision, "outcome", None)
        if isinstance(raw_outcome, DecisionOutcome):
            outcome = raw_outcome
        elif hasattr(raw_decision, "allow"):
            # PolicyEvaluationResult protocol support
            outcome = DecisionOutcome.ALLOW if getattr(raw_decision, "allow") else DecisionOutcome.DENY
        elif hasattr(raw_decision, "allowed"):
            # Alternative policy result object support
            outcome = DecisionOutcome.ALLOW if getattr(raw_decision, "allowed") else DecisionOutcome.DENY
        else:
            out_str = getattr(raw_outcome, "value", str(raw_outcome)).lower()
            if out_str == "allow":
                outcome = DecisionOutcome.ALLOW
            elif out_str == "warn":
                outcome = DecisionOutcome.WARN
            elif out_str == "require_approval":
                outcome = DecisionOutcome.REQUIRE_APPROVAL
            else:
                outcome = DecisionOutcome.DENY

        pol_id = getattr(raw_decision, "policy_id", "SCLASS-DEFAULT")
        risk = getattr(raw_decision, "risk_level", "medium")
        reason = getattr(raw_decision, "reason", "Evaluated under S-Class policy engine")
        remediation = getattr(raw_decision, "remediation", None)
        meta = getattr(raw_decision, "metadata", {})

        return self.seal_decision(
            request=request,
            outcome=outcome,
            policy_id=pol_id,
            risk_level=risk,
            reason=reason,
            remediation=remediation,
            capability=target_cap,
            metadata=meta,
        )

    def verify_decision(
        self,
        decision: Any,
        request: ActionRequest,
        capability: Optional[Capability] = None,
        expected_registry_generation: Optional[int] = None,
        expected_policy_version: Optional[str] = None,
        max_age_seconds: float = 3600.0,
    ) -> bool:
        """Verifies an AuthorizationDecision against this service's secret key, capability, registry generation, and policy version."""
        ver = expected_policy_version or self.policy_version
        exp_gen = expected_registry_generation if expected_registry_generation is not None else getattr(self.capability_registry, "generation", None)
        valid, _ = verify_decision_integrity(
            decision=decision,
            request=request,
            capability=capability,
            expected_registry_generation=exp_gen,
            expected_policy_version=ver,
            secret_key=self._secret_key,
            max_age_seconds=max_age_seconds,
        )
        return valid
