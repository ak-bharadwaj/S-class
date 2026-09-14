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
from typing import Dict, Any, Optional, List, Union, Tuple

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.capability import Capability
from sclass.policy.provider import PolicyProvider

logger = logging.getLogger("sclass.policy.cedar_provider")


def clean_entity(e: str) -> str:
    """Removes surrounding quotes and whitespace from an entity/identifier."""
    return re.sub(r'[\"\']', '', e.strip())


class CedarContextNamespace:
    """Context wrapper enabling attribute-style and dict-style access for condition eval."""
    def __init__(self, d: Optional[Dict[str, Any]] = None):
        self._d = d or {}

    def __getattr__(self, name: str) -> Any:
        return self._d.get(name)

    def __getitem__(self, name: str) -> Any:
        return self._d.get(name)

    def get(self, name: str, default: Any = None) -> Any:
        return self._d.get(name, default)


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
    clause_type: str = "when"  # "when" | "unless"
    rule_id: str = "rule_default"

    def _matches_entity(self, raw_pattern: str, entity_value: str) -> bool:
        """Matches a principal/action/resource pattern against the target entity string."""
        raw = raw_pattern.strip()
        if raw.lower() in ("principal", "action", "resource", "?", "*", ""):
            return True

        cleaned_entity = clean_entity(entity_value)
        entity_id = cleaned_entity.split("::")[-1]

        def _match_single(target: str) -> bool:
            c_target = clean_entity(target)
            if not c_target:
                return True
            target_id = c_target.split("::")[-1]
            return (
                c_target == cleaned_entity
                or c_target in cleaned_entity
                or cleaned_entity in c_target
                or target_id == entity_id
                or entity_id.endswith(target_id)
                or target_id.endswith(entity_id)
            )

        # Equality match: e.g. "principal == Agent::\"alice\"" or "== Agent::\"alice\""
        if "==" in raw:
            target = raw.split("==", 1)[1]
            return _match_single(target)

        # Set membership: e.g. "action in [Action::\"read\", Action::\"write\"]"
        if " in " in raw:
            target = raw.split(" in ", 1)[1].strip()
            if target.startswith("[") and target.endswith("]"):
                items = [i for i in target.strip("[]").split(",") if i.strip()]
                return any(_match_single(item) for item in items)
            return _match_single(target)

        # Direct pattern match
        return _match_single(raw)

    def matches(self, principal: str, action: str, resource: str, context: Dict[str, Any]) -> bool:
        """Evaluates whether rule patterns and condition match the evaluation context."""
        # 1. Principal match
        if not self._matches_entity(self.principal_pattern, principal):
            return False

        # 2. Action match
        if not self._matches_entity(self.action_pattern, action):
            return False

        # 3. Resource match
        if not self._matches_entity(self.resource_pattern, resource):
            return False

        # 4. Condition check (for when {...} or unless {...})
        if self.condition:
            cond = self.condition.strip()
            # Normalize boolean literals, null, operators
            c = re.sub(r'\btrue\b', 'True', cond)
            c = re.sub(r'\bfalse\b', 'False', c)
            c = re.sub(r'\bnull\b', 'None', c)
            c = c.replace('&&', ' and ').replace('||', ' or ')
            # Replace ! (not part of !=) with not
            c = re.sub(r'!(?!=)', ' not ', c)
            # Replace Entity::"id" or Entity::id with "Entity::id"
            c = re.sub(r'([A-Za-z0-9_]+)::[\"\']?(.*?)[\"\']?(?=[^A-Za-z0-9_\-]|$)', r'"\1::\2"', c)

            globs = {
                "__builtins__": None,
                "True": True,
                "False": False,
                "None": None,
            }
            locs = {
                "context": CedarContextNamespace(context),
                "principal": principal,
                "action": action,
                "resource": resource,
            }
            try:
                cond_val = bool(eval(c, globs, locs))
                # when: condition must be true; unless: condition must be false
                matched = cond_val if self.clause_type == "when" else (not cond_val)
                if not matched:
                    return False
            except Exception as ex:
                logger.debug(f"Condition evaluation failed for rule '{self.rule_id}': {ex}")
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
        self._cedarpy = None
        try:
            import cedarpy
            self._cedarpy = cedarpy
        except ImportError:
            self._cedarpy = None

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

    @staticmethod
    def _split_cedar_args(args_str: str) -> List[str]:
        """Splits Cedar arguments respecting nested brackets and string literals."""
        parts: List[str] = []
        current: List[str] = []
        depth_bracket = 0
        in_quote = False
        quote_char = None
        for ch in args_str:
            if in_quote:
                current.append(ch)
                if ch == quote_char:
                    in_quote = False
            elif ch in ('"', "'"):
                in_quote = True
                quote_char = ch
                current.append(ch)
            elif ch == '[':
                depth_bracket += 1
                current.append(ch)
            elif ch == ']':
                depth_bracket -= 1
                current.append(ch)
            elif ch == ',' and depth_bracket == 0:
                parts.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            parts.append(''.join(current).strip())
        return parts

    def add_policy(self, policy_text: str) -> None:
        """Parses and registers Cedar policy statements."""
        statements = [s.strip() for s in policy_text.split(";") if s.strip()]
        for stmt in statements:
            # Match: permit / forbid ( ... ) [when|unless { ... }]
            m = re.match(
                r"(permit|forbid)\s*\((.*?)\)\s*(?:(when|unless)\s*\{\s*(.*?)\s*\})?",
                stmt,
                re.DOTALL,
            )
            if m:
                effect, args_body, clause, cond = m.groups()
                args = self._split_cedar_args(args_body)
                princ = args[0] if len(args) > 0 else "principal"
                act = args[1] if len(args) > 1 else "action"
                res = args[2] if len(args) > 2 else "resource"
                rule = CedarRule(
                    effect=effect.strip().lower(),
                    principal_pattern=princ.strip(),
                    action_pattern=act.strip(),
                    resource_pattern=res.strip(),
                    clause_type=(clause or "when").strip().lower(),
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
