"""
S-Class EOS V11.2 - D5 Deterministic Ready / Blocked / Executable Frontier (§11.4, CORE-22, CORE-23).
Pure mathematical query model over canonical obligation state.
READY != EXECUTABLE distinction:
- Ready: OPEN obligation with all dependencies in SATISFIED or CONDITIONAL.
- Blocked: BLOCKED obligation or transitively dependent on a BLOCKED obligation.
- Executable: Ready obligation that satisfies active security policy and resource bounds.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple, Any
from domain.models import Obligation, Policy
from domain.types import ObligationStatus


@dataclass(frozen=True)
class ExecutionFrontier:
    """Immutable snapshot of the deterministic execution frontier (§11.4)."""
    ready_obligation_ids: Tuple[str, ...]
    blocked_obligation_ids: Tuple[str, ...]
    executable_obligation_ids: Tuple[str, ...]


def get_topological_dependency_order(obligations: Mapping[str, Obligation]) -> List[str]:
    """Kahn's algorithm for deterministic topological sort. Rejects cycles (CORE-23)."""
    in_degree: Dict[str, int] = {oid: 0 for oid in obligations}
    dependents: Dict[str, List[str]] = {oid: [] for oid in obligations}

    for oid, obl in obligations.items():
        for dep in obl.depends_on:
            if dep in obligations:
                in_degree[oid] += 1
                dependents[dep].append(oid)

    # Deterministic queue ordering by ID
    queue = sorted([oid for oid, deg in in_degree.items() if deg == 0])
    ordered: List[str] = []

    while queue:
        curr = queue.pop(0)
        ordered.append(curr)
        for dep_oid in sorted(dependents[curr]):
            in_degree[dep_oid] -= 1
            if in_degree[dep_oid] == 0:
                queue.append(dep_oid)
        queue.sort()

    if len(ordered) != len(obligations):
        raise ValueError("Cyclic dependency detected in obligation graph (CORE-23 violation).")

    return ordered


def compute_ready_frontier(obligations: Mapping[str, Obligation]) -> Tuple[str, ...]:
    """Returns all obligations in OPEN status whose prerequisites are SATISFIED or CONDITIONAL."""
    ready: List[str] = []
    for oid, obl in obligations.items():
        if obl.status != ObligationStatus.OPEN:
            continue

        all_prereqs_met = True
        for dep_id in obl.depends_on:
            dep_obl = obligations.get(dep_id)
            if not dep_obl or dep_obl.status not in (ObligationStatus.SATISFIED, ObligationStatus.CONDITIONAL):
                all_prereqs_met = False
                break

        if all_prereqs_met:
            ready.append(oid)

    return tuple(sorted(ready))


def compute_blocked_frontier(obligations: Mapping[str, Obligation]) -> Tuple[str, ...]:
    """Returns all obligations that are directly BLOCKED or transitively dependent on a BLOCKED obligation."""
    blocked: Set[str] = set()

    # 1. Directly blocked
    for oid, obl in obligations.items():
        if obl.status == ObligationStatus.BLOCKED:
            blocked.add(oid)

    # 2. Transitive propagation
    changed = True
    while changed:
        changed = False
        for oid, obl in obligations.items():
            if oid not in blocked:
                for dep_id in obl.depends_on:
                    if dep_id in blocked:
                        blocked.add(oid)
                        changed = True
                        break

    return tuple(sorted(blocked))


def compute_executable_frontier(
    obligations: Mapping[str, Obligation],
    policies: Mapping[str, Policy],
    active_security_profile: str = "DEFAULT",
    budget_remaining: float = 100.0,
    disallowed_categories: Optional[Sequence[Any]] = None,
) -> Tuple[str, ...]:
    """Returns the subset of Ready obligations satisfying active security policy & resource bounds (CORE-22)."""
    ready_ids = compute_ready_frontier(obligations)
    disallowed = set(disallowed_categories or [])

    executable: List[str] = []
    for oid in ready_ids:
        obl = obligations[oid]
        # Check disallowed category
        if obl.category in disallowed:
            continue

        # Check policy binding
        if obl.policy_id and obl.policy_id not in policies:
            # Missing policy fails closed
            continue

        # Check resource budget
        if budget_remaining <= 0.0:
            continue

        executable.append(oid)

    return tuple(sorted(executable))


def compute_frontier(
    obligations: Mapping[str, Obligation],
    policies: Optional[Mapping[str, Policy]] = None,
    active_security_profile: str = "DEFAULT",
    budget_remaining: float = 100.0,
    disallowed_categories: Optional[Sequence[Any]] = None,
) -> ExecutionFrontier:
    """Computes the complete, deterministic ExecutionFrontier snapshot."""
    pol_map = policies or {}
    ready = compute_ready_frontier(obligations)
    blocked = compute_blocked_frontier(obligations)
    executable = compute_executable_frontier(
        obligations=obligations,
        policies=pol_map,
        active_security_profile=active_security_profile,
        budget_remaining=budget_remaining,
        disallowed_categories=disallowed_categories,
    )
    return ExecutionFrontier(
        ready_obligation_ids=ready,
        blocked_obligation_ids=blocked,
        executable_obligation_ids=executable,
    )
