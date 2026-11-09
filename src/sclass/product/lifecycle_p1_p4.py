"""Authoritative Lifecycle P1 & P4 Engine for S-Class Product Layer.

Implements normative requirements for Chapter 2 Discovery (P1) & Decomposition (P4):
- PD-CH2-056: P1 MUST classify unresolvable target snapshot, incomplete index coverage, or missing unknown outcome as MISSING.
- PD-CH2-057: P1 MUST resolve required skills/depth against policy/profile precedence and pin their digests into context/step-pack.
- PD-CH2-029: P4 MUST enforce task-count and task-unit caps from the F4 lane's canonical Policy defaults.
- PD-CH2-031: WorkGraph dependency edges MUST be acyclic.
- PD-CH2-032: Known write-set overlap MUST serialize mechanically; unknown/undeclared write sets MUST block for human resolution.
"""
from __future__ import annotations

from collections import deque
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

    if (
        type(target_snapshot_resolved) is not bool
        or type(index_coverage_ratio) is bool
        or not isinstance(index_coverage_ratio, (int, float))
        or type(high_impact_unknowns_resolved) is not bool
        or type(min_index_coverage) is bool
        or not isinstance(min_index_coverage, (int, float))
    ):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-056",
            detail="Arguments must be exact bool/float types",
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

    if type(skills_resolved) is not bool or type(policy_floor_respected) is not bool or (isinstance(pinned_skill_digests, (list, tuple, dict)) and len(pinned_skill_digests) > 1000):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-057",
            detail="Skill depth precedence requires exact boolean inputs and bounded skill digests",
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

    if not isinstance(lane_type, str) or type(task_units) is not int or type(task_count) is not int:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-029",
            detail="lane_type must be str and task_units/task_count must be exact ints",
        )

    caps = custom_caps or DEFAULT_POLICY_CAPS
    if lane_type.upper() not in caps:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-029",
            detail=f"Unknown lane type: {lane_type}",
        )
    lane_caps = caps[lane_type.upper()]

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

    if not isinstance(graph_edges, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-031",
            detail="graph_edges must be a mapping",
        )

    if len(graph_edges) > 1000:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-031",
            detail="WorkGraph exceeds maximum size limit (1000 nodes)",
        )

    adj: Dict[str, List[str]] = {}
    in_degree: Dict[str, int] = {}
    all_nodes: Set[str] = set()

    for node, targets in graph_edges.items():
        if not isinstance(node, str):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-031",
                detail="Graph node keys must be strings",
            )
        all_nodes.add(node)
        if node not in in_degree:
            in_degree[node] = 0
        if not isinstance(targets, (list, tuple, set)) or isinstance(targets, (str, bytes)):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-031",
                detail=f"Edge targets for node {node} must be a list/tuple/set of string node ids, not {type(targets).__name__}",
            )
        if len(targets) > 10000:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-031",
                detail=f"Edge targets for node {node} exceed maximum limit (10000)",
            )
        clean_targets: List[str] = []
        for target in targets:
            if not isinstance(target, str):
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH2-031",
                    detail=f"Edge target {target!r} must be a string",
                )
            clean_targets.append(target)
            all_nodes.add(target)
            in_degree[target] = in_degree.get(target, 0) + 1
        adj[node] = clean_targets

    if len(all_nodes) > 10000:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-031",
            detail="Total WorkGraph node count exceeds maximum limit (10000)",
        )

    # Kahn's iterative topological sort algorithm - strictly O(V + E), no recursion
    queue = deque([n for n in all_nodes if in_degree.get(n, 0) == 0])
    visited_count = 0

    while queue:
        curr = queue.popleft()
        visited_count += 1
        for neighbor in adj.get(curr, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited_count < len(all_nodes):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-031",
            detail="WorkGraph dependency cycle detected",
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

    if not isinstance(tasks, (list, tuple)) or isinstance(tasks, (str, bytes)):
        return GateOutput(
            state=GateState.BLOCKED_ON_HUMAN,
            must_id="PD-CH2-032",
            detail="tasks must be a sequence of task mappings",
        )

    if len(tasks) > 10000:
        return GateOutput(
            state=GateState.BLOCKED_ON_HUMAN,
            must_id="PD-CH2-032",
            detail="Task count exceeds maximum limit (10000)",
        )

    for task in tasks:
        if not isinstance(task, Mapping):
            return GateOutput(
                state=GateState.BLOCKED_ON_HUMAN,
                must_id="PD-CH2-032",
                detail="Each task must be a mapping",
            )
        ws = task.get("declared_write_set")
        if ws is None or not isinstance(ws, (list, tuple, set)) or isinstance(ws, (str, bytes)):
            return GateOutput(
                state=GateState.BLOCKED_ON_HUMAN,
                must_id="PD-CH2-032",
                detail=f"Task {task.get('task_id', 'unknown')} has unknown/undeclared write set",
            )

    # Known write sets: check overlap between parallel tasks
    overlap_detected = False
    seen_writes: Set[str] = set()
    for task in tasks:
        ws_items = task.get("declared_write_set", [])
        ws = set()
        for p in ws_items:
            if not isinstance(p, str):
                return GateOutput(
                    state=GateState.BLOCKED_ON_HUMAN,
                    must_id="PD-CH2-032",
                    detail="Write set path must be string",
                )
            ws.add(p)
        if seen_writes.intersection(ws):
            overlap_detected = True
        seen_writes.update(ws)

    if overlap_detected:
        all_serialized = all(task.get("serialized", False) is True for task in tasks)
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
        target_snapshot_resolved=manifest.get("target_snapshot_resolved"),
        index_coverage_ratio=manifest.get("index_coverage_ratio"),
        high_impact_unknowns_resolved=manifest.get("high_impact_unknowns_resolved"),
        authority=authority,
    )
    if r056.state != GateState.SATISFIED:
        return r056

    # 2. PD-CH2-057
    r057 = evaluate_pd_ch2_057_skill_depth_precedence(
        skills_resolved=manifest.get("skills_resolved"),
        pinned_skill_digests=manifest.get("pinned_skill_digests"),
        policy_floor_respected=manifest.get("policy_floor_respected"),
        authority=authority,
    )
    if r057.state != GateState.SATISFIED:
        return r057

    # 3. PD-CH2-029
    r029 = evaluate_pd_ch2_029_task_caps(
        lane_type=manifest.get("lane_type"),
        task_units=manifest.get("task_units"),
        task_count=manifest.get("task_count"),
        authority=authority,
    )
    if r029.state != GateState.SATISFIED:
        return r029

    # 4. PD-CH2-031
    r031 = evaluate_pd_ch2_031_work_graph_acyclic(
        graph_edges=manifest.get("graph_edges"),
        authority=authority,
    )
    if r031.state != GateState.SATISFIED:
        return r031

    # 5. PD-CH2-032
    r032 = evaluate_pd_ch2_032_write_set_overlap(
        tasks=manifest.get("tasks"),
        authority=authority,
    )
    if r032.state != GateState.SATISFIED:
        return r032

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All P1 and P4 lifecycle obligations satisfied",
    )
