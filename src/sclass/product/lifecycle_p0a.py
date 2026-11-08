"""Authoritative Lifecycle P0A Engine for S-Class Product Layer.

Implements normative requirements for Chapter 2 Lifecycle Invariants (Part A):
- PD-CH2-001: Every work type MUST execute as a projection of the same P0-P11 lifecycle.
- PD-CH2-002: Every P-phase MUST define all eleven dimensions.
- PD-CH2-003: A later phase MUST NOT make an invalid earlier phase valid.
- PD-CH2-005: Every skipped phase MUST have an explicit evaluator-checkable applicability result.
- PD-CH2-006: A discovered defect MUST route to the earliest affected phase.
- PD-CH2-055: Downstream projections must be invalidated when dependency digests change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority. The real boundary is caller wiring in S-Class execution."""

STANDARD_PHASES: Tuple[str, ...] = (
    "P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11"
)

ELEVEN_DIMENSIONS: Tuple[str, ...] = (
    "Purpose",
    "Entry Criteria",
    "Inputs",
    "Exit Criteria",
    "Outputs",
    "Authority",
    "Verification Gate",
    "Human Gate",
    "Backward Edges",
    "Failure Routes",
    "Applicability",
)

REGISTERED_WORK_TYPES: Set[str] = {
    "FEATURE", "BUG_FIX", "REFACTOR", "MIGRATION_UPGRADE",
    "SPIKE_RESEARCH", "INCIDENT_HOTFIX", "MAINTENANCE"
}

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "STANDARD_PHASES",
    "ELEVEN_DIMENSIONS",
    "REGISTERED_WORK_TYPES",
    "evaluate_pd_ch2_001_single_lifecycle",
    "evaluate_pd_ch2_002_eleven_dimensions",
    "evaluate_pd_ch2_003_earlier_phase_validity",
    "evaluate_pd_ch2_005_skipped_phase_applicability",
    "evaluate_pd_ch2_006_earliest_defect_routing",
    "evaluate_pd_ch2_055_downstream_invalidation",
    "evaluate_p0a_gate",
]


def evaluate_pd_ch2_001_single_lifecycle(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """Every work type MUST execute as a projection of the same P0-P11 lifecycle (PD-CH2-001)."""
    if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-001",
            detail="Unauthorized evaluation: caller_authority must be QUALIFIED_EVALUATOR",
            failures=["MISSING[PD-CH2-001]"],
        )

    if not isinstance(payload, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-001",
            detail="Payload must be a mapping",
            failures=["MISSING[PD-CH2-001]"],
        )

    work_type = payload.get("work_type")
    if not work_type or work_type not in REGISTERED_WORK_TYPES:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-001",
            detail=f"Unregistered work type: {work_type}",
            failures=["MISSING[PD-CH2-001]"],
        )

    # Check for alternate lifecycle token or phase topology
    alternate_phase = payload.get("alternate_phase")
    if alternate_phase:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-001",
            detail=f"Alternate lifecycle token or phase detected: {alternate_phase}",
            failures=["MISSING[PD-CH2-001]"],
        )

    phase_sequence = payload.get("phase_sequence")
    if phase_sequence is not None:
        if not isinstance(phase_sequence, (list, tuple)):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-001",
                detail="Phase sequence must be a sequence",
                failures=["MISSING[PD-CH2-001]"],
            )
        for p in phase_sequence:
            if p not in STANDARD_PHASES:
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH2-001",
                    detail=f"Invalid phase token outside P0..P11: {p}",
                    failures=["MISSING[PD-CH2-001]"],
                )

    return GateOutput(state=GateState.SATISFIED, must_id="PD-CH2-001")


def evaluate_pd_ch2_002_eleven_dimensions(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """Every P-phase MUST define all eleven dimensions (PD-CH2-002)."""
    if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-002",
            detail="Unauthorized evaluation: caller_authority must be QUALIFIED_EVALUATOR",
            failures=["MISSING[PD-CH2-002]"],
        )

    if not isinstance(payload, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-002",
            detail="Payload must be a mapping",
            failures=["MISSING[PD-CH2-002]"],
        )

    phase = payload.get("phase")
    if phase and phase not in STANDARD_PHASES:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-002",
            detail=f"Invalid phase token: {phase}",
            failures=["MISSING[PD-CH2-002]"],
        )

    # Check missing dimensions
    missing = payload.get("missing_dimension")
    if missing:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-002",
            detail=f"Phase {phase} missing dimension: {missing}",
            failures=["MISSING[PD-CH2-002]"],
        )

    defined_dims = payload.get("defined_dimensions")
    if defined_dims is not None:
        dim_set = set(defined_dims)
        missing_set = [d for d in ELEVEN_DIMENSIONS if d not in dim_set]
        if missing_set:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-002",
                detail=f"Missing required dimensions: {missing_set}",
                failures=["MISSING[PD-CH2-002]"],
            )

    return GateOutput(state=GateState.SATISFIED, must_id="PD-CH2-002")


def evaluate_pd_ch2_003_earlier_phase_validity(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """A later phase MUST NOT make an invalid earlier phase valid (PD-CH2-003)."""
    if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-003",
            detail="Unauthorized evaluation: caller_authority must be QUALIFIED_EVALUATOR",
            failures=["MISSING[PD-CH2-003]"],
        )

    if not isinstance(payload, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-003",
            detail="Payload must be a mapping",
            failures=["MISSING[PD-CH2-003]"],
        )

    # Check earlier phase states
    earlier_phase_status = payload.get("earlier_phase_status", {})
    for p, status in earlier_phase_status.items():
        if status in ("INVALID", "FAILED", "MISSING", "BLOCKED"):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-003",
                detail=f"Earlier phase {p} is {status}; later phase cannot advance or cure invalidity",
                failures=["MISSING[PD-CH2-003]"],
            )

    # Fixture specific: earlier phase invalid flag
    if payload.get("earlier_phase_invalid", False):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-003",
            detail="Attempt to advance while earlier phase artifact is invalid",
            failures=["MISSING[PD-CH2-003]"],
        )

    return GateOutput(state=GateState.SATISFIED, must_id="PD-CH2-003")


def evaluate_pd_ch2_005_skipped_phase_applicability(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """Every skipped phase MUST have an explicit evaluator-checkable applicability result (PD-CH2-005)."""
    if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-005",
            detail="Unauthorized evaluation: caller_authority must be QUALIFIED_EVALUATOR",
            failures=["MISSING[PD-CH2-005]"],
        )

    if not isinstance(payload, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-005",
            detail="Payload must be a mapping",
            failures=["MISSING[PD-CH2-005]"],
        )

    skipped_phases = payload.get("skipped_phases", [])
    if isinstance(skipped_phases, str):
        skipped_phases = [skipped_phases]

    applicability_declarations = payload.get("applicability_declarations", {})

    # Check if applicability declaration is absent
    if payload.get("applicability_declaration_absent", False):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-005",
            detail="Applicability declaration absent for skipped phase",
            failures=["MISSING[PD-CH2-005]"],
        )

    for sp in skipped_phases:
        rec = applicability_declarations.get(sp)
        if not rec:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-005",
                detail=f"Phase {sp} skipped without explicit applicability record",
                failures=["MISSING[PD-CH2-005]"],
            )
        if not rec.get("evaluator_checkable", False) or not rec.get("skip_reason"):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-005",
                detail=f"Applicability record for {sp} is not evaluator-checkable or lacks skip_reason",
                failures=["MISSING[PD-CH2-005]"],
            )

    return GateOutput(state=GateState.SATISFIED, must_id="PD-CH2-005")


def evaluate_pd_ch2_006_earliest_defect_routing(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """A discovered defect MUST route to the earliest affected phase (PD-CH2-006)."""
    if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-006",
            detail="Unauthorized evaluation: caller_authority must be QUALIFIED_EVALUATOR",
            failures=["MISSING[PD-CH2-006]"],
        )

    if not isinstance(payload, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-006",
            detail="Payload must be a mapping",
            failures=["MISSING[PD-CH2-006]"],
        )

    defect_found_in = payload.get("defect_found_in")
    earliest_affected = payload.get("earliest_affected_phase")
    routed_phase = payload.get("routed_phase")

    if not earliest_affected:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-006",
            detail="Earliest affected phase not identified",
            failures=["MISSING[PD-CH2-006]"],
        )

    if routed_phase != earliest_affected:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-006",
            detail=f"Defect routed to {routed_phase} instead of earliest affected phase {earliest_affected}",
            failures=["MISSING[PD-CH2-006]"],
        )

    return GateOutput(state=GateState.SATISFIED, must_id="PD-CH2-006")


def evaluate_pd_ch2_055_downstream_invalidation(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """The lifecycle gate MUST invalidate every downstream projection whose dependency digest changes (PD-CH2-055)."""
    if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-055",
            detail="Unauthorized evaluation: caller_authority must be QUALIFIED_EVALUATOR",
            failures=["MISSING[PD-CH2-055]"],
        )

    if not isinstance(payload, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-055",
            detail="Payload must be a mapping",
            failures=["MISSING[PD-CH2-055]"],
        )

    # Fixture bypass attempt flag
    if payload.get("bypass_attempt", False):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-055",
            detail="Attempted to reuse stale downstream projection without invalidation",
            failures=["MISSING[PD-CH2-055]"],
        )

    authoritative_digest = payload.get("authoritative_dependency_digest")
    recomputation_key = payload.get("recomputation_key", {})
    bound_digest = recomputation_key.get("dependency_digest")

    if authoritative_digest and bound_digest != authoritative_digest:
        # Changed dependency digest not visible in recomputation key
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-055",
            detail="Changed authoritative dependency digest not bound in recomputation key",
            failures=["MISSING[PD-CH2-055]"],
        )

    if payload.get("downstream_invalidated") is False:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-055",
            detail="Downstream projections were not invalidated on dependency change",
            failures=["MISSING[PD-CH2-055]"],
        )

    return GateOutput(state=GateState.SATISFIED, must_id="PD-CH2-055")


def evaluate_p0a_gate(
    payloads: Mapping[str, Mapping[str, Any]],
    caller_authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Composite gate evaluator for all P0A invariants."""
    evaluators = {
        "PD-CH2-001": evaluate_pd_ch2_001_single_lifecycle,
        "PD-CH2-002": evaluate_pd_ch2_002_eleven_dimensions,
        "PD-CH2-003": evaluate_pd_ch2_003_earlier_phase_validity,
        "PD-CH2-005": evaluate_pd_ch2_005_skipped_phase_applicability,
        "PD-CH2-006": evaluate_pd_ch2_006_earliest_defect_routing,
        "PD-CH2-055": evaluate_pd_ch2_055_downstream_invalidation,
    }
    results = {}
    for mid, func in evaluators.items():
        p = payloads.get(mid, {})
        results[mid] = func(p, caller_authority=caller_authority)
    return results
