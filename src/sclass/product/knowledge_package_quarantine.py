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

    if not package_metadata or not isinstance(package_metadata, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-007",
            detail="Knowledge package metadata missing entirely or invalid type",
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
    precedence_deterministic: Optional[bool] = None,
    lower_tier_removes_mandatory: Optional[bool] = False,
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

    if precedence_deterministic is False or lower_tier_removes_mandatory is True:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-008",
            detail="Knowledge resolution failed deterministic precedence or lower tier removes mandatory check",
        )

    if not (
        type(precedence_deterministic) is bool and precedence_deterministic is True
        and (lower_tier_removes_mandatory is None or (type(lower_tier_removes_mandatory) is bool and lower_tier_removes_mandatory is False))
    ):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-008",
            detail="Precedence or mandatory check evidence omitted or invalid type",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH6-008",
        detail="Knowledge resolution applies deterministic precedence with mandatory check preservation",
    )


def evaluate_pd_ch6_009_lifecycle_projection(
    is_evidence_projection: Optional[bool] = None,
    *,
    independent_state_machine: Optional[bool] = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH6-009 (Line 3717): Pack lifecycle labels MUST be projections of qualification/revocation evidence."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-009",
            detail="Caller lacks qualified evaluator authority",
        )

    if is_evidence_projection is False or independent_state_machine is True:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-009",
            detail="Lifecycle label operating as an independent state machine or not projected from evidence",
        )

    if not (
        type(is_evidence_projection) is bool and is_evidence_projection is True
        and (independent_state_machine is None or (type(independent_state_machine) is bool and independent_state_machine is False))
    ):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-009",
            detail="Lifecycle projection evidence omitted or invalid type",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH6-009",
        detail="Pack lifecycle labels projected deterministically from qualification and revocation evidence",
    )


def evaluate_pd_ch6_010_quarantine_conditions(
    unknown_checks: Optional[bool] = None,
    weakened_floors: Optional[bool] = None,
    invalid_signature: Optional[bool] = None,
    unsupported_compatibility: Optional[bool] = None,
    *,
    quarantined: Optional[bool] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH6-010 (Line 3741): Unknown checks, weakened floors, invalid signatures, or unsupported compatibility."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-010",
            detail="Caller lacks qualified evaluator authority",
        )

    # Any explicit violation or quarantine state fails closed immediately
    if (
        unknown_checks is True
        or weakened_floors is True
        or invalid_signature is True
        or unsupported_compatibility is True
    ):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-010",
            detail="Package contains unknown checks, weakened floors, invalid signature or unsupported compatibility without quarantine",
        )

    if quarantined is True:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-010",
            detail="Package safely quarantined due to integrity/compatibility flaws",
        )

    # For SATISFIED, all four conditions must be affirmatively verified clean (exact bool False)
    if not (
        type(unknown_checks) is bool and unknown_checks is False
        and type(weakened_floors) is bool and weakened_floors is False
        and type(invalid_signature) is bool and invalid_signature is False
        and type(unsupported_compatibility) is bool and unsupported_compatibility is False
        and (quarantined is None or (type(quarantined) is bool and quarantined is False))
    ):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-010",
            detail="Quarantine conditions evidence omitted, incomplete, or invalid type",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH6-010",
        detail="Package verified clean of unknown checks, weakened floors, signature, and compatibility flaws",
    )


def evaluate_pd_ch6_011_license_provenance_verification(
    license_verified: Optional[bool] = None,
    provenance_verified: Optional[bool] = None,
    *,
    public_url_only: Optional[bool] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH6-011 (Line 3765): Unclear license/provenance MUST remain UNVERIFIED and block promotion."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-011",
            detail="Caller lacks qualified evaluator authority",
        )

    if public_url_only is True or license_verified is False or provenance_verified is False:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-011",
            detail="Unclear license/provenance or public URL only without explicit permission",
        )

    if not (
        type(license_verified) is bool and license_verified is True
        and type(provenance_verified) is bool and provenance_verified is True
        and (public_url_only is None or (type(public_url_only) is bool and public_url_only is False))
    ):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-011",
            detail="License reference and provenance evidence omitted or invalid type",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH6-011",
        detail="License reference and provenance verified with explicit permissions",
    )


def evaluate_pd_ch6_012_steppack_digest_pinning(
    in_flight: Optional[bool] = None,
    content_digest_pinned: Optional[bool] = None,
    compiler_digest_pinned: Optional[bool] = None,
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

    if in_flight is True:
        if content_digest_pinned is False or compiler_digest_pinned is False:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH6-012",
                detail="In-flight StepPack missing content digest or compiler digest pin",
            )
        if not (
            type(content_digest_pinned) is bool and content_digest_pinned is True
            and type(compiler_digest_pinned) is bool and compiler_digest_pinned is True
        ):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH6-012",
                detail="In-flight StepPack digest pin evidence omitted or invalid type",
            )
        return GateOutput(
            state=GateState.SATISFIED,
            must_id="PD-CH6-012",
            detail="StepPack content and compiler digests pinned",
        )

    if type(in_flight) is bool and in_flight is False:
        return GateOutput(
            state=GateState.SATISFIED,
            must_id="PD-CH6-012",
            detail="StepPack not in-flight",
        )

    return GateOutput(
        state=GateState.MISSING,
        must_id="PD-CH6-012",
        detail="In-flight parameter omitted or invalid type",
    )


def evaluate_b6_a_gate(
    payload: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Aggregate gate evaluator for Block 6 Lane A (PD-CH6-007..012)."""
    if not isinstance(payload, Mapping):
        payload = {}

    res: Dict[str, GateOutput] = {}

    if "package_metadata" in payload:
        res["PD-CH6-007"] = evaluate_pd_ch6_007_package_metadata(
            payload.get("package_metadata"),
            authority=authority,
        )
    else:
        res["PD-CH6-007"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-007",
            detail="Payload missing required key: package_metadata",
        )

    if "precedence_deterministic" in payload or "lower_tier_removes_mandatory" in payload:
        res["PD-CH6-008"] = evaluate_pd_ch6_008_precedence_and_conflicts(
            payload.get("precedence_deterministic"),
            lower_tier_removes_mandatory=payload.get("lower_tier_removes_mandatory"),
            authority=authority,
        )
    else:
        res["PD-CH6-008"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-008",
            detail="Payload missing required key: precedence_deterministic",
        )

    if "is_evidence_projection" in payload or "independent_state_machine" in payload:
        res["PD-CH6-009"] = evaluate_pd_ch6_009_lifecycle_projection(
            payload.get("is_evidence_projection"),
            independent_state_machine=payload.get("independent_state_machine"),
            authority=authority,
        )
    else:
        res["PD-CH6-009"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-009",
            detail="Payload missing required key: is_evidence_projection",
        )

    if (
        "unknown_checks" in payload
        or "weakened_floors" in payload
        or "invalid_signature" in payload
        or "unsupported_compatibility" in payload
        or "quarantined" in payload
    ):
        res["PD-CH6-010"] = evaluate_pd_ch6_010_quarantine_conditions(
            unknown_checks=payload.get("unknown_checks"),
            weakened_floors=payload.get("weakened_floors"),
            invalid_signature=payload.get("invalid_signature"),
            unsupported_compatibility=payload.get("unsupported_compatibility"),
            quarantined=payload.get("quarantined"),
            authority=authority,
        )
    else:
        res["PD-CH6-010"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-010",
            detail="Payload missing required quarantine condition keys",
        )

    if "license_verified" in payload or "provenance_verified" in payload or "public_url_only" in payload:
        res["PD-CH6-011"] = evaluate_pd_ch6_011_license_provenance_verification(
            payload.get("license_verified"),
            payload.get("provenance_verified"),
            public_url_only=payload.get("public_url_only"),
            authority=authority,
        )
    else:
        res["PD-CH6-011"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-011",
            detail="Payload missing required license/provenance keys",
        )

    if "in_flight" in payload or "content_digest_pinned" in payload or "compiler_digest_pinned" in payload:
        res["PD-CH6-012"] = evaluate_pd_ch6_012_steppack_digest_pinning(
            payload.get("in_flight"),
            payload.get("content_digest_pinned"),
            payload.get("compiler_digest_pinned"),
            authority=authority,
        )
    else:
        res["PD-CH6-012"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-012",
            detail="Payload missing required StepPack digest pinning keys",
        )

    return res
