"""Deterministic Obligation Graph and Frontier Representation for S-Class D1.

Adapts OpenSpec-validated topological concepts:
1. Duplicate ID rejection.
2. Missing dependency reference rejection.
3. Universal cycle rejection (self-loop, 2-node cycle, multi-node, disconnected).
4. O(V + E) deterministic topological ordering using Kahn's algorithm with declaration-order queue preservation.
5. Exact compatibility with D0 WorkerContext frontier contract (including executable_obligation_ids).
6. Cross-task dependency contamination rejection.
7. Anti-aliasing and defensive isolation.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from domain.exceptions import (
    DuplicateObligationError,
    MissingDependencyError,
    CyclicDependencyError,
    CrossTaskContaminationError,
)
from domain.models import Obligation
from domain.types import ObligationStatus


@dataclass(frozen=True)
class FrontierSnapshot:
    """Immutable snapshot of the obligation graph frontier, matching D0 WorkerContext $defs/FrontierSnapshot."""
    ready_obligation_ids: Tuple[str, ...]
    blocked_obligation_ids: Tuple[str, ...]
    executable_obligation_ids: Tuple[str, ...]
    satisfied_obligation_ids: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        """Returns JSON-compatible dictionary matching the D0 Draft-2020-12 WorkerContext Frontier schema."""
        return {
            "ready_obligation_ids": list(self.ready_obligation_ids),
            "blocked_obligation_ids": list(self.blocked_obligation_ids),
            "executable_obligation_ids": list(self.executable_obligation_ids),
        }


class ObligationGraph:
    """Pure, deterministic obligation dependency graph with O(V + E) traversal and declaration-order preservation."""

    def __init__(self, task_id: Optional[str] = None):
        self._task_id = task_id
        self._obligations: Dict[str, Obligation] = {}
        self._order: List[str] = []                     # Preserves declaration order
        self._order_idx: Dict[str, int] = {}            # Fast declaration index lookup
        self._adj: Dict[str, List[str]] = {}            # Forward edges: dep_id -> [dependent_ids]
        self._rev_adj: Dict[str, List[str]] = {}        # Reverse edges: obl_id -> [dep_ids]
        self._dirty: bool = True
        self._topo_order_cache: Optional[Tuple[Obligation, ...]] = None

    @property
    def task_id(self) -> Optional[str]:
        return self._task_id

    def add_obligation(self, obligation: Obligation) -> 'ObligationGraph':
        """Adds an obligation to the graph, enforcing duplicate and cross-task invariants."""
        if not isinstance(obligation, Obligation):
            raise TypeError("Expected an Obligation instance.")

        # Invariant 1: Cross-task contamination check
        if self._task_id is None:
            self._task_id = obligation.task_id
        elif self._task_id != obligation.task_id:
            raise CrossTaskContaminationError(
                f"Cannot add obligation '{obligation.obligation_id}' (task '{obligation.task_id}') "
                f"to graph of task '{self._task_id}'."
            )

        # Invariant 2: Duplicate obligation ID rejection
        obl_id = obligation.obligation_id
        if obl_id in self._obligations:
            raise DuplicateObligationError(
                f"Obligation with ID '{obl_id}' already exists in graph."
            )

        self._obligations[obl_id] = obligation
        self._order_idx[obl_id] = len(self._order)
        self._order.append(obl_id)

        if obl_id not in self._adj:
            self._adj[obl_id] = []
        self._rev_adj[obl_id] = list(obligation.depends_on)

        # Update forward adjacency for prerequisites
        for dep in obligation.depends_on:
            if dep not in self._adj:
                self._adj[dep] = []
            self._adj[dep].append(obl_id)

        self._dirty = True
        self._topo_order_cache = None
        return self

    def get_obligation(self, obligation_id: str) -> Optional[Obligation]:
        """Returns the obligation or None."""
        return self._obligations.get(obligation_id)

    def validate(self) -> None:
        """Validates graph integrity in O(V + E): rejects missing dependencies and all cycle topologies."""
        if not self._dirty and self._topo_order_cache is not None:
            return

        # 1. Missing dependency reference check: O(V + E)
        for obl_id, deps in self._rev_adj.items():
            for dep in deps:
                if dep not in self._obligations:
                    raise MissingDependencyError(
                        f"Obligation '{obl_id}' depends on non-existent obligation '{dep}'."
                    )

        # 2. O(V + E) cycle detection and topological ordering using Kahn's algorithm
        in_degrees: Dict[str, int] = {obl_id: len(deps) for obl_id, deps in self._rev_adj.items()}

        # Initial queue of root nodes in declaration order
        queue: deque = deque([obl_id for obl_id in self._order if in_degrees[obl_id] == 0])
        topo_list: List[Obligation] = []

        while queue:
            curr_id = queue.popleft()
            topo_list.append(self._obligations[curr_id])

            # Collect newly freed nodes
            freed_nodes = []
            for dependent_id in self._adj.get(curr_id, ()):
                in_degrees[dependent_id] -= 1
                if in_degrees[dependent_id] == 0:
                    freed_nodes.append(dependent_id)

            # Sort freed nodes by declaration order to maintain deterministic declaration scheduling
            if len(freed_nodes) > 1:
                freed_nodes.sort(key=lambda nid: self._order_idx[nid])

            for node_id in freed_nodes:
                queue.append(node_id)

        if len(topo_list) != len(self._obligations):
            raise CyclicDependencyError(
                "Cyclic dependency detected in obligation graph."
            )

        self._topo_order_cache = tuple(topo_list)
        self._dirty = False

    def get_dependency_order(self) -> Tuple[Obligation, ...]:
        """Returns deterministic topological order of obligations in O(V + E), preserving declaration order on ties."""
        self.validate()
        assert self._topo_order_cache is not None
        return self._topo_order_cache

    def get_unmet_dependencies(self, obligation_id: str) -> Tuple[str, ...]:
        """Returns tuple of unmet dependency IDs for a given obligation, preserving declaration order."""
        obl = self._obligations.get(obligation_id)
        if not obl:
            raise KeyError(f"Obligation '{obligation_id}' not found in graph.")

        unmet = []
        for dep_id in obl.depends_on:
            dep_obl = self._obligations.get(dep_id)
            if dep_obl is None or dep_obl.status not in (ObligationStatus.SATISFIED, ObligationStatus.CONDITIONAL):
                unmet.append(dep_id)

        return tuple(unmet)

    def get_ready(self) -> Tuple[Obligation, ...]:
        """CORE-22: Deterministic Ready Frontier derivation in O(V + E), preserving declaration order."""
        self.validate()
        ready = []
        for obl_id in self._order:
            obl = self._obligations[obl_id]
            if obl.status == ObligationStatus.OPEN:
                if len(self.get_unmet_dependencies(obl_id)) == 0:
                    ready.append(obl)

        return tuple(ready)

    def get_blocked(self) -> Tuple[Obligation, ...]:
        """CORE-22: Deterministic Blocked Frontier derivation in O(V + E), preserving declaration order."""
        self.validate()
        blocked = []
        for obl_id in self._order:
            obl = self._obligations[obl_id]
            if obl.status == ObligationStatus.BLOCKED:
                blocked.append(obl)
            elif obl.status == ObligationStatus.OPEN and len(self.get_unmet_dependencies(obl_id)) > 0:
                blocked.append(obl)

        return tuple(blocked)

    def get_frontier(self) -> FrontierSnapshot:
        """Returns an immutable FrontierSnapshot compliant with D0 WorkerContext schema."""
        ready = tuple(o.obligation_id for o in self.get_ready())
        blocked = tuple(o.obligation_id for o in self.get_blocked())
        executable = ready
        satisfied = tuple(
            obl_id
            for obl_id in self._order
            if self._obligations[obl_id].status in (ObligationStatus.SATISFIED, ObligationStatus.CONDITIONAL)
        )
        return FrontierSnapshot(
            ready_obligation_ids=ready,
            blocked_obligation_ids=blocked,
            executable_obligation_ids=executable,
            satisfied_obligation_ids=satisfied,
        )

    def __len__(self) -> int:
        return len(self._obligations)
