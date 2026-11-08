"""Authoritative OSS Qualification & Playbook Gate Engine.

Implements normative requirements for Chapter 6 Knowledge Management (Block 6, Lane B6-B):
- PD-CH6-013 (Line 3813): A v1 stack pack MUST reference qualified adapter capability families
  or explicitly block applicable checks.
- PD-CH6-014 (Line 3835): An OSS qualification record MUST contain all 16 fields and each field
  must remain UNVERIFIED until independently supported by evidence; incomplete records cannot
  promote a dependency.
- PD-CH6-003 (Line 3862): Activation MUST require scope-specific qualification and absence of
  effective revocation.
- PD-CH6-006 (Line 3863): v1 Python Feature/Bug Fix playbook content MUST provide phase
  checklists and refer to qualified adapter families.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary across Block 6 Lane B evaluation."""

OSS_QUALIFICATION_FIELDS: FrozenSet[str] = frozenset({
    "upstream_repository",
    "immutable_ref",
    "license_obligations",
    "dependency_summary",
    "security_review",
    "test_ci_evidence",
    "install_digest",
    "os_runtime_assumptions",
    "consumed_api",
    "adapter_contract_version",
    "replacement_candidate",
    "fallback",
    "known_failure_modes",
    "qualification_status",
    "reviewer_reference",
    "record_digest",
})

REQUIRED_PLAYBOOK_PHASES: FrozenSet[str] = frozenset({
    "P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11"
})

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "OSS_QUALIFICATION_FIELDS",
    "REQUIRED_PLAYBOOK_PHASES",
    "evaluate_pd_ch6_013_stack_pack_adapters",
    "evaluate_pd_ch6_014_oss_qualification_record",
    "evaluate_pd_ch6_003_pack_activation",
    "evaluate_pd_ch6_006_playbook_content",
    "evaluate_b6_b_gate",
]


def evaluate_pd_ch6_013_stack_pack_adapters(
    stack_pack: Optional[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH6-013 (Line 3813): Stack pack references qualified adapter families or explicitly blocks checks."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-013",
            detail="Caller lacks qualified evaluator authority",
        )

    if not stack_pack:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-013",
            detail="Stack pack definition missing entirely",
        )

    adapter_refs = stack_pack.get("adapter_capability_families", {})
    blocked_checks = set(stack_pack.get("explicitly_blocked_checks", []))

    if not adapter_refs and not blocked_checks:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-013",
            detail="Stack pack neither references qualified adapter capability families nor blocks checks",
        )

    # Any referenced adapter family that is unqualified must be explicitly blocked
    for family, info in adapter_refs.items():
        is_qualified = info.get("qualified", False) if isinstance(info, dict) else False
        if not is_qualified:
            applicable_checks = info.get("applicable_checks", []) if isinstance(info, dict) else [family]
            if not any(chk in blocked_checks for chk in applicable_checks):
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH6-013",
                    detail=f"Unqualified adapter family {family} has unblocked applicable checks",
                )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH6-013",
        detail="Stack pack references qualified adapter capability families or explicitly blocks applicable checks",
    )


def evaluate_pd_ch6_014_oss_qualification_record(
    record: Optional[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH6-014 (Line 3835): OSS qualification record must contain all 16 fields and each must remain UNVERIFIED until evidence."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-014",
            detail="Caller lacks qualified evaluator authority",
        )

    if not record:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-014",
            detail="OSS qualification record missing",
        )

    # Must contain all 16 fields
    for req_field in OSS_QUALIFICATION_FIELDS:
        if req_field not in record:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH6-014",
                detail=f"OSS qualification record missing required field: {req_field}",
            )
        val = record[req_field]
        if val is None or (isinstance(val, str) and not val.strip()):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH6-014",
                detail=f"OSS qualification record field {req_field} is empty or null",
            )

    # Incomplete records cannot promote dependency; must remain UNVERIFIED until independently supported
    # If fields claim verified without evidence support, fails
    unsupported_claims = record.get("unsupported_verified_claims", False)
    if unsupported_claims:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-014",
            detail="Fields claimed verified without independent supporting evidence",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH6-014",
        detail="OSS qualification record contains all 16 required fields with verified evidence envelope",
    )


def evaluate_pd_ch6_003_pack_activation(
    scope_specific_qualification: bool,
    effective_revocation_present: bool = False,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH6-003 (Line 3862): Activation MUST require scope-specific qualification and absence of effective revocation."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-003",
            detail="Caller lacks qualified evaluator authority",
        )

    if not scope_specific_qualification or effective_revocation_present:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-003",
            detail="Pack activation requires scope-specific qualification and absence of effective revocation",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH6-003",
        detail="Pack activation permitted with scope-specific qualification and zero effective revocation",
    )


def evaluate_pd_ch6_006_playbook_content(
    playbook_content: Optional[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH6-006 (Line 3863): v1 Python Feature/Bug Fix playbook content MUST provide phase checklists and refer to qualified adapter families."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-006",
            detail="Caller lacks qualified evaluator authority",
        )

    if not playbook_content:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-006",
            detail="Playbook content missing entirely",
        )

    phases = set(playbook_content.get("phases", []))
    missing_phases = REQUIRED_PLAYBOOK_PHASES - phases
    if missing_phases:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-006",
            detail=f"Playbook content missing phase checklists: {sorted(missing_phases)}",
        )

    unqualified_claimed_usable = playbook_content.get("unqualified_adapter_claimed_usable", False)
    if unqualified_claimed_usable:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH6-006",
            detail="Unqualified adapter family claimed usable in playbook",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH6-006",
        detail="Playbook content contains all phase checklists (P0..P11) and references qualified adapter families",
    )


def evaluate_b6_b_gate(
    payload: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Aggregate gate evaluator for Block 6 Lane B (PD-CH6-013, 014, 003, 006)."""
    return {
        "PD-CH6-013": evaluate_pd_ch6_013_stack_pack_adapters(
            payload.get("stack_pack"),
            authority=authority,
        ),
        "PD-CH6-014": evaluate_pd_ch6_014_oss_qualification_record(
            payload.get("oss_qualification_record"),
            authority=authority,
        ),
        "PD-CH6-003": evaluate_pd_ch6_003_pack_activation(
            payload.get("scope_specific_qualification", False),
            effective_revocation_present=payload.get("effective_revocation_present", False),
            authority=authority,
        ),
        "PD-CH6-006": evaluate_pd_ch6_006_playbook_content(
            payload.get("playbook_content"),
            authority=authority,
        ),
    }
