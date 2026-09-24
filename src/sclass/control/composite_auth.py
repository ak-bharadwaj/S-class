"""
S-Class Control: Dual-Layer Authorization (S-Class + Step-Code Runtime Permissions).
Enforces Section 10:
Agent asks for action -> S-Class policy authorization -> Runtime permission analysis -> execution.

Invariants:
1. S-Class deny always blocks execution.
2. Runtime deny also blocks execution.
3. S-Class allow cannot bypass runtime restrictions.
4. Modified action after authorization requires a new authorization (action hash binding).
5. Runtime permission != S-Class authorization.
"""

from __future__ import annotations
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.control.authorization import authorize, get_policy_engine
from sclass.control.policy import PolicyEngine
from sclass.execution.harness import StepCodeCommandAnalyzer
from sclass.execution.operations import compute_action_hash
from sclass.core.errors import SecurityViolationError


@dataclass(frozen=True)
class CompositeAuthResult:
    """Consolidated outcome of the dual-layer authorization evaluation."""
    sclass_allowed: bool
    runtime_allowed: bool
    can_execute: bool
    sclass_reason: str
    runtime_reason: str
    action_hash: str
    authorized_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sclass_allowed": self.sclass_allowed,
            "runtime_allowed": self.runtime_allowed,
            "can_execute": self.can_execute,
            "sclass_reason": self.sclass_reason,
            "runtime_reason": self.runtime_reason,
            "action_hash": self.action_hash,
            "authorized_at": self.authorized_at,
        }


def _parse_iso_utc(ts: str) -> datetime:
    clean = (ts or "").strip()
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception as e:
        raise SecurityViolationError(f"Corrupt authorization timestamp '{ts}': {e}")


class DualLayerAuthorizer:
    """
    Coordinates S-Class governance authorization and lower runtime permission analysis.
    """

    @classmethod
    def authorize_request(
        cls,
        action: ActionRequest,
        workspace_dir: Optional[str] = None,
        engine: Optional[PolicyEngine] = None,
    ) -> AuthorizationDecision:
        """
        Computes S-Class authorization and embeds the cryptographic action_hash.
        """
        ws = workspace_dir or action.workspace or os.getcwd()
        decision = authorize(action, workspace_dir=ws, engine=engine)

        from sclass.policy.authorization_service import (
            compute_canonical_request_hash,
            generate_integrity_token,
            get_authorization_secret,
        )

        act_hash = compute_action_hash(action.capability, action.action, action.target, action.parameters)
        req_hash = decision.request_hash or compute_canonical_request_hash(action)

        new_meta = dict(decision.metadata or {})
        new_meta["action_hash"] = act_hash
        new_meta["request_hash"] = req_hash

        task_id = action.task_id or action.session or ""
        session_id = action.session or ""
        workspace_id = ws

        cap_id = decision.capability_id or action.capability or action.action or ""
        cap_hash = decision.capability_hash or ""
        cap_ver = decision.capability_version or "1.0.0"
        reg_gen = decision.capability_registry_generation or 0
        pol_id = decision.policy_id or "SCLASS-CORE-DEFAULT"
        pol_ver = decision.policy_version or "1.0.0"
        eval_at = decision.evaluated_at or datetime.now(timezone.utc).isoformat()
        outcome_str = decision.outcome.value if isinstance(decision.outcome, DecisionOutcome) else str(decision.outcome)
        risk_str = decision.risk_level or "LOW"

        token = generate_integrity_token(
            issuer="S_CLASS",
            request_hash=req_hash,
            capability_hash=cap_hash,
            capability_id=cap_id,
            capability_version=cap_ver,
            registry_generation=reg_gen,
            policy_id=pol_id,
            policy_version=pol_ver,
            outcome=outcome_str,
            risk_level=risk_str,
            evaluated_at=eval_at,
            action_hash=act_hash,
            workspace_id=workspace_id,
            task_id=task_id,
            session_id=session_id,
        )

        return AuthorizationDecision(
            outcome=decision.outcome,
            policy_id=pol_id,
            risk_level=risk_str,
            reason=decision.reason,
            remediation=decision.remediation,
            evaluated_at=eval_at,
            metadata=new_meta,
            issuer="S_CLASS",
            request_hash=req_hash,
            action_hash=act_hash,
            capability_hash=cap_hash,
            capability_id=cap_id,
            capability_version=cap_ver,
            capability_registry_generation=reg_gen,
            policy_version=pol_ver,
            integrity_token=token,
            decision_id=decision.decision_id or f"dec_{uuid.uuid4().hex[:8]}",
            request_id=decision.request_id or f"req_{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            workspace_id=workspace_id,
            session_id=session_id,
            obligations=decision.obligations,
            required_claims=decision.required_claims,
        )

    @classmethod
    def evaluate_dual_layer(
        cls,
        action: ActionRequest,
        sclass_decision: AuthorizationDecision,
        workspace_dir: str = "",
    ) -> CompositeAuthResult:
        """
        Evaluates the dual-layer authorization hierarchy (Section 4, 5, 6, 7, 10).
        """
        if sclass_decision is None or not isinstance(sclass_decision, AuthorizationDecision):
            raise SecurityViolationError("Malformed authorization decision: expected valid AuthorizationDecision instance")

        ws = workspace_dir or action.workspace or os.getcwd()

        # Step 1: Verify Issuer Authenticity
        if sclass_decision.issuer != "S_CLASS":
            raise SecurityViolationError(f"Untrusted issuer '{sclass_decision.issuer}': only S-Class issued decisions are authoritative")

        # Step 2: Verify Action Hash Integrity (Section 4 & 5)
        current_act_hash = compute_action_hash(action.capability, action.action, action.target, action.parameters)
        signed_act_hash = sclass_decision.action_hash or (sclass_decision.metadata.get("action_hash") if sclass_decision.metadata else None)

        if signed_act_hash and signed_act_hash != current_act_hash:
            raise SecurityViolationError(
                f"ACTION MODIFIED AFTER AUTHORIZATION: Current action hash '{current_act_hash}' "
                f"does not match authorized action hash '{signed_act_hash}'. Execution is blocked until re-authorized."
            )

        # Step 3: Verify Request Hash Integrity (Section 5)
        from sclass.policy.authorization_service import compute_canonical_request_hash
        current_req_hash = compute_canonical_request_hash(action)
        if sclass_decision.request_hash and sclass_decision.request_hash != current_req_hash:
            raise SecurityViolationError(
                f"REQUEST HASH MISMATCH: Decision bound to '{sclass_decision.request_hash}', "
                f"but action request hash is '{current_req_hash}'. Execution blocked fail-closed."
            )

        # Step 3b: Verify Capability Binding (Section 4 & 7)
        if sclass_decision.capability_id and action.capability:
            from sclass.policy.capability_resolver import CapabilityRegistry
            reg = CapabilityRegistry()
            cap = reg.get(sclass_decision.capability_id)
            if cap:
                if not cap.allows_operation(action.capability) and sclass_decision.capability_id != action.capability:
                    raise SecurityViolationError(
                        f"CAPABILITY MISMATCH: Decision bound to capability '{sclass_decision.capability_id}', "
                        f"which does not permit requested action capability '{action.capability}'."
                    )
            elif sclass_decision.capability_id != action.capability:
                raise SecurityViolationError(
                    f"CAPABILITY MISMATCH: Decision bound to capability '{sclass_decision.capability_id}', "
                    f"but action requested '{action.capability}'."
                )

        # Step 4: Verify Scope Bindings (Section 7: task_id, session_id, workspace_id)
        if sclass_decision.workspace_id and ws:
            dec_ws = os.path.normpath(sclass_decision.workspace_id).lower()
            curr_ws = os.path.normpath(ws).lower()
            if dec_ws != curr_ws:
                raise SecurityViolationError(
                    f"AUTHORIZATION SCOPE VIOLATION: Decision bound to workspace '{sclass_decision.workspace_id}', "
                    f"but attempted execution is in workspace '{ws}'."
                )

        dec_task = sclass_decision.task_id or (sclass_decision.metadata.get("task_id") if sclass_decision.metadata else "")
        req_task = action.task_id or ""
        if dec_task and req_task and dec_task != req_task:
            raise SecurityViolationError(
                f"AUTHORIZATION SCOPE VIOLATION: Decision bound to task '{dec_task}', "
                f"but attempted execution is for task '{req_task}'."
            )

        dec_session = sclass_decision.session_id or (sclass_decision.metadata.get("session_id") if sclass_decision.metadata else "")
        if dec_session and action.session and dec_session != action.session:
            raise SecurityViolationError(
                f"AUTHORIZATION SCOPE VIOLATION: Decision bound to session '{dec_session}', "
                f"but attempted execution is for session '{action.session}'."
            )

        # Step 5: Verify Policy Version and Generation (Section 4)
        if sclass_decision.policy_version and sclass_decision.policy_version != "1.0.0":
            raise SecurityViolationError(
                f"POLICY VERSION MISMATCH: Decision bound to policy version '{sclass_decision.policy_version}', "
                "expected active policy version '1.0.0'."
            )

        # Step 6: Verify Freshness / Expiration
        if sclass_decision.evaluated_at:
            try:
                eval_dt = _parse_iso_utc(sclass_decision.evaluated_at)
                age = (datetime.now(timezone.utc) - eval_dt).total_seconds()
                if age < -30.0:
                    raise SecurityViolationError(f"AUTHORIZATION EXPIRED: Future timestamp exceeding allowable skew limit ({age:.1f}s).")
                if age > 3600.0:
                    raise SecurityViolationError(f"AUTHORIZATION EXPIRED: Decision age {age:.1f}s exceeds 3600s TTL.")
            except SecurityViolationError:
                raise
            except Exception as e:
                raise SecurityViolationError(f"AUTHORIZATION EXPIRED: Invalid evaluated_at timestamp: {e}")

        # Step 7: Cryptographic HMAC Token Verification (Section 4 & 4.1)
        if sclass_decision.integrity_token:
            if not sclass_decision.verify_integrity():
                raise SecurityViolationError("INVALID HMAC INTEGRITY TOKEN: Decision has been forged, tampered with, or altered.")

        # Step 8: S-Class Authorization Outcome Check (Section 6: WARN MUST NEVER EXECUTE)
        # ALLOW -> executable, subject to all other gates
        # WARN -> non-executable until explicit approval
        # REQUIRE_APPROVAL -> non-executable until explicit approval
        # DENY -> non-executable
        if sclass_decision.outcome == DecisionOutcome.ALLOW:
            if not sclass_decision.integrity_token:
                sclass_allowed = False
                sclass_reason = "DENIED: Missing cryptographic HMAC integrity token on ALLOW decision"
            elif not signed_act_hash or not sclass_decision.request_hash:
                sclass_allowed = False
                sclass_reason = "DENIED: Missing request or action hash on ALLOW authorization decision"
            else:
                sclass_allowed = True
                sclass_reason = sclass_decision.reason or "Authorized by S-Class policy"
        elif sclass_decision.outcome == DecisionOutcome.WARN:
            sclass_allowed = False
            sclass_reason = f"WARN: Non-executable until explicit approval: {sclass_decision.reason}"
        elif sclass_decision.outcome == DecisionOutcome.REQUIRE_APPROVAL:
            sclass_allowed = False
            sclass_reason = f"REQUIRE_APPROVAL: Non-executable until explicit approval: {sclass_decision.reason}"
        else:
            sclass_allowed = False
            sclass_reason = sclass_decision.reason or "DENY: S-Class policy denied execution"

        # Step 9: Runtime Permission Analysis (Step-Code command safety layer)
        cmd_str = action.parameters.get("command") or action.parameters.get("command_line") or action.target or ""
        runtime_analysis = StepCodeCommandAnalyzer.analyze_command(cmd_str, ws)
        runtime_allowed = bool(runtime_analysis.get("allowed", False))
        runtime_reason = runtime_analysis.get("reason", "")

        # Step 10: Strict Conjunction Gate (Section 10)
        # S-Class deny -> execution denied
        # S-Class allow, runtime deny -> execution denied
        # Both allow -> execution may proceed
        can_execute = bool(sclass_allowed and runtime_allowed)

        return CompositeAuthResult(
            sclass_allowed=sclass_allowed,
            runtime_allowed=runtime_allowed,
            can_execute=can_execute,
            sclass_reason=sclass_reason,
            runtime_reason=runtime_reason,
            action_hash=current_act_hash,
        )
