"""
S-Class EOS V10.2 - Authoritative Execution Dependency & Topology Resolution Engine

Computes deterministic topological execution DAGs, transitive invalidation graphs,
and fail-closed cycle detection derived strictly from explicit architectural evidence.
"""

from typing import Dict, List, Set, Any, Optional, Tuple
from collections import defaultdict, deque

from execution_ir import (
    ExecutionTask,
    ExecutionDependency,
    DependencyType,
    ExecutionMode,
    TaskRiskLevel
)
from lld_compiler import LLDComponent, LLDComponentType
from requirement_ir import RequirementGraph, RequirementNode
from behavior_graph import BehaviorGraph, BehaviorNodeType
from hld_compiler import HLDDesign, HLDModule


class CyclicDependencyError(ValueError):
    """Raised when an execution dependency cycle is detected."""
    pass


class ExecutionDependencyResolver:
    """Derives architectural dependencies and validates execution DAG invariants."""

    @classmethod
    def resolve_dependencies(
        cls,
        tasks: Dict[str, ExecutionTask],
        lld_components: Optional[List[LLDComponent]] = None,
        r_graph: Optional[RequirementGraph] = None,
        b_graph: Optional[BehaviorGraph] = None,
        hld: Optional[HLDDesign] = None
    ) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], Dict[str, List[str]]]:
        """
        Derives all explicit architectural dependencies and produces:
        (dependency_dag, reverse_dag, invalidation_graph).

        Raises CyclicDependencyError if any cyclic dependency exists.
        """
        dependency_dag: Dict[str, Set[str]] = {t_id: set() for t_id in tasks}
        reverse_dag: Dict[str, Set[str]] = {t_id: set() for t_id in tasks}

        lld_map = {c.id: c for c in (lld_components or [])}
        hld_mod_map = {m.id: m for m in (hld.modules if hld else [])}

        # 1. Existing explicit dependencies declared on tasks
        for t_id, task in tasks.items():
            for dep in task.dependencies:
                if dep.source_task_id not in tasks:
                    raise CyclicDependencyError(
                        f"Task '{t_id}' declares dependency on unknown task '{dep.source_task_id}' not found in task graph."
                    )
                if dep.source_task_id != t_id:
                    dependency_dag[t_id].add(dep.source_task_id)
                    reverse_dag[dep.source_task_id].add(t_id)

        # 2. Derive Requirement Graph Dependencies: If REQ-A depends on REQ-B, Task(A) depends on Task(B)
        if r_graph and r_graph.nodes:
            req_to_tasks: Dict[str, Set[str]] = defaultdict(set)
            for t_id, task in tasks.items():
                for r_id in task.parent_req_ids:
                    req_to_tasks[r_id].add(t_id)

            for r_id, req_node in r_graph.nodes.items():
                dependent_req_tasks = req_to_tasks.get(r_id, set())
                for prereq_req_id in getattr(req_node, "dependencies", []):
                    prereq_tasks = req_to_tasks.get(prereq_req_id, set())
                    for dep_t in dependent_req_tasks:
                        for pre_t in prereq_tasks:
                            if dep_t != pre_t:
                                dependency_dag[dep_t].add(pre_t)
                                reverse_dag[pre_t].add(dep_t)
                                # Record typed dependency
                                if not any(d.source_task_id == pre_t for d in tasks[dep_t].dependencies):
                                    tasks[dep_t].dependencies.append(ExecutionDependency(
                                        source_task_id=pre_t,
                                        target_task_id=dep_t,
                                        dep_type=DependencyType.HARD_PREREQUISITE,
                                        rationale=f"Upstream requirement '{r_id}' depends on requirement '{prereq_req_id}'",
                                        lineage_ref=f"{r_id}->{prereq_req_id}"
                                    ))

        # 3. Derive Behavior Graph State-Flow Preconditions:
        # If Behavior A transitions S0 -> S1, and Behavior B requires S1, Task(B) depends on Task(A)
        if b_graph and b_graph.nodes:
            entity_state_providers: Dict[Tuple[str, str], Set[str]] = defaultdict(set) # (entity, to_state) -> task_ids
            for t_id, task in tasks.items():
                for b_id in task.parent_behavior_ids:
                    b_node = b_graph.get_node(b_id)
                    if b_node and b_node.to_state and b_node.target_entity_id:
                        entity_state_providers[(b_node.target_entity_id.lower(), b_node.to_state.lower())].add(t_id)

            for t_id, task in tasks.items():
                for b_id in task.parent_behavior_ids:
                    b_node = b_graph.get_node(b_id)
                    if b_node and b_node.from_state and b_node.target_entity_id:
                        key = (b_node.target_entity_id.lower(), b_node.from_state.lower())
                        for provider_t in entity_state_providers.get(key, set()):
                            if provider_t != t_id:
                                dependency_dag[t_id].add(provider_t)
                                reverse_dag[provider_t].add(t_id)
                                if not any(d.source_task_id == provider_t for d in task.dependencies):
                                    task.dependencies.append(ExecutionDependency(
                                        source_task_id=provider_t,
                                        target_task_id=t_id,
                                        dep_type=DependencyType.STATE_FLOW,
                                        rationale=f"State flow: entity '{b_node.target_entity_id}' requires state '{b_node.from_state}' produced by task '{provider_t}'",
                                        lineage_ref=f"state:{b_node.from_state}"
                                    ))

        # 4. Derive Architecture Layer Precedence:
        # Backend API Controller/Service contracts precede UI Surfaces that consume their behaviors/requirements/entities
        backend_tasks_by_beh: Dict[str, Set[str]] = defaultdict(set)
        backend_tasks_by_req: Dict[str, Set[str]] = defaultdict(set)
        backend_tasks_by_entity: Dict[str, Set[str]] = defaultdict(set)

        for t_id, task in tasks.items():
            if task.parent_lld_id in lld_map:
                comp = lld_map[task.parent_lld_id]
                if comp.component_type in [LLDComponentType.CONTROLLER, LLDComponentType.SERVICE, LLDComponentType.CLI_DISPATCHER]:
                    for b_id in task.parent_behavior_ids:
                        backend_tasks_by_beh[b_id].add(t_id)
                    for r_id in task.parent_req_ids:
                        backend_tasks_by_req[r_id].add(t_id)
                    for ent in comp.owned_entities:
                        backend_tasks_by_entity[ent.lower()].add(t_id)

        for t_id, task in tasks.items():
            if task.parent_lld_id in lld_map:
                comp = lld_map[task.parent_lld_id]
                if comp.component_type == LLDComponentType.UI_SURFACE:
                    matching_backend_tasks = set()
                    for b_id in task.parent_behavior_ids:
                        matching_backend_tasks.update(backend_tasks_by_beh.get(b_id, []))
                    for r_id in task.parent_req_ids:
                        matching_backend_tasks.update(backend_tasks_by_req.get(r_id, []))
                    for ent in comp.owned_entities:
                        matching_backend_tasks.update(backend_tasks_by_entity.get(ent.lower(), []))

                    if not matching_backend_tasks and comp.parent and comp.parent.hld_id:
                        for b_t_id, b_t in tasks.items():
                            if b_t_id != t_id and b_t.parent_lld_id in lld_map:
                                b_comp = lld_map[b_t.parent_lld_id]
                                if b_comp.component_type in [LLDComponentType.CONTROLLER, LLDComponentType.SERVICE, LLDComponentType.CLI_DISPATCHER]:
                                    if b_comp.parent and b_comp.parent.hld_id == comp.parent.hld_id:
                                        matching_backend_tasks.add(b_t_id)

                    for b_t in matching_backend_tasks:
                        if b_t != t_id:
                            dependency_dag[t_id].add(b_t)
                            reverse_dag[b_t].add(t_id)
                            if not any(d.source_task_id == b_t for d in task.dependencies):
                                task.dependencies.append(ExecutionDependency(
                                    source_task_id=b_t,
                                    target_task_id=t_id,
                                    dep_type=DependencyType.DATA_FLOW,
                                    rationale=f"Architectural layering: backend service task '{b_t}' must precede UI consumer task '{t_id}'",
                                    lineage_ref=f"layer:backend->ui"
                                ))

        # 5. Cycle Detection using Kahn's Algorithm
        in_degree = {t_id: len(dependency_dag[t_id]) for t_id in tasks}
        queue = deque([t_id for t_id, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            node = queue.popleft()
            visited_count += 1
            for child in reverse_dag[node]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if visited_count != len(tasks):
            # Find cycle nodes
            cycle_nodes = [t_id for t_id, deg in in_degree.items() if deg > 0]
            raise CyclicDependencyError(
                f"Cyclic dependency detected among execution tasks: {sorted(cycle_nodes)}"
            )

        # 6. Compute Transitive Invalidation Graph (Downstream Cascade)
        invalidation_graph: Dict[str, List[str]] = {}
        for t_id in tasks:
            descendants: Set[str] = set()
            to_visit = list(reverse_dag[t_id])
            seen: Set[str] = set()
            while to_visit:
                curr = to_visit.pop()
                if curr not in seen:
                    seen.add(curr)
                    descendants.add(curr)
                    to_visit.extend(reverse_dag[curr])
            invalidation_graph[t_id] = sorted(list(descendants))

        sorted_dep_dag = {k: sorted(list(v)) for k, v in sorted(dependency_dag.items())}
        sorted_rev_dag = {k: sorted(list(v)) for k, v in sorted(reverse_dag.items())}

        return sorted_dep_dag, sorted_rev_dag, invalidation_graph

    @classmethod
    def compute_topological_order(cls, dependency_dag: Dict[str, List[str]]) -> List[str]:
        """Computes deterministic topological ordering with tie-breaking on task IDs."""
        in_degree = {k: len(v) for k, v in dependency_dag.items()}
        reverse_dag: Dict[str, List[str]] = defaultdict(list)
        for child, parents in dependency_dag.items():
            for p in parents:
                reverse_dag[p].append(child)

        # Priority queue / sorted list for deterministic tie breaking
        ready = sorted([k for k, deg in in_degree.items() if deg == 0])
        ordered: List[str] = []

        while ready:
            curr = ready.pop(0)
            ordered.append(curr)
            for child in sorted(reverse_dag[curr]):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    ready.append(child)
                    ready.sort()

        if len(ordered) != len(dependency_dag):
            raise CyclicDependencyError("Topological sort failed due to unresolvable cycle in dependency DAG.")

        return ordered
