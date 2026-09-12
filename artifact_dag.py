"""
S-Class V12: OpenGSD Topological Wave Scheduler & Artifact DAG Engine
(artifact_dag.py)

Constructs a Directed Acyclic Graph (DAG) of planned execution artifacts and
schedules independent tasks into concurrent Execution Waves (W1, W2, ... Wn).
"""

from typing import Dict, Any, Optional, List, Set, Tuple
from collections import defaultdict, deque


class ArtifactDAG:
    """
    Topological Dependency Ordering and Wave Scheduling Engine.
    """

    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)  # task_id -> set of prerequisite task_ids
        self.dependents: Dict[str, Set[str]] = defaultdict(set)  # prerequisite -> set of downstream task_ids

    def add_node(
        self,
        task_id: str,
        category: str = "general",
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Registers a node with its dependency prerequisites."""
        self.nodes[task_id] = {
            "id": task_id,
            "category": category,
            "metadata": metadata or {},
        }
        for dep in dependencies or []:
            self.dependencies[task_id].add(dep)
            self.dependents[dep].add(task_id)

    def detect_cycles(self) -> List[List[str]]:
        """Detects cyclic dependencies in the artifact DAG using DFS."""
        visited: Dict[str, int] = {}  # 0 = unvisited, 1 = visiting, 2 = visited
        cycles: List[List[str]] = []
        path: List[str] = []

        def dfs(node: str):
            visited[node] = 1
            path.append(node)
            for neighbor in self.dependencies.get(node, []):
                if neighbor not in self.nodes:
                    continue
                if visited.get(neighbor, 0) == 1:
                    idx = path.index(neighbor)
                    cycles.append(path[idx:] + [neighbor])
                elif visited.get(neighbor, 0) == 0:
                    dfs(neighbor)
            path.pop()
            visited[node] = 2

        for n in self.nodes:
            if visited.get(n, 0) == 0:
                dfs(n)

        return cycles

    def compute_waves(self) -> List[List[str]]:
        """
        Computes concurrent Execution Waves (W1, W2, ... Wn) using Kahn's topological leveling.
        Returns a list of waves, where each wave is a list of task IDs that can execute in parallel.
        """
        cycles = self.detect_cycles()
        if cycles:
            raise ValueError(f"Cyclic dependency detected in task DAG: {cycles}")

        # In-degree based on internal prerequisites
        in_degree: Dict[str, int] = {}
        for nid in self.nodes:
            # Only count dependencies that exist in nodes
            valid_deps = [d for d in self.dependencies[nid] if d in self.nodes]
            in_degree[nid] = len(valid_deps)

        waves: List[List[str]] = []
        ready = deque([nid for nid, deg in in_degree.items() if deg == 0])

        while ready:
            current_wave = []
            next_wave_ready = []

            # Drain current wave
            while ready:
                node = ready.popleft()
                current_wave.append(node)

            current_wave.sort()
            waves.append(current_wave)

            # Decrement in-degree for dependents
            for node in current_wave:
                for dependent in self.dependents.get(node, []):
                    if dependent in in_degree:
                        in_degree[dependent] -= 1
                        if in_degree[dependent] == 0:
                            next_wave_ready.append(dependent)

            ready.extend(next_wave_ready)

        return waves

    def get_wave_assignments(self) -> Dict[str, int]:
        """Returns mapping from task_id -> wave_number (1-indexed)."""
        waves = self.compute_waves()
        assignments = {}
        for wave_idx, wave in enumerate(waves, start=1):
            for tid in wave:
                assignments[tid] = wave_idx
        return assignments

    def to_mermaid_dag(self) -> str:
        """Renders the wave-scheduled DAG as a Mermaid flowchart with wave subgraphs."""
        waves = self.compute_waves()
        lines = ["graph TD"]

        for wave_idx, wave in enumerate(waves, start=1):
            lines.append(f"    subgraph Wave_{wave_idx}[\"Wave {wave_idx}\"]")
            for tid in wave:
                node_info = self.nodes.get(tid, {})
                cat = node_info.get("category", "")
                label = f"{tid} ({cat})" if cat else tid
                lines.append(f"        {tid}[\"{label}\"]")
            lines.append("    end")

        for tid, deps in self.dependencies.items():
            for dep in deps:
                if dep in self.nodes:
                    lines.append(f"    {dep} --> {tid}")

        return "\n".join(lines)
