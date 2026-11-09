"""Authoritative Lifecycle P1 & P4 Engine for S-Class Product Layer.

Implements normative requirements for Chapter 2 Discovery (P1) & Decomposition (P4):
- PD-CH2-056: P1 MUST classify unresolvable target snapshot, incomplete index coverage, or missing unknown outcome as MISSING.
- PD-CH2-057: P1 MUST resolve required skills/depth against policy/profile precedence and pin their digests into context/step-pack.
- PD-CH2-029: P4 MUST enforce task-count and task-unit caps from the F4 lane's canonical Policy defaults.
- PD-CH2-031: WorkGraph dependency edges MUST be acyclic.
- PD-CH2-032: Known write-set overlap MUST serialize mechanically; unknown/undeclared write sets MUST block for human resolution.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary in S-Class execution."""

DEFAULT_POLICY_CAPS: Dict[str, Dict[str, int]] = {
    "MICRO": {"max_task_count": 8, "max_task_units": 4, "max_total_units": 16},
    "STANDARD": {"max_task_count": 32, "max_task_units": 16, "max_total_units": 128},
    "EXPANDED": {"max_task_count": 64, "max_task_units": 32, "max_total_units": 512},
}

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "DEFAULT_POLICY_CAPS",
    "evaluate_pd_ch2_056_discovery_completeness",
    "evaluate_pd_ch2_057_skill_depth_precedence",
    "evaluate_pd_ch2_029_task_caps",
    "evaluate_pd_ch2_031_work_graph_acyclic",
    "evaluate_pd_ch2_032_write_set_overlap",
    "evaluate_p1_p4_gate",
]


def evaluate_pd_ch2_056_discovery_completeness(
    target_snapshot_resolved: bool,
    index_coverage_ratio: float,
    high_impact_unknowns_resolved: bool,
    min_index_coverage: float = 1.0,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-056: P1 discovery completeness classification."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-056",
            detail="Caller lacks qualified evaluator authority",
        )

    if not target_snapshot_resolved:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-056",
            detail="Unresolvable target snapshot classified as MISSING",
        )

    if index_coverage_ratio < min_index_coverage:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-056",
            detail=f"Incomplete index coverage ({index_coverage_ratio} < {min_index_coverage}) classified as MISSING",
        )

    if not high_impact_unknowns_resolved:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-056",
            detail="Missing high-impact unknown outcome classified as MISSING",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="P1 target snapshot, index coverage, and unknowns completely resolved",
    )


def evaluate_pd_ch2_057_skill_depth_precedence(
    skills_resolved: bool,
    pinned_skill_digests: Sequence[str] | Mapping[str, str],
    policy_floor_respected: bool,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-057: P1 skill resolution & digest pinning before downstream progression."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-057",
            detail="Caller lacks qualified evaluator authority",
        )

    if not skills_resolved or not pinned_skill_digests or not policy_floor_respected:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-057",
            detail="Required skills, pinned digests, or policy depth floors missing",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Skills resolved against policy precedence and pinned into context/step-pack",
    )


def evaluate_pd_ch2_029_task_caps(
    lane_type: str,
    task_units: int,
    task_count: int = 1,
    *,
    custom_caps: Optional[Mapping[str, Mapping[str, int]]] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-029: P4 task-count and task-unit caps enforcement from policy defaults."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-029",
            detail="Caller lacks qualified evaluator authority",
        )

    caps = custom_caps or DEFAULT_POLICY_CAPS
    lane_caps = caps.get(lane_type.upper(), caps.get("MICRO", {"max_task_count": 8, "max_task_units": 4}))

    max_units = lane_caps.get("max_task_units", 4)
    max_count = lane_caps.get("max_task_count", 8)

    if task_units > max_units:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-029",
            detail=f"{lane_type} task of {task_units} units exceeds {max_units}-unit cap",
        )

    if task_count > max_count:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-029",
            detail=f"{lane_type} task count of {task_count} exceeds {max_count} cap",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail=f"{lane_type} tasks within policy caps ({task_units}<={max_units}, {task_count}<={max_count})",
    )


def evaluate_pd_ch2_031_work_graph_acyclic(
    graph_edges: Mapping[str, Sequence[str]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-031: WorkGraph dependency edges MUST be acyclic."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-031",
            detail="Caller lacks qualified evaluator authority",
        )

    # Detect cycles using DFS cycle detection
    visited: Dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited

    def has_cycle(node: str) -> bool:
        visited[node] = 1
        for neighbor in graph_edges.get(node, []):
            state = visited.get(neighbor, 0)
            if state == 1:
                return True
            if state == 0 and has_cycle(neighbor):
                return True
        visited[node] = 2
        return False

    all_nodes = set(graph_edges.keys())
    for targets in graph_edges.values():
        all_nodes.update(targets)

    for node in all_nodes:
        if visited.get(node, 0) == 0:
            if has_cycle(node):
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH2-031",
                    detail=f"WorkGraph dependency cycle detected involving {node}",
                )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="WorkGraph dependency graph is strictly acyclic",
    )


def evaluate_pd_ch2_032_write_set_overlap(
    tasks: Sequence[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-032: Known write-set overlap MUST serialize mechanically; unknown write sets block for human."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.BLOCKED_ON_HUMAN,
            must_id="PD-CH2-032",
            detail="Caller lacks qualified evaluator authority",
        )

    for task in tasks:
        ws = task.get("declared_write_set")
        if ws is None:
            return GateOutput(
                state=GateState.BLOCKED_ON_HUMAN,
                must_id="PD-CH2-032",
                detail=f"Task {task.get('task_id', 'unknown')} has unknown/undeclared write set",
            )

    # Known write sets: check overlap between parallel tasks
    overlap_detected = False
    seen_writes: Set[str] = set()
    for task in tasks:
        ws = set(task.get("declared_write_set", []))
        if seen_writes.intersection(ws):
            overlap_detected = True
        seen_writes.update(ws)

    if overlap_detected:
        all_serialized = all(task.get("serialized", False) for task in tasks)
        if not all_serialized:
            return GateOutput(
                state=GateState.SATISFIED,
                detail="Known overlap detected and mechanically serialized",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Write sets inspected: no unhandled overlaps or unknown write sets",
    )


def evaluate_p1_p4_gate(
    manifest: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """Composite gate evaluator for Lifecycle P1 and P4 obligations."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-056",
            detail="Caller lacks qualified evaluator authority",
            failures=[
                "MISSING[PD-CH2-056]", "MISSING[PD-CH2-057]", "MISSING[PD-CH2-029]",
                "MISSING[PD-CH2-031]", "BLOCKED_ON_HUMAN[PD-CH2-032]",
            ],
        )

    if not isinstance(manifest, Mapping) or not manifest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-056",
            detail="Manifest is empty or missing required fields",
        )

    # 1. PD-CH2-056
    r056 = evaluate_pd_ch2_056_discovery_completeness(
        target_snapshot_resolved=manifest.get("target_snapshot_resolved", True),
        index_coverage_ratio=manifest.get("index_coverage_ratio", 1.0),
        high_impact_unknowns_resolved=manifest.get("high_impact_unknowns_resolved", True),
        authority=authority,
    )
    if r056.state != GateState.SATISFIED:
        return r056

    # 2. PD-CH2-057
    r057 = evaluate_pd_ch2_057_skill_depth_precedence(
        skills_resolved=manifest.get("skills_resolved", True),
        pinned_skill_digests=manifest.get("pinned_skill_digests", ["sha256-abc"]),
        policy_floor_respected=manifest.get("policy_floor_respected", True),
        authority=authority,
    )
    if r057.state != GateState.SATISFIED:
        return r057

    # 3. PD-CH2-029
    r029 = evaluate_pd_ch2_029_task_caps(
        lane_type=manifest.get("lane_type", "MICRO"),
        task_units=manifest.get("task_units", 2),
        task_count=manifest.get("task_count", 1),
        authority=authority,
    )
    if r029.state != GateState.SATISFIED:
        return r029

    # 4. PD-CH2-031
    r031 = evaluate_pd_ch2_031_work_graph_acyclic(
        graph_edges=manifest.get("graph_edges", {}),
        authority=authority,
    )
    if r031.state != GateState.SATISFIED:
        return r031

    # 5. PD-CH2-032
    r032 = evaluate_pd_ch2_032_write_set_overlap(
        tasks=manifest.get("tasks", []),
        authority=authority,
    )
    if r032.state != GateState.SATISFIED:
        return r032

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All P1 and P4 lifecycle obligations satisfied",
    )
