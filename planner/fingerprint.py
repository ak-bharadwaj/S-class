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
from planner.models import ExecutionStrategyArtifact, PlanNode, PlannerStateContent

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
    task_id: str,
    milestones: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    obligations: Sequence[Mapping[str, Any]],
) -> str:
    """Computes the high-level semantic intent fingerprint."""
    payload = {
        "task_id": task_id,
        "milestones": list(milestones),
        "claims": list(claims),
        "obligations": list(obligations),
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


def compute_planner_state_digest(content: PlannerStateContent) -> str:
    """Computes pure semantic state digest, strictly invariant to telemetry/metadata."""
    payload = {
        "task_id": content.task_id,
        "milestones": list(content.milestones),
        "claims": list(content.claims),
        "obligations": list(content.obligations),
        "executable_frontier": sorted(list(content.executable_frontier)),
        "blocked_frontier": sorted(list(content.blocked_frontier)),
        "evidence_digests": sorted(list(content.evidence_digests)),
        "active_policies": list(content.active_policies),
        "state_version": content.state_version,
        "state_digest": content.state_digest,
    }
    raw = SCLASS_PLANNER_STATE_DOMAIN_SEPARATOR.encode("utf-8") + canonicalize_json(payload)
    return hashlib.sha256(raw).hexdigest()
