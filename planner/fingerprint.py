"""D8 Autonomous Planning Substrate - Fingerprint & Cryptographic Hashes (§3.6, §8.1).

Computes deterministic RFC 8785 canonical JSON SHA-256 digests prefixed with
frozen domain separators:
- SCLASS_PLAN_INTENT_V1: High-level goal and claim commitment
- SCLASS_EXEC_STRATEGY_V1: Exact executable strategy and DAG structure
- SCLASS_PLANNER_STATE_V1: Exact semantic planner state
"""

from __future__ import annotations
import hashlib
import json
from typing import Any, Mapping, Sequence

from domain.models import _unfreeze_nested
from planner.models import ExecutionStrategyArtifact, Plan, PlanNode, PlannerStateContent

SCLASS_PLAN_INTENT_DOMAIN_SEPARATOR = "SCLASS_PLAN_INTENT_V1:"
SCLASS_EXEC_STRATEGY_DOMAIN_SEPARATOR = "SCLASS_EXEC_STRATEGY_V1:"
SCLASS_PLANNER_STATE_DOMAIN_SEPARATOR = "SCLASS_PLANNER_STATE_V1:"


def canonicalize_json(data: Any) -> bytes:
    """Canonical RFC 8785 JSON serializer."""
    unfrozen = _unfreeze_nested(data)
    return json.dumps(
        unfrozen,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")


def compute_plan_semantic_fingerprint(
    plan: Optional[Plan] = None,
    *,
    task_id: str = "",
    plan_id: str = "",
    version: int = 1,
    milestones: Sequence[Mapping[str, Any]] = (),
    architecture_claims: Sequence[Mapping[str, Any]] = (),
    obligation_ids: Sequence[str] = (),
) -> str:
    """Computes the canonical D0 Plan semantic intent fingerprint."""
    if isinstance(plan, Plan):
        payload = {
            "plan_id": plan.plan_id,
            "task_id": plan.task_id,
            "version": plan.version,
            "milestones": list(plan.milestones),
            "architecture_claims": list(plan.architecture_claims),
            "obligation_ids": sorted(list(plan.obligation_ids)),
        }
    else:
        payload = {
            "plan_id": plan_id,
            "task_id": task_id,
            "version": version,
            "milestones": list(milestones),
            "architecture_claims": list(architecture_claims),
            "obligation_ids": sorted(list(obligation_ids)),
        }
    raw = SCLASS_PLAN_INTENT_DOMAIN_SEPARATOR.encode("utf-8") + canonicalize_json(payload)
    return hashlib.sha256(raw).hexdigest()


def compute_execution_strategy_fingerprint(strategy: ExecutionStrategyArtifact) -> str:
    """Computes the exact execution strategy fingerprint committing to nodes and DAG edges."""
    node_payloads = []
    for node in strategy.nodes:
        node_payloads.append({
            "node_id": node.node_id,
            "obligation_id": node.obligation_id,
            "action_type": node.action_type,
            "target": node.target,
            "purpose": node.purpose,
            "context_digest": node.execution_context.context_digest,
            "parameters": node.parameters,
            "prerequisites": list(node.prerequisites),
            "estimated_cost_usd": node.estimated_cost_usd,
            "timeout_seconds": node.timeout_seconds,
            "node_digest": node.node_digest,
        })

    # Sort nodes by node_id for deterministic representation
    node_payloads.sort(key=lambda n: n["node_id"])
    sorted_edges = sorted(list(strategy.dependency_edges), key=lambda e: (e[0], e[1]))

    payload = {
        "strategy_id": strategy.strategy_id,
        "plan_id": strategy.plan_id,
        "plan_revision": strategy.plan_revision,
        "nodes": node_payloads,
        "dependency_edges": sorted_edges,
    }
    raw = SCLASS_EXEC_STRATEGY_DOMAIN_SEPARATOR.encode("utf-8") + canonicalize_json(payload)
    return hashlib.sha256(raw).hexdigest()


def _canonicalize_policy_expression(expr: Any) -> Dict[str, Any]:
    if expr is None:
        return {}
    if isinstance(expr, dict):
        return dict(expr)

    rules = []
    for r in getattr(expr, "rules", ()):
        if hasattr(r, "rule_type"):
            rules.append({
                "rule_type": r.rule_type.value if hasattr(r.rule_type, "value") else str(r.rule_type),
                "parameters": dict(getattr(r, "parameters", {})),
            })
        elif isinstance(r, dict):
            rules.append(dict(r))
        else:
            rules.append({"rule": str(r)})

    rules.sort(key=lambda x: (x.get("rule_type", ""), str(sorted(x.get("parameters", {}).items()))))

    cond = getattr(expr, "condition", None)
    if cond is not None:
        cond = dict(cond)

    then_e = getattr(expr, "then_expression", None)
    else_e = getattr(expr, "else_expression", None)

    return {
        "combinator": expr.combinator.value if hasattr(expr.combinator, "value") else str(expr.combinator),
        "rules": rules,
        "min_count": getattr(expr, "min_count", None),
        "condition": cond,
        "then_expression": _canonicalize_policy_expression(then_e) if then_e else None,
        "else_expression": _canonicalize_policy_expression(else_e) if else_e else None,
    }


def _canonicalize_policy(pol: Any) -> Dict[str, Any]:
    if hasattr(pol, "policy_id"):
        return {
            "policy_id": pol.policy_id,
            "scope_level": pol.scope_level.value if hasattr(pol.scope_level, "value") else str(pol.scope_level),
            "version": getattr(pol, "version", 1),
            "expression": _canonicalize_policy_expression(getattr(pol, "expression", None)),
        }
    elif isinstance(pol, dict):
        return dict(pol)
    return {"policy_id": str(pol)}


def _canonicalize_exception(exc: Any) -> Dict[str, Any]:
    if hasattr(exc, "exception_id"):
        return {
            "exception_id": exc.exception_id,
            "obligation_id": exc.obligation_id,
            "policy_id": exc.policy_id,
            "justification": exc.justification,
            "compensating_controls": list(getattr(exc, "compensating_controls", ())),
            "expiry": getattr(exc, "expiry", None),
        }
    elif isinstance(exc, dict):
        return dict(exc)
    return {"exception_id": str(exc)}


def compute_planner_state_digest(content: PlannerStateContent) -> str:
    """Computes pure semantic state digest, strictly invariant to telemetry/metadata."""
    normalized_policies = [_canonicalize_policy(pol) for pol in getattr(content, "active_policies", ())]
    normalized_exceptions = [_canonicalize_exception(exc) for exc in getattr(content, "exceptions", ())]

    payload = {
        "task_id": content.task_id,
        "milestones": list(content.milestones),
        "claims": list(content.claims),
        "obligations": list(content.obligations),
        "executable_frontier": sorted(list(content.executable_frontier)),
        "blocked_frontier": sorted(list(content.blocked_frontier)),
        "evidence_digests": sorted(list(content.evidence_digests)),
        "active_policies": normalized_policies,
        "exceptions": normalized_exceptions,
        "analysis_digests": sorted(list(getattr(content, "analysis_digests", ()))),
        "state_version": content.state_version,
        "state_digest": content.state_digest,
    }
    raw = SCLASS_PLANNER_STATE_DOMAIN_SEPARATOR.encode("utf-8") + canonicalize_json(payload)
    return hashlib.sha256(raw).hexdigest()
