"""Authoritative Erratum Governance, Open Issue Schema & Master Cross-Link Gate Engine.

Implements normative requirements for Chapter 10 Closure & Governance (Block 9, Lane B9-C):
- PD-CH10-012 (Line 4543): A frozen change MUST require a formal erratum path and concrete
  insufficiency/replay analysis; frozen source is never edited ad hoc.
- PD-CH10-013 (Line 4567): Every open issue MUST name impact, owner, evidence/decision needed,
  blocking phase, and status; OI-008 remains OPEN until two raw fresh-chat reviews are owner-supplied.
- PD-CH10-007 (Line 4594): Version/qualification and issue/claim registries MUST be internally
  cross-linked to the master.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary across Block 9 Lane C evaluation."""

REQUIRED_OPEN_ISSUE_FIELDS: FrozenSet[str] = frozenset({
    "impact",
    "owner",
    "evidence_or_decision_needed",
    "blocking_phase",
    "status",
})

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "REQUIRED_OPEN_ISSUE_FIELDS",
    "evaluate_pd_ch10_012_frozen_erratum_path",
    "evaluate_pd_ch10_013_open_issue_schema",
    "evaluate_pd_ch10_007_master_cross_links",
    "evaluate_b9_c_gate",
]


def evaluate_pd_ch10_012_frozen_erratum_path(
    formal_erratum_path: bool,
    insufficiency_analysis_present: bool,
    replay_analysis_present: bool,
    *,
    ad_hoc_source_edit: bool = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH10-012 (Line 4543): Frozen change requires formal erratum path, insufficiency and replay analysis."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH10-012",
            detail="Caller lacks qualified evaluator authority",
        )

    if ad_hoc_source_edit or not formal_erratum_path or not insufficiency_analysis_present or not replay_analysis_present:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH10-012",
            detail="Frozen change attempted without formal erratum path, insufficiency analysis, replay analysis, or ad-hoc source edit detected",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH10-012",
        detail="Formal erratum path followed with concrete insufficiency and replay analysis",
    )


def evaluate_pd_ch10_013_open_issue_schema(
    issue: Optional[Mapping[str, Any]],
    *,
    oi_008_owner_reviews_count: int = 0,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH10-013 (Line 4567): Open issues name impact, owner, evidence, phase, status; OI-008 requires 2 raw fresh-chat reviews."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH10-013",
            detail="Caller lacks qualified evaluator authority",
        )

    if not issue:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH10-013",
            detail="Open issue record missing entirely",
        )

    for field in REQUIRED_OPEN_ISSUE_FIELDS:
        val = issue.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH10-013",
                detail=f"Open issue missing required field: {field} (action_result: BLOCKED)",
            )

    issue_id = str(issue.get("id", "")).upper()
    status = str(issue.get("status", "")).upper()

    if "OI-008" in issue_id and status == "CLOSED":
        if oi_008_owner_reviews_count < 2:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH10-013",
                detail="OI-008 cannot be closed without two raw fresh-chat reviews owner-supplied (action_result: BLOCKED)",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH10-013",
        detail="Open issue satisfies complete schema and closure constraints",
    )


def evaluate_pd_ch10_007_master_cross_links(
    cross_linked_to_master: bool,
    *,
    unknown_references_present: bool = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH10-007 (Line 4594): Version/qualification and issue/claim registries internally cross-linked to master."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH10-007",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(cross_linked_to_master) is not bool or type(unknown_references_present) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH10-007",
            detail="Arguments must be exact bool",
        )

    if not cross_linked_to_master or unknown_references_present:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH10-007",
            detail="Registries contain unknown issue/citation/claim reference or missing internal cross-links to master",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH10-007",
        detail="Registries fully and consistently cross-linked to hash-verified master",
    )


def evaluate_b9_c_gate(
    payload: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Aggregate gate evaluator for Block 9 Lane C (PD-CH10-012..013, PD-CH10-007)."""
    return {
        "PD-CH10-012": evaluate_pd_ch10_012_frozen_erratum_path(
            payload.get("formal_erratum_path", False),
            payload.get("insufficiency_analysis_present", False),
            payload.get("replay_analysis_present", False),
            ad_hoc_source_edit=payload.get("ad_hoc_source_edit", False),
            authority=authority,
        ),
        "PD-CH10-013": evaluate_pd_ch10_013_open_issue_schema(
            payload.get("issue"),
            oi_008_owner_reviews_count=payload.get("oi_008_owner_reviews_count", 0),
            authority=authority,
        ),
        "PD-CH10-007": evaluate_pd_ch10_007_master_cross_links(
            payload.get("cross_linked_to_master", False),
            unknown_references_present=payload.get("unknown_references_present", False),
            authority=authority,
        ),
    }
