"""
S-Class Domain: ActionRequest, Capability, and AuthorizationDecision.
"""

from __future__ import annotations
import os
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
    task_id: str

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
        final_task_id = task_id if task_id is not None else (session if session is not None else "")
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
        object.__setattr__(self, "task_id", final_task_id)
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
    def timestamp(self) -> str:
        return self.provenance.get("timestamp", "")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor": self.actor,
            "session": self.session,
            "task_id": self.task_id,
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
            "timestamp": self.timestamp,
        }

    def compute_action_hash(self) -> str:
        """Computes deterministic cryptographic hash of the action parameters."""
        from sclass.execution.operations import compute_action_hash
        return compute_action_hash(self.capability, self.action, self.target, self.parameters, workspace_dir=self.workspace)

    def compute_request_hash(self) -> str:
        """Computes canonical request hash binding actor, session, capability, action, target, parameters, workspace."""
        from sclass.policy.authorization_service import compute_canonical_request_hash
        return compute_canonical_request_hash(self)

    def compute_hash(self) -> str:
        """Computes deterministic cryptographic hash of the action request (backwards compatibility)."""
        return self.compute_action_hash()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ActionRequest:
        prov = dict(data.get("provenance", {}))
        if "platform" in data and "platform" not in prov:
            prov["platform"] = data["platform"]
        if "timestamp" in data and "timestamp" not in prov:
            prov["timestamp"] = data["timestamp"]

        return cls(
            actor=data.get("actor") or data.get("agent", "unknown_actor"),
            session=data.get("session", ""),
            task_id=data.get("task_id", ""),
            capability=data.get("capability") or data.get("tool", ""),
            action=data.get("action") or data.get("tool", "unknown_action"),
            target=data.get("target", ""),
            parameters=data.get("parameters", {}),
            workspace=data.get("workspace", ""),
            context=data.get("context", {}),
            provenance=prov,
        )


@dataclass(frozen=True)
class AuthorizationDecision:
    """Canonical authorization decision emitted by S-Class policy engine."""
    outcome: DecisionOutcome
    policy_id: str = "default_policy"
    risk_level: str = "medium"
    reason: str = ""
    remediation: Optional[str] = None
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    issuer: str = "S_CLASS"
    request_hash: str = ""
    action_hash: str = ""
    capability_hash: str = ""
    capability_id: str = ""
    capability_version: str = "1.0.0"
    capability_registry_generation: int = 0
    policy_version: str = "1.0.0"
    integrity_token: str = ""
    decision_id_override: Optional[str] = None
    request_id_override: Optional[str] = None
    task_id: str = ""
    workspace_id: str = ""
    session_id: str = ""
    operation_id: str = ""
    obligations: Tuple[str, ...] = field(default_factory=tuple)
    required_claims: Tuple[str, ...] = field(default_factory=tuple)

    def __init__(
        self,
        outcome: DecisionOutcome,
        policy_id: str = "default_policy",
        risk_level: str = "medium",
        reason: str = "",
        remediation: Optional[str] = None,
        evaluated_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        issuer: str = "S_CLASS",
        request_hash: str = "",
        capability_hash: str = "",
        capability_id: str = "",
        capability_version: str = "1.0.0",
        capability_registry_generation: int = 0,
        policy_version: str = "1.0.0",
        integrity_token: str = "",
        *,
        action_hash: Optional[str] = None,
        task_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        session_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        request_id: Optional[str] = None,
        created_at: Optional[str] = None,
        obligations: Optional[Union[List[str], Tuple[str, ...]]] = None,
        required_claims: Optional[Union[List[str], Tuple[str, ...]]] = None,
    ):
        meta = dict(metadata or {})
        if decision_id:
            meta["decision_id"] = decision_id
        if request_id:
            meta["request_id"] = request_id
        eval_time = evaluated_at or created_at or datetime.now(timezone.utc).isoformat()
        act_hash = action_hash or meta.get("action_hash", "")
        t_id = task_id or meta.get("task_id", "")
        ws_id = workspace_id or meta.get("workspace_id", "")
        s_id = session_id or meta.get("session_id", "")
        op_id = operation_id or meta.get("operation_id", "")

        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "policy_id", policy_id)
        object.__setattr__(self, "risk_level", risk_level)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "remediation", remediation)
        object.__setattr__(self, "evaluated_at", eval_time)
        object.__setattr__(self, "metadata", meta)
        object.__setattr__(self, "issuer", issuer)
        object.__setattr__(self, "request_hash", request_hash)
        object.__setattr__(self, "action_hash", act_hash)
        object.__setattr__(self, "capability_hash", capability_hash)
        object.__setattr__(self, "capability_id", capability_id)
        object.__setattr__(self, "capability_version", capability_version)
        object.__setattr__(self, "capability_registry_generation", capability_registry_generation)
        object.__setattr__(self, "policy_version", policy_version)
        object.__setattr__(self, "integrity_token", integrity_token)
        object.__setattr__(self, "decision_id_override", decision_id)
        object.__setattr__(self, "request_id_override", request_id)
        object.__setattr__(self, "task_id", t_id)
        object.__setattr__(self, "workspace_id", ws_id)
        object.__setattr__(self, "session_id", s_id)
        object.__setattr__(self, "operation_id", op_id)
        object.__setattr__(self, "obligations", tuple(obligations or ()))
        object.__setattr__(self, "required_claims", tuple(required_claims or ()))

    @property
    def decision_id(self) -> str:
        return self.decision_id_override or self.metadata.get("decision_id", f"dec_{id(self)}")

    @property
    def request_id(self) -> str:
        return self.request_id_override or self.metadata.get("request_id", "")

    @property
    def created_at(self) -> str:
        return self.evaluated_at


    @property
    def allow(self) -> bool:
        return self.is_allowed

    @property
    def is_allowed(self) -> bool:
        # Enforce Section 6: WARN MUST NEVER EXECUTE. Only ALLOW is executable.
        return self.outcome == DecisionOutcome.ALLOW

    @property
    def is_denied(self) -> bool:
        return self.outcome == DecisionOutcome.DENY

    @property
    def is_warned(self) -> bool:
        return self.outcome == DecisionOutcome.WARN

    @property
    def requires_approval(self) -> bool:
        return self.outcome in (DecisionOutcome.WARN, DecisionOutcome.REQUIRE_APPROVAL)

    def verify_integrity(self, secret_key: Optional[bytes] = None) -> bool:
        """Verifies HMAC integrity token of this decision."""
        if not self.integrity_token:
            return False
        if not self.request_hash or not self.action_hash:
            return False
        import hmac
        import hashlib
        from sclass.policy.authorization_service import get_authorization_secret
        key = secret_key or get_authorization_secret()
        out_str = self.outcome.value if isinstance(self.outcome, DecisionOutcome) else str(self.outcome)
        ws_norm = os.path.normpath(self.workspace_id).replace("\\", "/") if self.workspace_id else ""
        payload_scoped = (
            f"{self.issuer}:{self.request_hash}:{self.action_hash}:{self.capability_hash}:"
            f"{self.capability_id}:{self.capability_version}:{self.capability_registry_generation}:"
            f"{self.policy_id}:{self.policy_version}:{out_str}:{self.risk_level}:{self.evaluated_at}:"
            f"{ws_norm}:{self.task_id or ''}:{self.session_id or ''}"
        )
        expected_scoped = hmac.new(key, payload_scoped.encode("utf-8"), hashlib.sha256).hexdigest()
        if hmac.compare_digest(self.integrity_token, expected_scoped):
            return True

        # Unscoped fallback only when scope identifiers are completely empty
        if not self.workspace_id and not self.task_id and not self.session_id:
            payload_with_act = f"{self.issuer}:{self.request_hash}:{self.action_hash}:{self.capability_hash}:{self.capability_id}:{self.capability_version}:{self.capability_registry_generation}:{self.policy_id}:{self.policy_version}:{out_str}:{self.risk_level}:{self.evaluated_at}"
            expected_with_act = hmac.new(key, payload_with_act.encode("utf-8"), hashlib.sha256).hexdigest()
            if hmac.compare_digest(self.integrity_token, expected_with_act):
                return True

            payload_legacy = f"{self.issuer}:{self.request_hash}:{self.capability_hash}:{self.capability_id}:{self.capability_version}:{self.capability_registry_generation}:{self.policy_id}:{self.policy_version}:{out_str}:{self.risk_level}:{self.evaluated_at}"
            expected_legacy = hmac.new(key, payload_legacy.encode("utf-8"), hashlib.sha256).hexdigest()
            if hmac.compare_digest(self.integrity_token, expected_legacy):
                return True

        return False

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
            "action_hash": self.action_hash,
            "capability_hash": self.capability_hash,
            "capability_id": self.capability_id,
            "capability_version": self.capability_version,
            "capability_registry_generation": self.capability_registry_generation,
            "policy_version": self.policy_version,
            "integrity_token": self.integrity_token,
            "task_id": self.task_id,
            "workspace_id": self.workspace_id,
            "session_id": self.session_id,
            "operation_id": self.operation_id,
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
            action_hash=data.get("action_hash") or data.get("metadata", {}).get("action_hash", ""),
            capability_hash=data.get("capability_hash", ""),
            capability_id=data.get("capability_id", ""),
            capability_version=data.get("capability_version", "1.0.0"),
            capability_registry_generation=int(data.get("capability_registry_generation", 0)),
            policy_version=data.get("policy_version", "1.0.0"),
            integrity_token=data.get("integrity_token", ""),
            task_id=data.get("task_id", ""),
            workspace_id=data.get("workspace_id", ""),
            session_id=data.get("session_id", ""),
            operation_id=data.get("operation_id", ""),
        )

