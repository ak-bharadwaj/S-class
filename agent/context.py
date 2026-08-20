"""
S-Class EOS V11.2 - D7 Deterministic Agent Context Builder (§8.1, §8.3).
Assembles task objectives, repository SHA bindings, D1 Frontier, D3 Policy constraints,
D4/D6A verification feedback, and capability-scoped tool manifests into an immutable AgentSessionContext.
"""

from __future__ import annotations
from typing import Mapping, Optional, Sequence, Any
from domain.models import Obligation, Policy
from controller.frontier import compute_executable_frontier
from agent.models import AgentSessionContext
from agent.tools import AgentToolRegistry


class AgentContextBuilder:
    """Pure builder assembling deterministic AgentSessionContext snapshots bound to repository SHA."""

    def __init__(self, tool_registry: Optional[AgentToolRegistry] = None):
        self._tool_registry = tool_registry or AgentToolRegistry()

    def build_context(
        self,
        session_id: str,
        repository_id: str,
        source_sha: str,
        task_id: str,
        objective: str,
        obligations: Mapping[str, Obligation],
        policies: Mapping[str, Policy],
        granted_capabilities: Sequence[str],
        verification_feedback: Optional[Sequence[Mapping[str, Any]]] = None,
        turn_index: int = 0,
        max_turns: int = 10,
        remaining_budget_usd: float = 10.0,
    ) -> AgentSessionContext:
        """Constructs an immutable AgentSessionContext from verified domain state."""
        # 1. Compute current executable frontier from D1 DAG
        frontier_ids = compute_executable_frontier(
            obligations=obligations,
            policies=policies,
            budget_remaining=remaining_budget_usd,
        )
        frontier_details = []
        for oid in frontier_ids:
            if oid in obligations:
                o = obligations[oid]
                frontier_details.append(
                    {
                        "obligation_id": o.obligation_id,
                        "title": o.title,
                        "description": o.description,
                        "category": o.category.value,
                        "criticality": o.criticality.value,
                        "policy_id": o.policy_id,
                    }
                )

        # 2. Extract policy constraint descriptions from D3 policies
        policy_rules = []
        for pol in policies.values():
            for rule in pol.expression.rules:
                policy_rules.append(f"[{pol.policy_id}] Rule: {rule.rule_type.value} - Params: {dict(rule.parameters)}")

        # 3. Filter available tools strictly to granted capabilities
        available_tools = self._tool_registry.get_available_tools_for_capabilities(granted_capabilities)

        return AgentSessionContext(
            session_id=session_id,
            repository_id=repository_id,
            source_sha=source_sha,
            task_id=task_id,
            objective=objective,
            frontier_obligation_ids=frontier_ids,
            frontier_details=tuple(frontier_details),
            policy_constraints=tuple(policy_rules),
            verification_feedback=tuple(verification_feedback or ()),
            available_tools=available_tools,
            granted_capabilities=tuple(granted_capabilities),
            turn_index=turn_index,
            max_turns=max_turns,
            remaining_budget_usd=remaining_budget_usd,
        )
