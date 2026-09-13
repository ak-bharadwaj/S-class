"""
S-Class Domain: ActionRequest, Capability, and AuthorizationDecision.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, Union

from sclass.domain.capability import (
    Capability,
    CAP_TERMINAL_EXECUTE,
    CAP_FILESYSTEM_READ,
    CAP_FILESYSTEM_WRITE,
    CAP_GIT_READ,
    CAP_GIT_WRITE,
    CAP_NETWORK_REQUEST,
    CAP_SECRET_READ,
    CAP_PROCESS_SPAWN,
)


class DecisionOutcome(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


@dataclass(frozen=True, init=False)
class ActionRequest:
    """
    Canonical typed request for an agent or tool action before execution.
    Unified across ACP terminal/fs, MCP tools/call, Claude, Codex, Cursor, OpenCode, and CLI.
    """
    actor: str
    session: str
    capability: str
    action: str
    target: str
    parameters: Dict[str, Any]
    workspace: str
    context: Dict[str, Any]
    provenance: Dict[str, Any]

    def __init__(
        self,
        actor: Optional[str] = None,
        session: Optional[str] = None,
        capability: Optional[str] = None,
        action: Optional[str] = None,
        target: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        workspace: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        provenance: Optional[Dict[str, Any]] = None,
        *,
        agent: Optional[str] = None,
        platform: Optional[str] = None,
        tool: Optional[str] = None,
        task_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ):
        final_actor = actor if actor is not None else (agent if agent is not None else "unknown_actor")
        final_session = session if session is not None else (task_id if task_id is not None else "")
        final_capability = capability if capability is not None else (tool if tool is not None else (action or ""))
        final_action = action if action is not None else (tool if tool is not None else "unknown_action")
        final_target = target if target is not None else ""
        final_parameters = dict(parameters) if parameters is not None else {}
        final_workspace = workspace if workspace is not None else ""
        final_context = dict(context) if context is not None else {}

        prov = dict(provenance) if provenance is not None else {}
        if platform is not None and "platform" not in prov:
            prov["platform"] = platform
        elif "platform" not in prov:
            prov["platform"] = "generic"

        if timestamp is not None and "timestamp" not in prov:
            prov["timestamp"] = timestamp
        elif "timestamp" not in prov:
            prov["timestamp"] = datetime.now(timezone.utc).isoformat()

        object.__setattr__(self, "actor", final_actor)
        object.__setattr__(self, "session", final_session)
        object.__setattr__(self, "capability", final_capability)
        object.__setattr__(self, "action", final_action)
        object.__setattr__(self, "target", final_target)
        object.__setattr__(self, "parameters", final_parameters)
        object.__setattr__(self, "workspace", final_workspace)
        object.__setattr__(self, "context", final_context)
        object.__setattr__(self, "provenance", prov)

    # Backwards-compatible aliases
    @property
    def agent(self) -> str:
        return self.actor

    @property
    def platform(self) -> str:
        return self.provenance.get("platform", "generic")

    @property
    def tool(self) -> str:
        return self.capability or self.action

    @property
    def task_id(self) -> Optional[str]:
        return self.session or None

    @property
    def timestamp(self) -> str:
        return self.provenance.get("timestamp", "")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor": self.actor,
            "session": self.session,
            "capability": self.capability,
            "action": self.action,
            "target": self.target,
            "parameters": dict(self.parameters),
            "workspace": self.workspace,
            "context": dict(self.context),
            "provenance": dict(self.provenance),
            # Backwards compatibility fields
            "agent": self.actor,
            "platform": self.platform,
            "tool": self.tool,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ActionRequest:
        prov = dict(data.get("provenance", {}))
        if "platform" in data and "platform" not in prov:
            prov["platform"] = data["platform"]
        if "timestamp" in data and "timestamp" not in prov:
            prov["timestamp"] = data["timestamp"]

        return cls(
            actor=data.get("actor") or data.get("agent", "unknown_actor"),
            session=data.get("session") or data.get("task_id", ""),
            capability=data.get("capability") or data.get("tool", ""),
            action=data.get("action", "unknown_action"),
            target=data.get("target", ""),
            parameters=dict(data.get("parameters", {})),
            workspace=data.get("workspace", ""),
            context=dict(data.get("context", {})),
            provenance=prov,
            agent=data.get("agent"),
            platform=data.get("platform"),
            tool=data.get("tool"),
            task_id=data.get("task_id"),
            timestamp=data.get("timestamp"),
        )


@dataclass(frozen=True)
class AuthorizationDecision:
    """Canonical authorization decision emitted by S-Class policy engine."""
    outcome: DecisionOutcome
    policy_id: str
    risk_level: str
    reason: str
    remediation: Optional[str] = None
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    issuer: str = "S_CLASS"
    request_hash: str = ""
    capability_hash: str = ""
    policy_version: str = "1.0.0"
    integrity_token: str = ""

    @property
    def is_allowed(self) -> bool:
        return self.outcome in (DecisionOutcome.ALLOW, DecisionOutcome.WARN)

    @property
    def is_denied(self) -> bool:
        return self.outcome == DecisionOutcome.DENY

    @property
    def is_warned(self) -> bool:
        return self.outcome == DecisionOutcome.WARN

    @property
    def requires_approval(self) -> bool:
        return self.outcome == DecisionOutcome.REQUIRE_APPROVAL

    def verify_integrity(self, secret_key: Optional[bytes] = None) -> bool:
        """Verifies HMAC integrity token of this decision."""
        if not self.integrity_token:
            return False
        import hmac
        import hashlib
        key = secret_key or os.environ.get("SCLASS_AUTH_SECRET", "sclass-internal-authoritative-auth-token-secret-v1").encode("utf-8")
        out_str = self.outcome.value if isinstance(self.outcome, DecisionOutcome) else str(self.outcome)
        payload = f"{self.issuer}:{self.request_hash}:{self.capability_hash}:{self.policy_id}:{self.policy_version}:{out_str}:{self.risk_level}:{self.evaluated_at}"
        expected = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(self.integrity_token, expected)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value if isinstance(self.outcome, DecisionOutcome) else str(self.outcome),
            "policy_id": self.policy_id,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "remediation": self.remediation,
            "evaluated_at": self.evaluated_at,
            "metadata": dict(self.metadata),
            "issuer": self.issuer,
            "request_hash": self.request_hash,
            "capability_hash": self.capability_hash,
            "policy_version": self.policy_version,
            "integrity_token": self.integrity_token,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AuthorizationDecision:
        raw_outcome = data.get("outcome", "deny")
        try:
            outcome = DecisionOutcome(raw_outcome)
        except ValueError:
            outcome = DecisionOutcome.DENY

        return cls(
            outcome=outcome,
            policy_id=data.get("policy_id", "default_policy"),
            risk_level=data.get("risk_level", "medium"),
            reason=data.get("reason", ""),
            remediation=data.get("remediation"),
            evaluated_at=data.get("evaluated_at", datetime.now(timezone.utc).isoformat()),
            metadata=dict(data.get("metadata", {})),
            issuer=data.get("issuer", "S_CLASS"),
            request_hash=data.get("request_hash", ""),
            capability_hash=data.get("capability_hash", ""),
            policy_version=data.get("policy_version", "1.0.0"),
            integrity_token=data.get("integrity_token", ""),
        )

