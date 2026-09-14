"""
S-Class Control: Policy Engine Protocol and Authoritative Security Rules.
Separates S-Class policy semantics (ALLOW, WARN, REQUIRE_APPROVAL, DENY) from backends.
Provides DefaultPolicyEngine and OPAEngine with deep context awareness.
"""

from __future__ import annotations
import os
import shlex
from typing import Protocol, runtime_checkable, Optional, Dict, Any, List
from dataclasses import dataclass, field

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.control.authority import get_path_authority, PathAuthorityLevel
from sclass.control.resources import classify_resource, AuthorityBoundary, ResourceKind
from sclass.control.capabilities import Capability
from sclass.execution.modes import check_protected_resource_targeting, ExecutionMode
from sclass.control.secret_scanner import SecretScanner


@dataclass(frozen=True)
class PolicyContext:
    """Rich execution context for authoritative policy decisions."""
    agent: str
    platform: str
    task: Optional[str]
    action: str
    resource: str
    workspace: str
    execution_mode: str = ExecutionMode.HOST_ARGV.value
    risk: str = "LOW"
    blast_radius: Optional[Dict[str, Any]] = None
    repository_state: Optional[str] = None
    previous_verification: Optional[str] = None
    network_access: bool = False
    protected_resource: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "platform": self.platform,
            "task": self.task,
            "action": self.action,
            "resource": self.resource,
            "workspace": self.workspace,
            "execution_mode": self.execution_mode,
            "risk": self.risk,
            "blast_radius": self.blast_radius,
            "repository_state": self.repository_state,
            "previous_verification": self.previous_verification,
            "network_access": self.network_access,
            "protected_resource": self.protected_resource,
        }


@runtime_checkable
class PolicyEngine(Protocol):
    """Protocol for policy evaluation engines."""

    def evaluate(self, request: ActionRequest, workspace_dir: str, mode: str = "enforce") -> AuthorizationDecision:
        """Evaluates an ActionRequest and returns an authoritative AuthorizationDecision."""
        ...


class DefaultPolicyEngine:
    """Built-in deterministic policy engine with capability and protected resource gating."""

    def evaluate(self, request: ActionRequest, workspace_dir: str, mode: str = "enforce") -> AuthorizationDecision:
        ws = os.path.abspath(workspace_dir or request.workspace or os.getcwd())

        # 1. Protected resource analysis on target path (for filesystem actions)
        if request.target and request.action not in ("shell.execute", "execute", "run_command"):
            r_kind, boundary = classify_resource(request.target, ws)
            if r_kind == ResourceKind.SECRET:
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY if mode == "enforce" else DecisionOutcome.WARN,
                    policy_id="SCLASS-SEC-SECRET",
                    risk_level="CRITICAL",
                    reason=f"Target path '{request.target}' is a secret/credential resource.",
                    remediation="Access to secrets (.env, keys, credentials) is strictly prohibited.",
                )
            if boundary in (AuthorityBoundary.SCLASS_TRUST_ROOT, AuthorityBoundary.SCLASS_VERIFICATION_ONLY):
                # Agents may not mutate trust roots or evidence
                if request.action in ("write_file", "delete_file", "edit_file", "unlink", "truncate", "modify"):

                    return AuthorizationDecision(
                        outcome=DecisionOutcome.DENY if mode == "enforce" else DecisionOutcome.WARN,
                        policy_id="SCLASS-AUTH-001",
                        risk_level="CRITICAL",
                        reason=f"Target path '{request.target}' is protected under boundary {boundary.value}.",
                        remediation="Trust state and evidence files are strictly non-agent-writable.",
                    )

            # Legacy path authority check
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

        # 3. Check commands for protected resource references and dangerous shell chaining
        if request.action in ("shell.execute", "execute", "run_command"):
            cmd = request.parameters.get("command") or request.target or ""

            # Check protected resource targeting
            is_targeted, reason = check_protected_resource_targeting(cmd)
            if is_targeted:
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY if mode == "enforce" else DecisionOutcome.WARN,
                    policy_id="SCLASS-SEC-002",
                    risk_level="CRITICAL",
                    reason=f"Command references protected S-Class resource: {reason}",
                    remediation="Agent processes cannot access or alter .sclass trust state.",
                )

            # Check dangerous destructive commands (e.g. rm -rf /, format, wipe)
            cmd_clean = " ".join(cmd.split()).lower()
            dangerous_patterns = (
                "rm -rf /", "rm -rf /*", "rm -rf ~", "rm -rf $home", "rm -r -f /",
                "rmdir /s /q c:\\", "rmdir /s /q c:/", "del /f /s /q c:\\",
                ":(){ :|:& };:", "mkfs", "dd if=", "> /dev/sda",
            )
            for dp in dangerous_patterns:
                if dp in cmd_clean or cmd_clean.startswith(dp):
                    return AuthorizationDecision(
                        outcome=DecisionOutcome.DENY if mode == "enforce" else DecisionOutcome.WARN,
                        policy_id="SCLASS-SEC-DANGEROUS",
                        risk_level="CRITICAL",
                        reason=f"Dangerous destructive command pattern detected: '{cmd}'",
                        remediation="Destructive filesystem commands are strictly forbidden by policy.",
                    )

            # Check dangerous shell chaining if not explicitly permitted

            exec_mode = request.parameters.get("mode") or request.context.get("mode", ExecutionMode.HOST_ARGV.value)
            if exec_mode != ExecutionMode.HOST_SHELL.value:
                if any(op in cmd for op in (";", "&&", "||", "|", "`", "$(")):
                    return AuthorizationDecision(
                        outcome=DecisionOutcome.DENY if mode == "enforce" else DecisionOutcome.WARN,
                        policy_id="SCLASS-SEC-003",
                        risk_level="HIGH",
                        reason="Command contains forbidden shell injection or chaining operators.",
                        remediation="Execute commands with single arguments or without shell chaining.",
                    )
            else:
                # HOST_SHELL mode requires approval
                return AuthorizationDecision(
                    outcome=DecisionOutcome.REQUIRE_APPROVAL if mode == "enforce" else DecisionOutcome.WARN,
                    policy_id="SCLASS-MODE-001",
                    risk_level="HIGH",
                    reason="HOST_SHELL command execution requires explicit approval under shell policy.",
                    remediation="Confirm approval to execute host shell process.",
                )

        # 4. Default: Allow
        return AuthorizationDecision(
            outcome=DecisionOutcome.ALLOW,
            policy_id="SCLASS-CORE-DEFAULT",
            risk_level="LOW",
            reason="Operation authorized under standard workspace policy.",
        )


class OPAEngine:
    """OPA policy evaluation backend with local DefaultPolicyEngine fallback."""

    def __init__(self, endpoint_url: Optional[str] = None):
        self.endpoint_url = endpoint_url or os.environ.get("SCLASS_OPA_URL", "http://localhost:8181/v1/data/sclass/authz")
        self.fallback = DefaultPolicyEngine()

    def evaluate(self, request: ActionRequest, workspace_dir: str, mode: str = "enforce") -> AuthorizationDecision:
        try:
            import requests
            payload = {"input": request.to_dict()}
            resp = requests.post(self.endpoint_url, json=payload, timeout=1.0)
            if resp.status_code == 200:
                data = resp.json().get("result", {})
                allow = data.get("allow", True)
                if not allow:
                    return AuthorizationDecision(
                        outcome=DecisionOutcome.DENY if mode == "enforce" else DecisionOutcome.WARN,
                        policy_id=data.get("policy_id", "OPA-DENY"),
                        risk_level="HIGH",
                        reason=data.get("reason", "Denied by external OPA engine"),
                    )
                return AuthorizationDecision(
                    outcome=DecisionOutcome.ALLOW,
                    policy_id="OPA-ALLOW",
                    risk_level="LOW",
                    reason="Allowed by external OPA engine",
                )
        except Exception:
            pass
        return self.fallback.evaluate(request, workspace_dir, mode)
