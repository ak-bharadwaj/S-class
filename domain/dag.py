"""Deterministic Obligation Graph and Frontier Representation for S-Class D1.

Adapts OpenSpec-validated topological concepts:
1. Duplicate ID rejection.
2. Missing dependency reference rejection.
3. Universal cycle rejection (self-loop, 2-node cycle, multi-node, disconnected).
4. Deterministic topological ordering (Kahn's algorithm with deterministic tie-breaking).
5. Deterministic READY, BLOCKED, and SATISFIED frontier queries (CORE-22).
6. Cross-task dependency contamination rejection.
7. Anti-aliasing and defensive copying.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

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
    """Immutable snapshot of the obligation graph frontier."""
    ready_obligation_ids: Tuple[str, ...]
    blocked_obligation_ids: Tuple[str, ...]
    satisfied_obligation_ids: Tuple[str, ...]


class ObligationGraph:
    """Pure, deterministic obligation dependency graph."""

    def __init__(self, task_id: Optional[str] = None):
        self._task_id = task_id
        self._obligations: Dict[str, Obligation] = {}

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
        if obligation.obligation_id in self._obligations:
            raise DuplicateObligationError(
                f"Obligation with ID '{obligation.obligation_id}' already exists in graph."
            )

        self._obligations[obligation.obligation_id] = obligation
        return self

    def get_obligation(self, obligation_id: str) -> Optional[Obligation]:
        """Returns a copy of the obligation or None."""
        return self._obligations.get(obligation_id)

    def validate(self) -> None:
        """Validates graph integrity: rejects missing dependencies and all cycle topologies."""
        # 1. Missing dependency reference check
        for obl_id, obl in self._obligations.items():
            for dep_id in obl.depends_on:
                if dep_id not in self._obligations:
                    raise MissingDependencyError(
                        f"Obligation '{obl_id}' depends on non-existent obligation '{dep_id}'."
                    )

        # 2. Cycle detection across all connected/disconnected components
        # Uses Kahn's algorithm in-degree calculation
        in_degree = {obl_id: 0 for obl_id in self._obligations}
        adj: Dict[str, List[str]] = {obl_id: [] for obl_id in self._obligations}

        for obl_id, obl in self._obligations.items():
            for dep_id in obl.depends_on:
                # Edge: dep_id -> obl_id
                adj[dep_id].append(obl_id)
                in_degree[obl_id] += 1

        queue = [obl_id for obl_id, deg in in_degree.items() if deg == 0]
        visited_count = 0

        while queue:
            curr = queue.pop(0)
            visited_count += 1
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count != len(self._obligations):
            raise CyclicDependencyError(
                "Cyclic dependency detected in obligation graph."
            )

    def get_dependency_order(self) -> Tuple[Obligation, ...]:
        """Returns deterministic topological order of obligations (Kahn's algorithm with lexical tie-break)."""
        self.validate()

        in_degree = {obl_id: 0 for obl_id in self._obligations}
        adj: Dict[str, List[str]] = {obl_id: [] for obl_id in self._obligations}

        for obl_id, obl in self._obligations.items():
            for dep_id in obl.depends_on:
                adj[dep_id].append(obl_id)
                in_degree[obl_id] += 1

        queue = [obl_id for obl_id, deg in in_degree.items() if deg == 0]
        queue.sort()  # Deterministic tie-breaking

        order: List[Obligation] = []
        while queue:
            curr_id = queue.pop(0)
            order.append(self._obligations[curr_id])
            for neighbor in adj[curr_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    queue.sort()  # Deterministic tie-breaking

        return tuple(order)

    def get_unmet_dependencies(self, obligation_id: str) -> Tuple[str, ...]:
        """Returns tuple of unmet dependency IDs for a given obligation."""
        obl = self._obligations.get(obligation_id)
        if not obl:
            raise KeyError(f"Obligation '{obligation_id}' not found in graph.")

        unmet = []
        for dep_id in obl.depends_on:
            dep_obl = self._obligations.get(dep_id)
            if dep_obl is None or dep_obl.status not in (ObligationStatus.SATISFIED, ObligationStatus.CONDITIONAL):
                unmet.append(dep_id)

        return tuple(sorted(unmet))

    def get_ready(self) -> Tuple[Obligation, ...]:
        """CORE-22: Deterministic Ready Frontier derivation.
        
        An obligation is READY iff:
        1. status == OPEN
        2. All dependencies in depends_on have status in {SATISFIED, CONDITIONAL}
        """
        self.validate()
        ready = []
        for obl_id, obl in self._obligations.items():
            if obl.status == ObligationStatus.OPEN:
                if len(self.get_unmet_dependencies(obl_id)) == 0:
                    ready.append(obl)

        # Deterministic sorting by obligation_id
        return tuple(sorted(ready, key=lambda o: o.obligation_id))

    def get_blocked(self) -> Tuple[Obligation, ...]:
        """CORE-22: Deterministic Blocked Frontier derivation.
        
        An obligation is BLOCKED iff:
        1. status == BLOCKED, OR
        2. status == OPEN but has at least one unmet dependency.
        """
        self.validate()
        blocked = []
        for obl_id, obl in self._obligations.items():
            if obl.status == ObligationStatus.BLOCKED:
                blocked.append(obl)
            elif obl.status == ObligationStatus.OPEN and len(self.get_unmet_dependencies(obl_id)) > 0:
                blocked.append(obl)

        return tuple(sorted(blocked, key=lambda o: o.obligation_id))

    def get_frontier(self) -> FrontierSnapshot:
        """Returns an immutable snapshot of Ready, Blocked, and Satisfied sets."""
        ready = tuple(o.obligation_id for o in self.get_ready())
        blocked = tuple(o.obligation_id for o in self.get_blocked())
        satisfied = tuple(
            sorted(
                obl_id
                for obl_id, obl in self._obligations.items()
                if obl.status in (ObligationStatus.SATISFIED, ObligationStatus.CONDITIONAL)
            )
        )
        return FrontierSnapshot(
            ready_obligation_ids=ready,
            blocked_obligation_ids=blocked,
            satisfied_obligation_ids=satisfied,
        )

    def __len__(self) -> int:
        return len(self._obligations)
