"""
S-Class Policy: Authoritative Authorization Service.
Governs non-forgeable, request-bound AuthorizationDecision issuance,
HMAC integrity token sealing, and cryptographic decision verification.
"""

from __future__ import annotations
import os
import hmac
import json
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union, Tuple

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.capability import Capability, CapabilityEvaluator, CapabilityDecision
from sclass.core.errors import SecurityViolationError


_SCLASS_INTERNAL_AUTH_SECRET = os.environ.get(
    "SCLASS_AUTH_SECRET",
    "sclass-internal-authoritative-auth-token-secret-v1"
).encode("utf-8")


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
    """Computes deterministic SHA-256 hash of a Capability object."""
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
    secret_key: Optional[bytes] = None,
) -> str:
    """Computes HMAC-SHA256 integrity token sealing decision parameters."""
    key = secret_key or _SCLASS_INTERNAL_AUTH_SECRET
    payload = f"{issuer}:{request_hash}:{capability_hash}:{policy_id}:{policy_version}:{outcome}:{risk_level}:{evaluated_at}"
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_decision_integrity(
    decision: Any,
    request: Union[ActionRequest, Any],
    secret_key: Optional[bytes] = None,
    max_age_seconds: float = 3600.0,
) -> Tuple[bool, str]:
    """
    Authoritatively verifies that an AuthorizationDecision:
    1. Was issued by S-Class (issuer == 'S_CLASS')
    2. Is bound to the exact canonical ActionRequest (request_hash matches)
    3. Has not been forged or tampered with (valid HMAC integrity_token)
    4. Is not stale (within max_age_seconds)
    5. Is allowed (outcome in 'allow', 'warn')
    """
    if decision is None:
        return False, "Authorization decision is None"

    issuer = getattr(decision, "issuer", None)
    if issuer != "S_CLASS":
        return False, f"Untrusted issuer '{issuer}': only S-Class issued decisions are authoritative"

    req_hash = compute_canonical_request_hash(request)
    decision_req_hash = getattr(decision, "request_hash", None)
    if not decision_req_hash or not hmac.compare_digest(decision_req_hash, req_hash):
        return False, f"Request hash mismatch: decision bound to '{decision_req_hash}', but request hash is '{req_hash}'"

    token = getattr(decision, "integrity_token", None)
    if not token:
        return False, "Missing integrity token on authorization decision"

    outcome_str = getattr(decision.outcome, "value", str(decision.outcome)).lower()
    risk_str = getattr(decision, "risk_level", "")
    cap_hash = getattr(decision, "capability_hash", "") or ""
    pol_id = getattr(decision, "policy_id", "")
    pol_ver = getattr(decision, "policy_version", "1.0.0")
    eval_at = getattr(decision, "evaluated_at", "")

    expected_token = generate_integrity_token(
        issuer=issuer,
        request_hash=decision_req_hash,
        capability_hash=cap_hash,
        policy_id=pol_id,
        policy_version=pol_ver,
        outcome=outcome_str,
        risk_level=risk_str,
        evaluated_at=eval_at,
        secret_key=secret_key,
    )

    if not hmac.compare_digest(token, expected_token):
        return False, "Integrity token verification failed: decision has been forged or tampered with"

    # Check staleness
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
    ActionRequest -> Capability evaluation -> OPA/Policy evaluation -> Sealed Decision.
    """

    def __init__(self, secret_key: Optional[bytes] = None):
        self._secret_key = secret_key or _SCLASS_INTERNAL_AUTH_SECRET

    def mint_approval_token(self, request: ActionRequest, approver: str = "operator") -> str:
        """Mints a verifiable S-Class approval token for a specific ActionRequest."""
        req_hash = compute_canonical_request_hash(request)
        ts = datetime.now(timezone.utc).isoformat()
        payload = f"APPROVED:{approver}:{req_hash}:{ts}"
        sig = hmac.new(self._secret_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{approver}:{ts}:{sig}"

    def verify_approval_token(self, token: str, request: ActionRequest) -> bool:
        """Verifies that an approval token was genuinely minted by S-Class for this request."""
        if not token or not isinstance(token, str):
            return False
        parts = token.split(":")
        if len(parts) != 3:
            return False
        approver, ts, sig = parts
        req_hash = compute_canonical_request_hash(request)
        payload = f"APPROVED:{approver}:{req_hash}:{ts}"
        expected_sig = hmac.new(self._secret_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected_sig)

    def seal_decision(
        self,
        request: ActionRequest,
        outcome: DecisionOutcome,
        policy_id: str,
        risk_level: str,
        reason: str,
        remediation: Optional[str] = None,
        capability: Optional[Capability] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuthorizationDecision:
        """Constructs and cryptographically seals a canonical AuthorizationDecision."""
        now_iso = datetime.now(timezone.utc).isoformat()
        req_hash = compute_canonical_request_hash(request)
        cap_hash = compute_canonical_capability_hash(capability)
        outcome_str = outcome.value if isinstance(outcome, DecisionOutcome) else str(outcome)

        token = generate_integrity_token(
            issuer="S_CLASS",
            request_hash=req_hash,
            capability_hash=cap_hash,
            policy_id=policy_id,
            policy_version="1.0.0",
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
            policy_version="1.0.0",
            integrity_token=token,
        )

    def authorize(
        self,
        request: ActionRequest,
        capability: Optional[Capability] = None,
        workspace_dir: str = "",
        policy_engine: Optional[Any] = None,
    ) -> AuthorizationDecision:
        """
        Authoritatively evaluates an ActionRequest across Capability, Policy, and Invariants.
        Returns a sealed, non-forgeable AuthorizationDecision.
        """
        if request is None:
            raise SecurityViolationError("NO AUTHORIZATION -> NO EXECUTION: ActionRequest cannot be None.")

        ws = os.path.abspath(workspace_dir or request.workspace or os.getcwd())

        # 1. Evaluate Capability if provided
        if capability is not None:
            cap_decision = capability.evaluate_request(request, ws)
            if not cap_decision.allowed:
                return self.seal_decision(
                    request=request,
                    outcome=DecisionOutcome.DENY,
                    policy_id=cap_decision.matched_policy,
                    risk_level=str(capability.risk),
                    reason=f"Capability constraint violation: {cap_decision.explanation}",
                    remediation="Request requires a capability with expanded privileges or valid approval.",
                    capability=capability,
                    metadata={"failed_constraints": cap_decision.failed_constraints},
                )

        # 2. Evaluate Policy Engine
        if policy_engine is not None:
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
                capability=capability,
            )

        raw_outcome = getattr(raw_decision, "outcome", None)
        if isinstance(raw_outcome, DecisionOutcome):
            outcome = raw_outcome
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
            capability=capability,
            metadata=meta,
        )

    def verify_decision(
        self,
        decision: Any,
        request: ActionRequest,
        max_age_seconds: float = 3600.0,
    ) -> bool:
        """Verifies an AuthorizationDecision against this service's secret key."""
        valid, _ = verify_decision_integrity(
            decision=decision,
            request=request,
            secret_key=self._secret_key,
            max_age_seconds=max_age_seconds,
        )
        return valid
