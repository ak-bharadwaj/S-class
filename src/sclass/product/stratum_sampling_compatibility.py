"""Authoritative Stratum Sampling, Compatibility Matrix & Roadmap Gate Engine.

Implements normative requirements for Chapter 9 & 10 (Block 9, Lane B9-B):
- PD-CH9-006 (Line 4401): Pack promotion MUST not proceed if false-completion worsens or any registered
  stratum has fewer completed paired tasks than policy-bound minimum (default 100 per stratum).
- PD-CH9-007 (Line 4402): Secret-egress/control claims MUST use qualified evidence on launched workers.
- PD-CH10-008 (Line 4426): Compatibility MUST be explicit across kernel, protocol, schema, adapter,
  and pack versions; unsupported pairs block.
- PD-CH10-009 (Line 4450): Audit export MUST bind canonical sequence range, digests, gate inputs/outputs,
  and explicit truncation or missing-data declarations.
- PD-CH10-010 (Line 4485): The roadmap MUST use only H0-H7, assign each capability a dependency and
  exit test, and must not represent planning as implemented capability.
- PD-CH10-011 (Line 4519): Every surfaced implementation fact MUST be classified as keep/replace/retire/qualify
  and evidence-backed or UNVERIFIED.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary across Block 9 Lane B evaluation."""

VALID_ROADMAP_HORIZONS: FrozenSet[str] = frozenset({
    "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7"
})

VALID_FACT_CLASSIFICATIONS: FrozenSet[str] = frozenset({
    "keep", "replace", "retire", "qualify"
})

REQUIRED_AUDIT_EXPORT_FIELDS: FrozenSet[str] = frozenset({
    "sequence_range",
    "digests",
    "gate_inputs_outputs",
    "declarations",
})

REQUIRED_COMPATIBILITY_FIELDS: FrozenSet[str] = frozenset({
    "kernel_version",
    "protocol_version",
    "schema_version",
    "adapter_version",
    "pack_version",
})

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "VALID_ROADMAP_HORIZONS",
    "VALID_FACT_CLASSIFICATIONS",
    "REQUIRED_AUDIT_EXPORT_FIELDS",
    "REQUIRED_COMPATIBILITY_FIELDS",
    "evaluate_pd_ch9_006_stratum_sampling_promotion",
    "evaluate_pd_ch9_007_secret_egress_claims",
    "evaluate_pd_ch10_008_explicit_compatibility",
    "evaluate_pd_ch10_009_audit_export_bindings",
    "evaluate_pd_ch10_010_roadmap_integrity",
    "evaluate_pd_ch10_011_fact_classification",
    "evaluate_b9_b_gate",
]


def evaluate_pd_ch9_006_stratum_sampling_promotion(
    false_completion_worsened: bool,
    stratum_counts: Mapping[str, int],
    *,
    minimum_per_stratum: int = 100,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH9-006 (Line 4401): Promotion blocked if false-completion worsens or stratum below minimum (100)."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-006",
            detail="Caller lacks qualified evaluator authority",
        )
    try:

        if false_completion_worsened:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH9-006",
                detail="False-completion rate worsened on evaluation (action_result: BLOCKED)",
            )

        if not stratum_counts:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH9-006",
                detail="Zero registered strata provided (action_result: BLOCKED)",
            )

        for stratum, count in stratum_counts.items():
            if count < minimum_per_stratum:
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH9-006",
                    detail=f"Stratum {stratum} has {count} paired tasks, below minimum {minimum_per_stratum} (action_result: BLOCKED)",
                )

        return GateOutput(
            state=GateState.SATISFIED,
            must_id="PD-CH9-006",
            detail="False-completion rate not worsened and all strata meet minimum paired task threshold",
        )
    except Exception as e:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-006",
            detail=f"Adversarial input rejected: {type(e).__name__}",
        )


def evaluate_pd_ch9_007_secret_egress_claims(
    qualified_receipt_on_launched_worker: bool,
    *,
    unqualified_scanner_or_native_host_write: Optional[bool] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH9-007 (Line 4402): Secret-egress claims require qualified evidence on launched worker; no host-native."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-007",
            detail="Caller lacks qualified evaluator authority",
        )

    _us = False if unqualified_scanner_or_native_host_write is None else unqualified_scanner_or_native_host_write
    if type(qualified_receipt_on_launched_worker) is not bool or type(_us) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-007",
            detail="Arguments must be exact bool",
        )

    if _us or not qualified_receipt_on_launched_worker:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-007",
            detail="Unqualified egress scanner, native host write, or missing qualified receipt on launched worker",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH9-007",
        detail="Secret-egress controls backed by qualified receipt on launched worker",
    )


def evaluate_pd_ch10_008_explicit_compatibility(
    compatibility_matrix: Optional[Mapping[str, Any]],
    *,
    unsupported_pair_present: Optional[bool] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH10-008 (Line 4426): Explicit compatibility across kernel, protocol, schema, adapter, pack."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH10-008",
            detail="Caller lacks qualified evaluator authority",
        )
    try:

        if not compatibility_matrix or unsupported_pair_present:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH10-008",
                detail="Compatibility matrix missing or unsupported version pair detected",
            )

        for field in REQUIRED_COMPATIBILITY_FIELDS:
            if field not in compatibility_matrix:
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH10-008",
                    detail=f"Compatibility matrix missing required version field: {field}",
                )

        return GateOutput(
            state=GateState.SATISFIED,
            must_id="PD-CH10-008",
            detail="Compatibility explicitly declared and verified across all subsystems",
        )
    except Exception as e:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH10-008",
            detail=f"Adversarial input rejected: {type(e).__name__}",
        )


def evaluate_pd_ch10_009_audit_export_bindings(
    audit_export: Optional[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH10-009 (Line 4450): Audit export binds sequence range, digests, gate I/O, truncation declarations."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH10-009",
            detail="Caller lacks qualified evaluator authority",
        )
    try:

        if not audit_export:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH10-009",
                detail="Audit export payload missing entirely",
            )

        for field in REQUIRED_AUDIT_EXPORT_FIELDS:
            val = audit_export.get(field)
            if val is None or (isinstance(val, (str, list, dict, set)) and len(val) == 0):
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH10-009",
                    detail=f"Audit export missing required field: {field}",
                )

        return GateOutput(
            state=GateState.SATISFIED,
            must_id="PD-CH10-009",
            detail="Audit export fully binds sequence range, digests, gate I/O, and declarations",
        )
    except Exception as e:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH10-009",
            detail=f"Adversarial input rejected: {type(e).__name__}",
        )


def evaluate_pd_ch10_010_roadmap_integrity(
    capabilities: Sequence[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH10-010 (Line 4485): Roadmap uses only H0-H7, assigns dependencies and exit tests, no planning as implemented."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH10-010",
            detail="Caller lacks qualified evaluator authority",
        )
    try:

        if not capabilities:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH10-010",
                detail="Roadmap capability list missing or empty",
            )

        for cap in capabilities:
            horizon = cap.get("horizon")
            if horizon not in VALID_ROADMAP_HORIZONS:
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH10-010",
                    detail=f"Capability {cap.get('id', 'unknown')} has invalid horizon {horizon} (must be H0-H7)",
                )
            if not cap.get("dependency") or not cap.get("exit_test"):
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH10-010",
                    detail=f"Capability {cap.get('id', 'unknown')} missing dependency or exit test",
                )
            if cap.get("planning_claimed_as_implemented", False):
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH10-010",
                    detail=f"Capability {cap.get('id', 'unknown')} improperly represents planning as implemented",
                )

        return GateOutput(
            state=GateState.SATISFIED,
            must_id="PD-CH10-010",
            detail="Roadmap conforms to H0-H7 with valid dependencies, exit tests, and honest implementation status",
        )
    except Exception as e:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH10-010",
            detail=f"Adversarial input rejected: {type(e).__name__}",
        )


def evaluate_pd_ch10_011_fact_classification(
    facts: Sequence[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH10-011 (Line 4519): Implementation facts classified as keep/replace/retire/qualify and evidence-backed or UNVERIFIED."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH10-011",
            detail="Caller lacks qualified evaluator authority",
        )
    try:

        if not facts:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH10-011",
                detail="Implementation facts list empty or missing",
            )

        for fact in facts:
            classification = fact.get("classification")
            if classification not in VALID_FACT_CLASSIFICATIONS:
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH10-011",
                    detail=f"Fact {fact.get('id', 'unknown')} has invalid classification {classification}",
                )
            has_evidence = bool(fact.get("evidence_ref"))
            is_unverified = bool(fact.get("unverified", False))
            if not has_evidence and not is_unverified:
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH10-011",
                    detail=f"Fact {fact.get('id', 'unknown')} neither evidence-backed nor explicitly UNVERIFIED",
                )

        return GateOutput(
            state=GateState.SATISFIED,
            must_id="PD-CH10-011",
            detail="All implementation facts properly classified and evidence-backed or UNVERIFIED",
        )
    except Exception as e:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH10-011",
            detail=f"Adversarial input rejected: {type(e).__name__}",
        )


def evaluate_b9_b_gate(
    payload: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Aggregate gate evaluator for Block 9 Lane B (PD-CH9-006..007, PD-CH10-008..011)."""
    if not isinstance(payload, Mapping):
        payload = {}
    return {
        "PD-CH9-006": evaluate_pd_ch9_006_stratum_sampling_promotion(
            payload.get("false_completion_worsened", False),
            payload.get("stratum_counts", {}),
            minimum_per_stratum=payload.get("minimum_per_stratum", 100),
            authority=authority,
        ),
        "PD-CH9-007": evaluate_pd_ch9_007_secret_egress_claims(
            payload.get("qualified_receipt_on_launched_worker", False),
            unqualified_scanner_or_native_host_write=payload.get("unqualified_scanner_or_native_host_write", False),
            authority=authority,
        ),
        "PD-CH10-008": evaluate_pd_ch10_008_explicit_compatibility(
            payload.get("compatibility_matrix"),
            unsupported_pair_present=payload.get("unsupported_pair_present", False),
            authority=authority,
        ),
        "PD-CH10-009": evaluate_pd_ch10_009_audit_export_bindings(
            payload.get("audit_export"),
            authority=authority,
        ),
        "PD-CH10-010": evaluate_pd_ch10_010_roadmap_integrity(
            payload.get("capabilities", []),
            authority=authority,
        ),
        "PD-CH10-011": evaluate_pd_ch10_011_fact_classification(
            payload.get("facts", []),
            authority=authority,
        ),
    }
