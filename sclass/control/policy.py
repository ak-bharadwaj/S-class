"""
S-Class Control: Policy Engine Protocol and Default Security Rules.
"""

from __future__ import annotations
import os
from typing import Protocol, runtime_checkable, Optional, Dict, Any, List

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.control.authority import get_path_authority, PathAuthorityLevel
from sclass.control.secret_scanner import SecretScanner


@runtime_checkable
class PolicyEngine(Protocol):
    """Protocol for policy evaluation engines (OPA, Cedar, or native S-Class)."""

    def evaluate(self, request: ActionRequest, workspace_dir: str, mode: str = "enforce") -> AuthorizationDecision:
        """Evaluates an ActionRequest and returns an authoritative AuthorizationDecision."""
        ...


class DefaultPolicyEngine:
    """Built-in deterministic policy engine for local workspace authority."""

    def evaluate(self, request: ActionRequest, workspace_dir: str, mode: str = "enforce") -> AuthorizationDecision:
        ws = os.path.abspath(workspace_dir or request.workspace or os.getcwd())

        # 1. Check path authority if target is specified
        if request.target:
            authority = get_path_authority(request.target, ws)
            if authority == PathAuthorityLevel.SCLASS_ONLY:
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY if mode == "enforce" else DecisionOutcome.WARN,
                    policy_id="SCLASS-EVID-001",
                    risk_level="CRITICAL",
                    reason=f"Target path '{request.target}' is protected under SCLASS_ONLY authority.",
                    remediation="Direct modification of S-Class state or ledger files by external agents is forbidden.",
                )

        # 2. Check secret exposure in parameters / content
        params_str = str(request.parameters)
        has_secrets, _, findings = SecretScanner.scan(params_str)
        if has_secrets:
            high_conf = [f for f in findings if f["confidence"] == "HIGH_CONFIDENCE"]
            if high_conf:
                fps = ", ".join(f["fingerprint"] for f in high_conf)
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY if mode == "enforce" else DecisionOutcome.WARN,
                    policy_id="SCLASS-SEC-001",
                    risk_level="HIGH",
                    reason=f"High-confidence credential detected in action parameters (fingerprint(s): {fps}). Value redacted.",
                    remediation="Do not hardcode secrets or private keys in source files or parameters.",
                )

        # 3. Check dangerous shell chaining if action is command execution
        if request.action in ("shell.execute", "execute", "run_command"):
            cmd = request.parameters.get("command") or request.target or ""
            if any(op in cmd for op in (";", "&&", "||", "|", "`", "$(")):
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY if mode == "enforce" else DecisionOutcome.WARN,
                    policy_id="SCLASS-SEC-003",
                    risk_level="HIGH",
                    reason="Command contains forbidden shell injection or chaining operators.",
                    remediation="Execute commands with single arguments or without shell chaining.",
                )

        # 4. Default: Allow
        return AuthorizationDecision(
            outcome=DecisionOutcome.ALLOW,
            policy_id="SCLASS-CORE-DEFAULT",
            risk_level="LOW",
            reason="Operation authorized under standard workspace policy.",
        )
