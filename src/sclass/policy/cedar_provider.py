"""
S-Class Policy: Cedar Policy Provider (RC.14).
Experimental, non-blocking authorization provider implementing the PolicyProvider abstraction.
Cedar decisions are normalized into canonical S-Class AuthorizationDecision models.
Guaranteed invariant: Cedar never blocks the release-critical MVP roadmap.
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Union

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.capability import Capability
from sclass.policy.provider import PolicyProvider

logger = logging.getLogger("sclass.policy.cedar_provider")


@dataclass
class CedarEntity:
    """Represents a Cedar entity identifier (e.g. Agent::"untrusted_worker")."""
    entity_type: str
    entity_id: str

    def __str__(self) -> str:
        return f'{self.entity_type}::"{self.entity_id}"'


@dataclass
class CedarRule:
    """Parsed Cedar policy rule statement."""
    effect: str  # "permit" | "forbid"
    principal_pattern: str
    action_pattern: str
    resource_pattern: str
    condition: Optional[str] = None
    rule_id: str = "rule_default"

    def matches(self, principal: str, action: str, resource: str, context: Dict[str, Any]) -> bool:
        """Evaluates whether rule patterns match the evaluation context."""
        # Principal match
        if self.principal_pattern.lower() not in ("principal", "?", "*", "") and self.principal_pattern not in principal:
            return False

        # Action match
        if self.action_pattern.lower() not in ("action", "?", "*", "") and self.action_pattern not in action:
            return False

        # Resource match
        if self.resource_pattern.lower() not in ("resource", "?", "*", "") and self.resource_pattern not in resource:
            return False

        # Condition check (basic expression evaluator for when {...})
        if self.condition:
            cond = self.condition.strip()
            # Handle context attribute checks e.g. context.platform == "claude"
            if "context." in cond:
                for k, v in context.items():
                    placeholder = f"context.{k}"
                    if placeholder in cond:
                        val_repr = f'"{v}"' if isinstance(v, str) else str(v)
                        cond = cond.replace(placeholder, val_repr)
                try:
                    # Evaluate simple python expression safely
                    return bool(eval(cond, {"__builtins__": None}, {}))
                except Exception:
                    return False

        return True


class CedarProvider(PolicyProvider):
    """
    Experimental, non-blocking Cedar policy engine provider.
    Evaluates principal/action/resource/context authorizations and normalizes them
    into canonical S-Class AuthorizationDecisions.
    """

    def __init__(
        self,
        policies: Optional[Union[str, List[str]]] = None,
        policy_version: str = "1.0.0-cedar",
        non_blocking: bool = True,
        strict_fail_closed: bool = False,
    ):
        self._policy_version = policy_version
        self.non_blocking = non_blocking
        self.strict_fail_closed = strict_fail_closed
        self._rules: List[CedarRule] = []

        if policies:
            if isinstance(policies, list):
                for p in policies:
                    self.add_policy(p)
            elif isinstance(policies, str):
                self.add_policy(policies)
        else:
            # Default permissive rule for unconfigured experimental Cedar
            self.add_policy('permit (principal, action, resource);')

    @property
    def provider_name(self) -> str:
        return "cedar"

    @property
    def provider_version(self) -> str:
        return self._policy_version

    @property
    def is_experimental(self) -> bool:
        return True

    def is_healthy(self) -> bool:
        """Always healthy since it embeds a reliable in-memory evaluator with graceful degradation."""
        return True

    def add_policy(self, policy_text: str) -> None:
        """Parses and registers Cedar policy statements."""
        statements = [s.strip() for s in policy_text.split(";") if s.strip()]
        for stmt in statements:
            # Match: permit / forbid (principal, action, resource) [when { ... }]
            m = re.match(r"(permit|forbid)\s*\(\s*([^,]+),\s*([^,]+),\s*([^)]+)\)\s*(?:when\s*\{\s*(.*?)\s*\})?", stmt, re.DOTALL)
            if m:
                effect, princ, act, res, cond = m.groups()
                rule = CedarRule(
                    effect=effect.strip().lower(),
                    principal_pattern=princ.strip().replace('"', ''),
                    action_pattern=act.strip().replace('"', ''),
                    resource_pattern=res.strip().replace('"', ''),
                    condition=cond.strip() if cond else None,
                    rule_id=f"cedar_{len(self._rules)+1}",
                )
                self._rules.append(rule)
            else:
                logger.warning(f"Failed to parse Cedar statement: {stmt}")

    def map_request_to_cedar(self, request: ActionRequest) -> Tuple[str, str, str, Dict[str, Any]]:
        """Maps canonical ActionRequest to Cedar Principal, Action, Resource, Context model."""
        # 1. Principal
        actor = request.actor or "unknown_agent"
        principal = f'Agent::"{actor}"' if "agent" in actor.lower() else f'User::"{actor}"'

        # 2. Action
        cap = request.capability or "terminal.execute"
        act = request.action or "run"
        action = f'Action::"{cap}.{act}"'

        # 3. Resource
        target = request.target or request.workspace or "workspace_root"
        resource = f'Resource::"{target}"'

        # 4. Context
        context = dict(request.context or {})
        if request.provenance:
            context["platform"] = request.provenance.get("platform", "generic")
        if request.session:
            context["session"] = request.session

        return principal, action, resource, context

    def evaluate(
        self,
        request: ActionRequest,
        workspace_dir: str = "",
        capability: Optional[Capability] = None,
        expected_policy_version: Optional[str] = None,
        mode: str = "enforce",
        timeout: Optional[float] = None,
    ) -> AuthorizationDecision:
        """
        Evaluates ActionRequest under Cedar policies.
        Normalizes decisions into canonical AuthorizationDecision.
        Non-blocking: experimental issues never crash or halt production pipeline.
        """
        try:
            principal, action, resource, context = self.map_request_to_cedar(request)

            has_permit = False
            forbid_reason = None
            permit_rule_id = None

            for rule in self._rules:
                if rule.matches(principal, action, resource, context):
                    if rule.effect == "forbid":
                        forbid_reason = f"Explicit forbid by Cedar rule '{rule.rule_id}'"
                        break
                    elif rule.effect == "permit":
                        has_permit = True
                        permit_rule_id = rule.rule_id

            if forbid_reason:
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY if (mode == "enforce" or self.strict_fail_closed) else DecisionOutcome.WARN,
                    policy_id="CEDAR-FORBID",
                    risk_level="HIGH",
                    reason=f"Denied by Cedar policy: {forbid_reason}",
                    metadata={
                        "principal": principal,
                        "action": action,
                        "resource": resource,
                        "experimental": True,
                        "provider": "cedar",
                    },
                )

            if has_permit:
                return AuthorizationDecision(
                    outcome=DecisionOutcome.ALLOW,
                    policy_id="CEDAR-PERMIT",
                    risk_level="LOW",
                    reason=f"Permitted by Cedar rule '{permit_rule_id}'",
                    metadata={
                        "principal": principal,
                        "action": action,
                        "resource": resource,
                        "experimental": True,
                        "provider": "cedar",
                    },
                )

            # Default: No permit matched
            if self.non_blocking and not self.strict_fail_closed:
                # In non-blocking experimental mode, warn rather than break roadmap
                return AuthorizationDecision(
                    outcome=DecisionOutcome.WARN if mode == "enforce" else DecisionOutcome.ALLOW,
                    policy_id="CEDAR-DEFAULT-DENY-NONBLOCKING",
                    risk_level="MEDIUM",
                    reason="Cedar policy did not explicitly permit (non-blocking experimental mode permits progression with warning)",
                    metadata={
                        "principal": principal,
                        "action": action,
                        "resource": resource,
                        "experimental": True,
                        "provider": "cedar",
                    },
                )
            else:
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY,
                    policy_id="CEDAR-DEFAULT-DENY",
                    risk_level="HIGH",
                    reason="Denied by Cedar policy: No matching permit statement found",
                    metadata={
                        "principal": principal,
                        "action": action,
                        "resource": resource,
                        "experimental": True,
                        "provider": "cedar",
                    },
                )

        except Exception as ex:
            logger.error(f"Cedar evaluation exception: {ex}")
            if self.non_blocking and not self.strict_fail_closed:
                # Cedar must never block the MVP roadmap
                return AuthorizationDecision(
                    outcome=DecisionOutcome.WARN,
                    policy_id="CEDAR-EVAL-ERROR-NONBLOCKING",
                    risk_level="LOW",
                    reason=f"Cedar experimental evaluation error suppressed: {ex}",
                    metadata={"error": str(ex), "experimental": True, "provider": "cedar"},
                )
            return AuthorizationDecision(
                outcome=DecisionOutcome.DENY,
                policy_id="CEDAR-EVAL-ERROR",
                risk_level="CRITICAL",
                reason=f"Cedar policy evaluation failure: {ex}",
                metadata={"error": str(ex), "experimental": True, "provider": "cedar"},
            )
