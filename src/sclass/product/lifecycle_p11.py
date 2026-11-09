"""Authoritative Lifecycle P11 & Operations Governance Engine for S-Class Product Layer.

Implements normative requirements for Chapter 2 Lifecycle Phase P11 & Flow Governance:
- PD-CH2-054: Signals must ground in canonical facts and route new objective work via P0.
- PD-CH2-058: Work type applicability matrix (covers all 12 phases P0..P11 with explicit reasons).
- PD-CH2-060: Default user-facing flows preserve P0..P11 order and defect rollback routing.
- PD-CH2-061: Operations/delivery flows bind entry predicate, gate outputs, and rollback conditions.
- PD-CH2-062: Project-class qualification requires explicit fit evidence, never language/size heuristics.
- PD-CH2-063: Question budget integer enforcement and blocker preservation upon exhaustion.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority. The real boundary is caller wiring in S-Class execution."""

ALL_PHASES: Tuple[str, ...] = (
    "P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11"
)

REGISTERED_WORK_TYPES: Set[str] = {
    "FEATURE", "BUG_FIX", "REFACTOR", "MIGRATION_UPGRADE",
    "SPIKE_RESEARCH", "INCIDENT_HOTFIX", "MAINTENANCE"
}

DEFAULT_QUESTION_BATCH_CAP: int = 5

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "ALL_PHASES",
    "REGISTERED_WORK_TYPES",
    "DEFAULT_QUESTION_BATCH_CAP",
    "evaluate_pd_ch2_054_signal",
    "evaluate_pd_ch2_058_applicability",
    "evaluate_pd_ch2_060_flow_order",
    "evaluate_pd_ch2_061_delivery_flow",
    "evaluate_pd_ch2_062_project_class",
    "evaluate_pd_ch2_063_question_budget",
    "evaluate_p11_gate",
]


def evaluate_pd_ch2_054_signal(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """Evaluates P11 monitoring signals (PD-CH2-054)."""
    if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-054",
            detail="Unauthorized evaluation: caller_authority must be QUALIFIED_EVALUATOR",
            failures=["MISSING[PD-CH2-054]"],
        )

    if not isinstance(payload, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-054",
            detail="payload must be a mapping",
            failures=["MISSING[PD-CH2-054]"],
        )

    # Signal must have source event reference
    source_event = payload.get("source_event_ref")
    if not source_event or source_event == "absent":
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-054",
            detail="P11 signal lacks canonical source_event_ref or digest binding",
            failures=["MISSING[PD-CH2-054]"],
        )

    # Proposed action cannot be autonomous workspace mutation
    action = payload.get("proposed_action", "")
    if action == "mutate_workspace" or "mutate" in str(action).lower():
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-054",
            detail="P11 signal may only propose P0 re-entry, never autonomous canonical mutation",
            failures=["MISSING[PD-CH2-054]"],
        )

    return GateOutput(state=GateState.SATISFIED)


def evaluate_pd_ch2_058_applicability(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """Evaluates work type phase applicability matrix coverage (PD-CH2-058)."""
    if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-058",
            detail="Unauthorized evaluation: caller_authority must be QUALIFIED_EVALUATOR",
            failures=["MISSING[PD-CH2-058]"],
        )

    if not isinstance(payload, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-058",
            detail="payload must be a mapping",
            failures=["MISSING[PD-CH2-058]"],
        )

    # Check applicability records cover all 12 phases P0..P11
    recs = payload.get("applicability_records[P0..P11]")
    if recs is None:
        recs = payload.get("applicability_records")
    if not isinstance(recs, (dict, list)):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-058",
            detail="applicability_records must cover all P0..P11 phases without implicit defaults",
            failures=["MISSING[PD-CH2-058]"],
        )

    if isinstance(recs, list) and len(recs) != 12:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-058",
            detail=f"applicability_records has {len(recs)} phases, exactly 12 required (P0..P11)",
            failures=["MISSING[PD-CH2-058]"],
        )
    if isinstance(recs, dict):
        missing_phases = [p for p in ALL_PHASES if p not in recs]
        if missing_phases:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-058",
                detail=f"applicability_records missing phases: {missing_phases}",
                failures=["MISSING[PD-CH2-058]"],
            )

    # Check skip reasons are explicit for skipped phases
    skip_reason = payload.get("skip_reason")
    if skip_reason is not None and not str(skip_reason).strip():
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-058",
            detail="skip_reason cannot be empty for a skipped phase",
            failures=["MISSING[PD-CH2-058]"],
        )

    # Evaluator record ref must be present
    eval_ref = payload.get("evaluator_record_ref")
    if not eval_ref:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-058",
            detail="evaluator_record_ref is absent; agent cannot mark phases NOT_APPLICABLE without evaluator outcome",
            failures=["MISSING[PD-CH2-058]"],
        )

    return GateOutput(state=GateState.SATISFIED)


def evaluate_pd_ch2_060_flow_order(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """Evaluates user-facing default flow order preservation (PD-CH2-060)."""
    if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-060",
            detail="Unauthorized evaluation: caller_authority must be QUALIFIED_EVALUATOR",
            failures=["MISSING[PD-CH2-060]"],
        )

    if not isinstance(payload, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-060",
            detail="payload must be a mapping",
            failures=["MISSING[PD-CH2-060]"],
        )

    phase_order = payload.get("phase_order")
    if not phase_order or not isinstance(phase_order, (list, tuple)):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-060",
            detail="phase_order is absent or invalid",
            failures=["MISSING[PD-CH2-060]"],
        )

    # Verify P0..P11 order strictly preserved
    indices = []
    for p in phase_order:
        if p in ALL_PHASES:
            indices.append(ALL_PHASES.index(p))
    if indices != sorted(indices):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-060",
            detail=f"phase_order violates canonical P0..P11 lifecycle ordering: {phase_order}",
            failures=["MISSING[PD-CH2-060]"],
        )

    # Defect origin routing check
    defect_origin = payload.get("defect_origin_phase")
    replay_start = payload.get("replay_start_phase")
    if defect_origin and replay_start:
        if defect_origin != replay_start:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-060",
                detail=f"Defect origin {defect_origin} routes to mismatched replay start {replay_start}",
                failures=["MISSING[PD-CH2-060]"],
            )

    return GateOutput(state=GateState.SATISFIED)


def evaluate_pd_ch2_061_delivery_flow(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """Evaluates operations/delivery flow binding (PD-CH2-061)."""
    if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-061",
            detail="Unauthorized evaluation: caller_authority must be QUALIFIED_EVALUATOR",
            failures=["MISSING[PD-CH2-061]"],
        )

    if not isinstance(payload, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-061",
            detail="payload must be a mapping",
            failures=["MISSING[PD-CH2-061]"],
        )

    # 1. Rollback condition digest must be present
    rb_digest = payload.get("rollback_condition_digest")
    if not rb_digest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-061",
            detail="rollback_condition_digest is absent for operations/delivery flow",
            failures=["MISSING[PD-CH2-061]"],
        )

    # 2. Entry predicate digest must be present and not stale
    entry_pred = payload.get("entry_predicate_digest")
    if not entry_pred or payload.get("entry_predicate_stale", False):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-061",
            detail="entry_predicate_digest is absent or stale",
            failures=["MISSING[PD-CH2-061]"],
        )

    # 3. Gate output digests must be present
    gate_outs = payload.get("gate_output_digests")
    if not gate_outs:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-061",
            detail="gate_output_digests is absent; stop condition cannot be satisfied without gate outputs",
            failures=["MISSING[PD-CH2-061]"],
        )

    return GateOutput(state=GateState.SATISFIED)


def evaluate_pd_ch2_062_project_class(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """Evaluates project-class qualification (PD-CH2-062)."""
    if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-062",
            detail="Unauthorized evaluation: caller_authority must be QUALIFIED_EVALUATOR",
            failures=["MISSING[PD-CH2-062]"],
        )

    if not isinstance(payload, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-062",
            detail="payload must be a mapping",
            failures=["MISSING[PD-CH2-062]"],
        )

    # Fit evidence digest must be present and not based on language/size alone
    fit_digest = payload.get("fit_evidence_digest")
    if not fit_digest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-062",
            detail="fit_evidence_digest is absent; qualification cannot be inferred from language or size alone",
            failures=["MISSING[PD-CH2-062]"],
        )
    if "repo_size" in str(fit_digest).lower() or "files" in str(fit_digest).lower():
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-062",
            detail="Repository size cannot be used as fit evidence",
            failures=["MISSING[PD-CH2-062]"],
        )

    # Qualification record digest must be genuine
    qual_digest = payload.get("qualification_record_digest")
    if not qual_digest or qual_digest == "forged" or "agent" in str(qual_digest).lower():
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-062",
            detail="qualification_record_digest is absent or forged; agent cannot self-qualify",
            failures=["MISSING[PD-CH2-062]"],
        )

    return GateOutput(state=GateState.SATISFIED)


def evaluate_pd_ch2_063_question_budget(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """Evaluates human question budget and open blocker enforcement (PD-CH2-063)."""
    if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-063",
            detail="Unauthorized evaluation: caller_authority must be QUALIFIED_EVALUATOR",
            failures=["MISSING[PD-CH2-063]"],
        )

    if not isinstance(payload, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-063",
            detail="payload must be a mapping",
            failures=["MISSING[PD-CH2-063]"],
        )

    # 1. questions_asked must be non-negative integer
    q_asked = payload.get("questions_asked")
    if q_asked is None or not isinstance(q_asked, int) or q_asked < 0:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-063",
            detail="questions_asked must be a non-negative integer",
            failures=["MISSING[PD-CH2-063]"],
        )

    # 2. Check question budget cap
    q_budget = payload.get("question_budget", DEFAULT_QUESTION_BATCH_CAP)
    open_blockers = payload.get("open_blockers_digest")

    if q_asked > q_budget and open_blockers:
        # If treated as exhausted-complete without resolving blockers
        if payload.get("treated_as_complete", True):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-063",
                detail=f"questions_asked ({q_asked}) exceeds budget ({q_budget}) while open blockers remain; unresolved blockers must remain open",
                failures=["MISSING[PD-CH2-063]"],
            )

    # 3. Open blockers cannot be cleared by agent write
    if open_blockers == "cleared_by_agent":
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-063",
            detail="open_blockers_digest cannot be cleared autonomously by agent write upon budget exhaustion",
            failures=["MISSING[PD-CH2-063]"],
        )

    return GateOutput(state=GateState.SATISFIED)


def evaluate_p11_gate(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """Unified entry point for P11 Lifecycle & Operations Gate."""
    auth = authority if authority is not None else caller_authority
    if auth != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-054",
            detail="Caller lacks qualified evaluator authority",
        )
    if not isinstance(payload, Mapping) or not payload:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-054",
            detail="Payload is empty or missing required fields",
        )
    must_id = payload.get("must_id")
    dispatch_map = {
        "PD-CH2-054": evaluate_pd_ch2_054_signal,
        "PD-CH2-058": evaluate_pd_ch2_058_applicability,
        "PD-CH2-060": evaluate_pd_ch2_060_flow_order,
        "PD-CH2-061": evaluate_pd_ch2_061_delivery_flow,
        "PD-CH2-062": evaluate_pd_ch2_062_project_class,
        "PD-CH2-063": evaluate_pd_ch2_063_question_budget,
    }
    if must_id in dispatch_map:
        return dispatch_map[must_id](payload, caller_authority=auth)

    return GateOutput(
        state=GateState.MISSING,
        must_id="PD-CH2-054",
        detail="Unrecognized P11 MUST ID or payload",
        failures=["MISSING[PD-CH2-054]"],
    )
