"""D8 Autonomous Planning Substrate - Dependency & DAG Engine (§3.6, §8.1).

Constructs topological schedules, validates acyclicity via Kahn's algorithm,
and computes deterministic parallel execution frontiers.
"""

from __future__ import annotations
from collections import defaultdict, deque
from typing import Dict, List, Sequence, Set, Tuple

from planner.models import ExecutionStrategyArtifact, PlanNode


class DependencyCycleError(ValueError):
    """Raised when a dependency cycle is detected in the plan strategy DAG."""
    pass


class DependencyPlanner:
    """Deterministic DAG validation and scheduling engine for plan strategies."""

    @staticmethod
    def validate_acyclicity(strategy: ExecutionStrategyArtifact) -> bool:
        """Validates that the dependency edges form a Directed Acyclic Graph."""
        try:
            DependencyPlanner.topological_sort(strategy)
            return True
        except DependencyCycleError:
            return False

    @staticmethod
    def topological_sort(strategy: ExecutionStrategyArtifact) -> Sequence[str]:
        """Computes a deterministic topological ordering using Kahn's algorithm."""
        node_ids = {node.node_id for node in strategy.nodes}
        in_degree: Dict[str, int] = {nid: 0 for nid in node_ids}
        adj: Dict[str, List[str]] = defaultdict(list)

        # Explicit edges from strategy
        for src, dst in strategy.dependency_edges:
            if src in node_ids and dst in node_ids:
                adj[src].append(dst)
                in_degree[dst] += 1

        # Implicit prerequisite edges declared on nodes
        for node in strategy.nodes:
            for prereq in node.prerequisites:
                if prereq in node_ids and node.node_id not in adj[prereq]:
                    adj[prereq].append(node.node_id)
                    in_degree[node.node_id] += 1

        # Deterministic queue (sorted lexicographically by node_id)
        queue = deque(sorted([nid for nid, deg in in_degree.items() if deg == 0]))
        order: List[str] = []

        while queue:
            curr = queue.popleft()
            order.append(curr)

            # Check neighbors
            for neighbor in sorted(adj[curr]):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
            # Maintain deterministic queue ordering
            queue = deque(sorted(list(queue)))

        if len(order) != len(node_ids):
            unvisited = node_ids - set(order)
            raise DependencyCycleError(
                f"Dependency cycle detected involving nodes: {sorted(list(unvisited))}"
            )

        return tuple(order)

    @staticmethod
    def compute_parallel_frontiers(strategy: ExecutionStrategyArtifact) -> Sequence[Tuple[str, ...]]:
        """Computes level-by-level parallel execution batches."""
        node_ids = {node.node_id for node in strategy.nodes}
        in_degree: Dict[str, int] = {nid: 0 for nid in node_ids}
        adj: Dict[str, List[str]] = defaultdict(list)

        for src, dst in strategy.dependency_edges:
            if src in node_ids and dst in node_ids:
                adj[src].append(dst)
                in_degree[dst] += 1

        for node in strategy.nodes:
            for prereq in node.prerequisites:
                if prereq in node_ids and node.node_id not in adj[prereq]:
                    adj[prereq].append(node.node_id)
                    in_degree[node.node_id] += 1

        current_frontier = sorted([nid for nid, deg in in_degree.items() if deg == 0])
        frontiers: List[Tuple[str, ...]] = []
        visited_count = 0

        while current_frontier:
            frontiers.append(tuple(current_frontier))
            visited_count += len(current_frontier)
            next_frontier = []

            for node_id in current_frontier:
                for neighbor in adj[node_id]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_frontier.append(neighbor)

            current_frontier = sorted(list(set(next_frontier)))

        if visited_count != len(node_ids):
            raise DependencyCycleError("Cycle detected during parallel frontier computation.")

        return tuple(frontiers)
