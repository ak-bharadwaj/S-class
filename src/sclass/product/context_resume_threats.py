"""Authoritative Context Resume Anchor & Threat Containment Engine.

Implements normative requirements for Chapter 4 Context & Threat Containment (Block 4, Lane F):
- PD-CH4-007 (Line 3467): Context resume MUST rebuild anchors from canonical state and reject transcript-only authority.
- PD-CH4-008 (Line 3468): All listed threat classes MUST map to a detection, gate, containment, and fixture.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import (
    GateOutput,
    GateState,
    require_bool_field,
    require_str_field,
)

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary across Block 4 evaluation."""

REQUIRED_THREAT_MAPPING_FIELDS: FrozenSet[str] = frozenset({
    "detection",
    "gate",
    "containment",
    "fixture",
})

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "REQUIRED_THREAT_MAPPING_FIELDS",
    "evaluate_pd_ch4_007_context_resume_anchors",
    "evaluate_pd_ch4_008_threat_matrix_containment",
    "evaluate_b4_f_gate",
]


def evaluate_pd_ch4_007_context_resume_anchors(
    canonical_anchors_present: bool,
    pinned_guidance_digests: Optional[Sequence[str]],
    step_pack_digest: Optional[str],
    *,
    transcript_only_authority: bool = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH4-007 (Line 3467): Context resume MUST rebuild anchors from canonical state and reject transcript-only authority."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-007",
            detail="Caller lacks qualified evaluator authority",
        )

    if err := (
        require_bool_field("PD-CH4-007", "canonical_anchors_present", canonical_anchors_present)
        or require_bool_field("PD-CH4-007", "transcript_only_authority", transcript_only_authority)
        or require_str_field("PD-CH4-007", "step_pack_digest", step_pack_digest)
    ):
        return err

    if (
        not isinstance(pinned_guidance_digests, Sequence)
        or isinstance(pinned_guidance_digests, (str, bytes))
        or not pinned_guidance_digests
    ):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-007",
            detail=f"Invalid type or empty value for key 'pinned_guidance_digests': expected non-empty Sequence, got {type(pinned_guidance_digests).__name__}",
        )

    if not canonical_anchors_present or transcript_only_authority:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-007",
            detail="Context resume missing canonical anchors, guidance digests, or relies on transcript-only authority",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH4-007",
        detail="Context resume rebuilt anchors from canonical state and pinned guidance digests",
    )


def evaluate_pd_ch4_008_threat_matrix_containment(
    threat_matrix_rows: Optional[Sequence[Mapping[str, Any]]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH4-008 (Line 3468): All listed threat classes MUST map to a detection, gate, containment, and fixture."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-008",
            detail="Caller lacks qualified evaluator authority",
        )

    if not threat_matrix_rows:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-008",
            detail="Empty or missing threat matrix rows",
        )

    for row in threat_matrix_rows:
        threat_id = row.get("threat_id", "UNKNOWN")
        for fld in REQUIRED_THREAT_MAPPING_FIELDS:
            if not row.get(fld):
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH4-008",
                    detail=f"Threat class '{threat_id}' missing required mapping: {fld}",
                )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH4-008",
        detail="All listed threat classes map to detection, gate, containment, and fixture",
    )


def evaluate_b4_f_gate(
    payload: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Aggregate gate evaluator for Block 4 Lane F (PD-CH4-007, PD-CH4-008)."""
    return {
        "PD-CH4-007": evaluate_pd_ch4_007_context_resume_anchors(
            payload.get("canonical_anchors_present", False),
            payload.get("pinned_guidance_digests"),
            payload.get("step_pack_digest"),
            transcript_only_authority=payload.get("transcript_only_authority", False),
            authority=authority,
        ),
        "PD-CH4-008": evaluate_pd_ch4_008_threat_matrix_containment(
            payload.get("threat_matrix_rows"),
            authority=authority,
        ),
    }
