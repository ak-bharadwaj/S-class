"""D8 Autonomous Planning Substrate - Proposal Emitter (§3.6, §8.1).

Selects the next executable node from a validated strategy DAG and synthesizes
an immutable ActionProposal bound to the active planning lease and state coordinates.
"""

from __future__ import annotations
import uuid
from typing import Optional, Sequence, Set

from controller.authorization import ActionProposal
from planner.dependency import DependencyPlanner
from planner.models import ExecutionStrategyArtifact, PlanNode, PlanningLease


class ProposalEmitter:
    """Emits ActionProposal objects bound to the active planning lease."""

    @staticmethod
    def emit_next_proposal(
        strategy: ExecutionStrategyArtifact,
        lease: PlanningLease,
        state_version: int,
        state_digest: str,
        completed_node_ids: Sequence[str] = (),
    ) -> Optional[ActionProposal]:
        """Selects the next uncompleted executable node in topological order."""
        if not isinstance(strategy, ExecutionStrategyArtifact):
            raise TypeError("strategy must be an ExecutionStrategyArtifact instance.")
        if not isinstance(lease, PlanningLease) or not lease.is_active:
            raise ValueError("An active PlanningLease is required to emit proposals.")

        # Enforce execution strategy fingerprint integrity
        from planner.fingerprint import compute_execution_strategy_fingerprint
        expected_strat_digest = compute_execution_strategy_fingerprint(strategy)
        if strategy.strategy_digest != expected_strat_digest:
            raise ValueError(
                f"Execution strategy digest tampering detected: '{strategy.strategy_digest}' != expected '{expected_strat_digest}'"
            )

        completed_set: Set[str] = set(completed_node_ids)
        topo_order = DependencyPlanner.topological_sort(strategy)
        nodes_by_id = {node.node_id: node for node in strategy.nodes}

        # Find first node whose prerequisites are all in completed_set
        for node_id in topo_order:
            if node_id in completed_set:
                continue

            node = nodes_by_id[node_id]

            # Enforce cryptographic action digest integrity against execution strategy
            from controller.token import compute_action_digest
            expected_digest = compute_action_digest(
                action_type=node.action_type,
                target=node.target,
                purpose=node.purpose,
                parameters=node.parameters,
            )
            if node.node_digest != expected_digest:
                raise ValueError(
                    f"Strategy node '{node.node_id}' action digest tampering detected: "
                    f"'{node.node_digest}' != expected '{expected_digest}'"
                )

            # Check prerequisites
            if all(prereq in completed_set for prereq in node.prerequisites):
                proposal_id = f"PROP-{node.node_id}-{uuid.uuid4().hex[:6]}"
                return ActionProposal(
                    proposal_id=proposal_id,
                    obligation_id=node.obligation_id,
                    action_type=node.action_type,
                    target=node.target,
                    purpose=node.purpose,
                    execution_context=node.execution_context,
                    estimated_cost_usd=node.estimated_cost_usd,
                    timeout_seconds=node.timeout_seconds,
                    prerequisites=node.prerequisites,
                    parameters=node.parameters,
                    action_digest=node.node_digest,
                    fencing_token=lease.fencing_token,
                    lease_epoch=lease.lease_epoch,
                    owner_id=lease.owner_id,
                    state_version=state_version,
                    state_digest=state_digest,
                )

        return None
