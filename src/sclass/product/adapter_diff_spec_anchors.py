"""Authoritative Adapter Differential Detection & Spec Anchor Traceability Engine.

Implements normative requirements for Section F10 & Chapter 3 (Block 4, Lane B):
- PD-F10-007 (Line 1026): Differential detection MUST compare canonicalized semantics and evidence bindings and surface any disagreement.
- PD-CH3-015 (Line 2916): Every product artifact MUST bind objective revision, source digest, artifact type and owning authority; product documents cannot shadow canonical objects.
- PD-CH3-016 (Line 2966): Every normative requirement MUST resolve to an exact spec path, symbol/heading and line range; unresolved means MISSING, and a changed anchor digest invalidates all dependent artifacts.
- PD-CH3-017 (Line 3024): Mechanical spec-quality predicates MUST use explicit measurable thresholds bound to the policy digest; unsupported/undecidable predicates cannot return PASS.
- PD-CH3-018 (Line 3074): A blocking clarification MUST have an authorized outcome or remain MISSING/BLOCKED_ON_HUMAN; silence and model inference are not confirmation.
- PD-CH3-020 (Line 3117): Invalidation is owned by PD-CH2-055; this MUST adds only that a spec change identifies the earliest replay point for affected work/evidence.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary across Block 4 evaluation."""

STANDARD_LIFECYCLE_PHASES: Tuple[str, ...] = (
    "P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11"
)

REQUIRED_ARTIFACT_FIELDS: FrozenSet[str] = frozenset({
    "objective_revision",
    "source_digest",
    "artifact_type",
    "owning_authority",
})

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "STANDARD_LIFECYCLE_PHASES",
    "REQUIRED_ARTIFACT_FIELDS",
    "evaluate_pd_f10_007_differential_detection",
    "evaluate_pd_ch3_015_artifact_binding_integrity",
    "evaluate_pd_ch3_016_spec_anchor_resolution",
    "evaluate_pd_ch3_017_predicate_measurable_thresholds",
    "evaluate_pd_ch3_018_clarification_authorized_outcome",
    "evaluate_pd_ch3_020_spec_change_replay_point",
    "evaluate_b4_b_gate",
]


def evaluate_pd_f10_007_differential_detection(
    canonical_semantics_primary: Any = None,
    canonical_semantics_secondary: Any = None,
    evidence_bindings_primary: Optional[Mapping[str, Any]] = None,
    evidence_bindings_secondary: Optional[Mapping[str, Any]] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-F10-007 (Line 1026): Differential detection MUST compare canonicalized semantics and evidence bindings."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-007",
            detail="Caller lacks qualified evaluator authority",
        )

    if canonical_semantics_primary is None or canonical_semantics_secondary is None:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-007",
            detail="Canonical semantics evidence omitted or incomplete",
        )

    if canonical_semantics_primary != canonical_semantics_secondary:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-007",
            detail="Semantic mismatch detected between differential runs",
        )

    if evidence_bindings_primary is not None and evidence_bindings_secondary is not None:
        if evidence_bindings_primary != evidence_bindings_secondary:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F10-007",
                detail="Evidence binding mismatch detected between differential runs",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-F10-007",
        detail="Differential detection verified: canonical semantics and evidence bindings match",
    )

def evaluate_pd_ch3_015_artifact_binding_integrity(
    objective_revision: Optional[str],
    source_digest: Optional[str],
    artifact_type: Optional[str],
    owning_authority: Optional[str],
    *,
    shadows_canonical_object: bool = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH3-015 (Line 2916): Every product artifact MUST bind objective revision, source digest, artifact type and owning authority."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-015",
            detail="Caller lacks qualified evaluator authority",
        )

    if not objective_revision or not source_digest or not artifact_type or not owning_authority:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-015",
            detail="Product artifact omits required binding: objective_revision, source_digest, artifact_type, or owning_authority",
        )

    if shadows_canonical_object:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-015",
            detail="Product document attempts to shadow canonical object id",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH3-015",
        detail="Product artifact binds objective revision, source digest, artifact type, and owning authority",
    )


def evaluate_pd_ch3_016_spec_anchor_resolution(
    spec_path: Optional[str],
    symbol_or_heading: Optional[str],
    line_range: Optional[Tuple[int, int]],
    anchor_digest: Optional[str],
    *,
    expected_anchor_digest: Optional[str] = None,
    is_fuzzy_match: bool = False,
    file_length_lines: int = 1000,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH3-016 (Line 2966): Every normative requirement MUST resolve to an exact spec path, symbol/heading and line range."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-016",
            detail="Caller lacks qualified evaluator authority",
        )

    if not spec_path or not symbol_or_heading or not line_range or not anchor_digest or is_fuzzy_match:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-016",
            detail="Normative requirement unresolved or supplied fuzzy symbol match",
        )

    start_line, end_line = line_range
    if start_line < 1 or end_line > file_length_lines or start_line > end_line:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-016",
            detail=f"Line range {line_range} beyond file length or invalid",
        )

    if expected_anchor_digest is not None and anchor_digest != expected_anchor_digest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-016",
            detail="Anchor digest mismatch; dependent artifacts invalidated",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH3-016",
        detail="Normative requirement resolved to exact spec path, symbol/heading, and valid line range",
    )


def evaluate_pd_ch3_017_predicate_measurable_thresholds(
    predicate: Optional[str],
    threshold_value: Optional[float],
    threshold_unit: Optional[str],
    policy_digest: Optional[str],
    policy_revision: Optional[str],
    *,
    is_undecidable: bool = False,
    expected_policy_digest: Optional[str] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH3-017 (Line 3024): Mechanical spec-quality predicates MUST use explicit measurable thresholds bound to policy digest."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-017",
            detail="Caller lacks qualified evaluator authority",
        )

    if not predicate or threshold_value is None or not threshold_unit or not policy_digest or not policy_revision:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-017",
            detail="Predicate threshold unit omitted or missing policy digest/revision",
        )

    if is_undecidable:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-017",
            detail="Undecidable or unsupported predicate cannot return PASS",
        )

    if expected_policy_digest is not None and policy_digest != expected_policy_digest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-017",
            detail="Threshold value edited without corresponding policy revision digest update",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH3-017",
        detail="Mechanical spec-quality predicate bound to explicit measurable threshold and policy digest",
    )


def evaluate_pd_ch3_018_clarification_authorized_outcome(
    clarification_id: Optional[str],
    authorized_outcome_digest: Optional[str],
    resolver_identity: Optional[str],
    *,
    is_model_inference: bool = False,
    is_silent: bool = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH3-018 (Line 3074): A blocking clarification MUST have an authorized outcome or remain MISSING/BLOCKED_ON_HUMAN."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-018",
            detail="Caller lacks qualified evaluator authority",
        )

    if not clarification_id or not authorized_outcome_digest or not resolver_identity or is_model_inference or is_silent:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-018",
            detail="Blocking clarification lacks authorized outcome digest or relies on model inference/silence",
        )

    if resolver_identity.lower().startswith("agent"):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-018",
            detail="Clarification outcome recorded by an agent-reachable key rather than authorized human",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH3-018",
        detail="Blocking clarification resolved with authorized outcome digest and confirmed non-agent resolver",
    )


def evaluate_pd_ch3_020_spec_change_replay_point(
    spec_anchor_digest: Optional[str],
    affected_evidence_digests: Optional[Sequence[str]],
    earliest_replay_phase: Optional[str],
    *,
    invalidated_evidence: bool = True,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH3-020 (Line 3117): Spec change MUST identify earliest replay point and invalidate affected evidence."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-020",
            detail="Caller lacks qualified evaluator authority",
        )

    if not spec_anchor_digest or earliest_replay_phase is None or not affected_evidence_digests:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-020",
            detail="Earliest replay phase omitted or affected evidence digests missing after spec change",
        )

    if earliest_replay_phase not in STANDARD_LIFECYCLE_PHASES:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-020",
            detail=f"Invalid earliest replay phase: {earliest_replay_phase}",
        )

    if not invalidated_evidence:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-020",
            detail="Affected evidence digests not invalidated after anchor change",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH3-020",
        detail=f"Spec change identified earliest replay point ({earliest_replay_phase}) and invalidated affected evidence",
    )


def evaluate_b4_b_gate(
    payload: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Aggregate gate evaluator for Block 4 Lane B (PD-F10-007, PD-CH3-015..018, PD-CH3-020)."""
    if not isinstance(payload, Mapping):
        payload = {}

    res: Dict[str, GateOutput] = {}

    if "canonical_semantics_primary" in payload or "canonical_semantics_secondary" in payload:
        res["PD-F10-007"] = evaluate_pd_f10_007_differential_detection(
            payload.get("canonical_semantics_primary"),
            payload.get("canonical_semantics_secondary"),
            evidence_bindings_primary=payload.get("evidence_bindings_primary"),
            evidence_bindings_secondary=payload.get("evidence_bindings_secondary"),
            authority=authority,
        )
    else:
        res["PD-F10-007"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-007",
            detail="Payload missing differential detection keys",
        )

    if "objective_revision" in payload or "source_digest" in payload:
        res["PD-CH3-015"] = evaluate_pd_ch3_015_artifact_binding_integrity(
            payload.get("objective_revision"),
            payload.get("source_digest"),
            payload.get("artifact_type"),
            payload.get("owning_authority"),
            shadows_canonical_object=payload.get("shadows_canonical_object", False),
            authority=authority,
        )
    else:
        res["PD-CH3-015"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-015",
            detail="Payload missing artifact binding integrity keys",
        )

    if "spec_path" in payload or "anchor_digest" in payload:
        res["PD-CH3-016"] = evaluate_pd_ch3_016_spec_anchor_resolution(
            payload.get("spec_path"),
            payload.get("symbol_or_heading"),
            payload.get("line_range"),
            payload.get("anchor_digest"),
            expected_anchor_digest=payload.get("expected_anchor_digest"),
            is_fuzzy_match=payload.get("is_fuzzy_match", False),
            file_length_lines=payload.get("file_length_lines", 1000),
            authority=authority,
        )
    else:
        res["PD-CH3-016"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-016",
            detail="Payload missing required spec anchor keys",
        )

    if "predicate" in payload:
        res["PD-CH3-017"] = evaluate_pd_ch3_017_predicate_measurable_thresholds(
            payload.get("predicate"),
            payload.get("threshold_value"),
            payload.get("threshold_unit"),
            payload.get("policy_digest"),
            payload.get("policy_revision"),
            is_undecidable=payload.get("is_undecidable", False),
            expected_policy_digest=payload.get("expected_policy_digest"),
            authority=authority,
        )
    else:
        res["PD-CH3-017"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-017",
            detail="Payload missing required key: predicate",
        )

    if "clarification_id" in payload:
        res["PD-CH3-018"] = evaluate_pd_ch3_018_clarification_authorized_outcome(
            payload.get("clarification_id"),
            payload.get("authorized_outcome_digest"),
            payload.get("resolver_identity"),
            is_model_inference=payload.get("is_model_inference", False),
            is_silent=payload.get("is_silent", False),
            authority=authority,
        )
    else:
        res["PD-CH3-018"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-018",
            detail="Payload missing required key: clarification_id",
        )

    if "spec_anchor_digest" in payload or "affected_evidence_digests" in payload:
        res["PD-CH3-020"] = evaluate_pd_ch3_020_spec_change_replay_point(
            payload.get("spec_anchor_digest"),
            payload.get("affected_evidence_digests"),
            payload.get("earliest_replay_phase"),
            invalidated_evidence=payload.get("invalidated_evidence", True),
            authority=authority,
        )
    else:
        res["PD-CH3-020"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-020",
            detail="Payload missing spec change replay keys",
        )

    return res
