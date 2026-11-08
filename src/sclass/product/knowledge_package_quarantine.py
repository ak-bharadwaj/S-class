"""Authoritative Knowledge Package Quarantine & Verification Gate Engine.

Implements normative requirements for Chapter 6 Knowledge Management (Block 6, Lane B6-A):
- PD-CH6-007 (Line 3669): Every knowledge package MUST have a closed schema, content digest,
  provenance, license reference, declared capability set, and a signature binding.
- PD-CH6-008 (Line 3693): Knowledge resolution MUST apply deterministic precedence and conflicts
  MUST NOT permit lower-tier content to remove mandatory checks.
- PD-CH6-009 (Line 3717): Pack lifecycle labels MUST be projections of qualification/revocation
  evidence, never an independent state machine.
- PD-CH6-010 (Line 3741): Unknown checks, weakened floors, invalid signatures, or unsupported
  compatibility MUST quarantine the package or return MISSING.
- PD-CH6-011 (Line 3765): Unclear license/provenance MUST remain UNVERIFIED and block promotion;
  a public URL alone is not permission.
- PD-CH6-012 (Line 3789): Every in-flight StepPack MUST pin selected content/compiler digests;
  invalidation is owned by PD-CH2-055.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary across Block 6 Lane A evaluation."""

REQUIRED_PACKAGE_METADATA_FIELDS: FrozenSet[str] = frozenset({
    "closed_schema",
    "content_digest",
    "provenance",
    "license_reference",
    "declared_capability_set",
    "signature_binding",
})

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "REQUIRED_PACKAGE_METADATA_FIELDS",
    "evaluate_pd_ch6_007_package_metadata",
    "evaluate_pd_ch6_008_precedence_and_conflicts",
    "evaluate_pd_ch6_009_lifecycle_projection",
    "evaluate_pd_ch6_010_quarantine_conditions",
    "evaluate_pd_ch6_011_license_provenance_verification",
    "evaluate_pd_ch6_012_steppack_digest_pinning",
    "evaluate_b6_a_gate",
]


def evaluate_pd_ch6_007_package_metadata(
    package_metadata: Optional[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH6-007 (Line 3669): Closed schema, content digest, provenance, license, capabilities, signature."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-007",
            detail="Caller lacks qualified evaluator authority",
        )

    if not package_metadata:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-007",
            detail="Knowledge package metadata missing entirely",
        )

    for req_field in REQUIRED_PACKAGE_METADATA_FIELDS:
        val = package_metadata.get(req_field)
        if val is None or (isinstance(val, (str, list, dict, set)) and len(val) == 0):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH6-007",
                detail=f"Knowledge package missing required metadata field: {req_field}",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH6-007",
        detail="Knowledge package satisfies closed schema, digests, provenance, and signature bindings",
    )


def evaluate_pd_ch6_008_precedence_and_conflicts(
    precedence_deterministic: bool,
    lower_tier_removes_mandatory: bool = False,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH6-008 (Line 3693): Deterministic precedence and conflict resolution without removing mandatory checks."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-008",
            detail="Caller lacks qualified evaluator authority",
        )

    if not precedence_deterministic or lower_tier_removes_mandatory:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-008",
            detail="Knowledge resolution failed deterministic precedence or lower tier removes mandatory check",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH6-008",
        detail="Knowledge resolution applies deterministic precedence with mandatory check preservation",
    )


def evaluate_pd_ch6_009_lifecycle_projection(
    is_evidence_projection: bool,
    *,
    independent_state_machine: bool = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH6-009 (Line 3717): Pack lifecycle labels MUST be projections of qualification/revocation evidence."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-009",
            detail="Caller lacks qualified evaluator authority",
        )

    if independent_state_machine or not is_evidence_projection:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-009",
            detail="Lifecycle label is an independent state machine or not projected from qualification/revocation evidence",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH6-009",
        detail="Lifecycle label is an authoritative projection of qualification and revocation evidence",
    )


def evaluate_pd_ch6_010_quarantine_conditions(
    unknown_checks: bool = False,
    weakened_floors: bool = False,
    invalid_signature: bool = False,
    unsupported_compatibility: bool = False,
    *,
    quarantined: bool = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH6-010 (Line 3741): Unknown checks, weakened floors, invalid signatures, unsupported compatibility."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-010",
            detail="Caller lacks qualified evaluator authority",
        )

    flawed = unknown_checks or weakened_floors or invalid_signature or unsupported_compatibility
    if flawed:
        if not quarantined:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH6-010",
                detail="Package contains unknown checks, weakened floors, invalid signature or unsupported compatibility without quarantine",
            )
        # If quarantined, the quarantine gate returns MISSING to prevent execution/promotion
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-010",
            detail="Package safely quarantined due to integrity/compatibility flaws",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH6-010",
        detail="Package verified clean of unknown checks, weakened floors, signature, and compatibility flaws",
    )


def evaluate_pd_ch6_011_license_provenance_verification(
    license_verified: bool,
    provenance_verified: bool,
    *,
    public_url_only: bool = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH6-011 (Line 3765): Unclear license/provenance MUST remain UNVERIFIED and block promotion."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-011",
            detail="Caller lacks qualified evaluator authority",
        )

    if public_url_only or not license_verified or not provenance_verified:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-011",
            detail="Unclear license/provenance or public URL only without explicit permission",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH6-011",
        detail="License reference and provenance verified with explicit permissions",
    )


def evaluate_pd_ch6_012_steppack_digest_pinning(
    in_flight: bool,
    content_digest_pinned: bool,
    compiler_digest_pinned: bool,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH6-012 (Line 3789): Every in-flight StepPack MUST pin selected content/compiler digests."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-012",
            detail="Caller lacks qualified evaluator authority",
        )

    if in_flight:
        if not content_digest_pinned or not compiler_digest_pinned:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH6-012",
                detail="In-flight StepPack missing content digest or compiler digest pin",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH6-012",
        detail="StepPack content and compiler digests pinned or pack not in-flight",
    )


def evaluate_b6_a_gate(
    payload: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Aggregate gate evaluator for Block 6 Lane A (PD-CH6-007..012)."""
    return {
        "PD-CH6-007": evaluate_pd_ch6_007_package_metadata(
            payload.get("package_metadata"),
            authority=authority,
        ),
        "PD-CH6-008": evaluate_pd_ch6_008_precedence_and_conflicts(
            payload.get("precedence_deterministic", False),
            lower_tier_removes_mandatory=payload.get("lower_tier_removes_mandatory", False),
            authority=authority,
        ),
        "PD-CH6-009": evaluate_pd_ch6_009_lifecycle_projection(
            payload.get("is_evidence_projection", False),
            independent_state_machine=payload.get("independent_state_machine", False),
            authority=authority,
        ),
        "PD-CH6-010": evaluate_pd_ch6_010_quarantine_conditions(
            unknown_checks=payload.get("unknown_checks", False),
            weakened_floors=payload.get("weakened_floors", False),
            invalid_signature=payload.get("invalid_signature", False),
            unsupported_compatibility=payload.get("unsupported_compatibility", False),
            quarantined=payload.get("quarantined", False),
            authority=authority,
        ),
        "PD-CH6-011": evaluate_pd_ch6_011_license_provenance_verification(
            payload.get("license_verified", False),
            payload.get("provenance_verified", False),
            public_url_only=payload.get("public_url_only", False),
            authority=authority,
        ),
        "PD-CH6-012": evaluate_pd_ch6_012_steppack_digest_pinning(
            payload.get("in_flight", False),
            payload.get("content_digest_pinned", False),
            payload.get("compiler_digest_pinned", False),
            authority=authority,
        ),
    }
