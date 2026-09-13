"""
S-Class Domain: ActionRequest and AuthorizationDecision.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional


class DecisionOutcome(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


@dataclass(frozen=True)
class ActionRequest:
    """Canonical typed request for an agent action before execution."""
    agent: str
    platform: str
    action: str
    tool: str
    target: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    workspace: str = ""
    task_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "platform": self.platform,
            "action": self.action,
            "tool": self.tool,
            "target": self.target,
            "parameters": dict(self.parameters),
            "workspace": self.workspace,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "context": dict(self.context),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ActionRequest:
        return cls(
            agent=data.get("agent", "unknown_agent"),
            platform=data.get("platform", "generic"),
            action=data.get("action", "unknown_action"),
            tool=data.get("tool", "unknown_tool"),
            target=data.get("target", ""),
            parameters=dict(data.get("parameters", {})),
            workspace=data.get("workspace", ""),
            task_id=data.get("task_id"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            context=dict(data.get("context", {})),
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value if isinstance(self.outcome, DecisionOutcome) else str(self.outcome),
            "policy_id": self.policy_id,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "remediation": self.remediation,
            "evaluated_at": self.evaluated_at,
            "metadata": dict(self.metadata),
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
        )
