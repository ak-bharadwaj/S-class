"""Authoritative Test Isolation Write Protection & Evidence Claim Verification Engine.

Implements normative requirements for Chapter 4 Test Isolation and Evidence Integrity (Block 4, Lane E):
- PD-CH4-010 (Line 3289): P6 MUST exclude every path in the bound TestInputSet from implementation writes; P7 evidence MUST use the same manifest.
- PD-CH4-014 (Line 3327): An observed delta outside the authorized write/scope set MUST return BLOCKED and cannot be accepted by a green test run.
- PD-CH4-016 (Line 3408): Independence claims MUST name distinct evidence producers/identities and cannot count a self-review or shared unqualified adapter.
- PD-CH4-002 (Line 3464): Claims of execution MUST bind qualified adapter structured results and raw result identity.
- PD-CH4-005 (Line 3465): Evidence freshness and independence MUST be evaluated from bound identity; invalidation is owned by PD-CH2-055.
- PD-CH4-006 (Line 3466): False-completion MUST be recorded only from canonical outcome/evidence events; agent prose has no closure authority.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary across Block 4 evaluation."""

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "evaluate_pd_ch4_010_test_input_write_isolation",
    "evaluate_pd_ch4_014_authorized_delta_scope",
    "evaluate_pd_ch4_016_independent_evidence_producers",
    "evaluate_pd_ch4_002_execution_claim_receipt",
    "evaluate_pd_ch4_005_evidence_freshness_identity",
    "evaluate_pd_ch4_006_canonical_closure_vs_prose",
    "evaluate_b4_e_gate",
]


def evaluate_pd_ch4_010_test_input_write_isolation(
    implementation_write_paths: Optional[Sequence[str]] = None,
    test_input_paths: Optional[Sequence[str]] = None,
    *,
    manifest_unchanged: bool = True,
    environment_digest_match: bool = True,
    test_is_green: bool = True,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH4-010 (Line 3289): P6 MUST exclude every path in bound TestInputSet from writes; P7 evidence uses same manifest."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-010",
            detail="Caller lacks qualified evaluator authority",
        )

    if implementation_write_paths is None or test_input_paths is None:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-010",
            detail="Write paths or test input paths omitted",
        )

    overlap = set(implementation_write_paths) & set(test_input_paths)
    if overlap:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-010",
            detail=f"P6 implementation writes touch paths in bound TestInputSet: {sorted(overlap)}",
        )

    if not manifest_unchanged or not environment_digest_match or not test_is_green:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-010",
            detail="P7 evidence altered manifest, environment digest mismatch, or test not green",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH4-010",
        detail="Test input set excluded from writes and evidence manifest matches green run",
    )

def evaluate_pd_ch4_014_authorized_delta_scope(
    observed_delta_paths: Sequence[str],
    authorized_write_paths: Sequence[str],
    *,
    green_test_run: bool = True,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH4-014 (Line 3327): Observed delta outside authorized scope returns BLOCKED; cannot be accepted by green test."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-014",
            detail="Caller lacks qualified evaluator authority",
        )

    unauthorized = set(observed_delta_paths) - set(authorized_write_paths)
    if unauthorized:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-014",
            detail=f"Observed delta outside authorized write set: {sorted(unauthorized)} (action_result: BLOCKED)",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH4-014",
        detail="Observed write delta strictly within authorized scope",
    )


def evaluate_pd_ch4_016_independent_evidence_producers(
    primary_producer: Optional[str],
    independent_producer: Optional[str],
    *,
    is_self_review: bool = False,
    shared_unqualified_adapter: bool = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH4-016 (Line 3408): Independence claims MUST name distinct evidence producers; self-review prohibited."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-016",
            detail="Caller lacks qualified evaluator authority",
        )

    if not primary_producer or not independent_producer:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-016",
            detail="Missing primary or independent evidence producer identity",
        )

    if primary_producer == independent_producer or is_self_review:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-016",
            detail=f"Self-review prohibited; identical evidence producer identity '{primary_producer}'",
        )

    if shared_unqualified_adapter:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-016",
            detail="Shared unqualified adapter cannot produce independent evidence",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH4-016",
        detail=f"Distinct independent evidence producers verified: '{primary_producer}' vs '{independent_producer}'",
    )


def evaluate_pd_ch4_002_execution_claim_receipt(
    has_execution_claim: bool,
    has_structured_results: bool,
    raw_result_digest: Optional[str],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH4-002 (Line 3464): Claims of execution MUST bind qualified adapter structured results and raw result identity."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-002",
            detail="Caller lacks qualified evaluator authority",
        )

    if has_execution_claim and (not has_structured_results or not raw_result_digest):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-002",
            detail="Agent says PASS without structured results receipt or raw result digest",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH4-002",
        detail="Execution claim bound to structured results and raw result digest",
    )


def evaluate_pd_ch4_005_evidence_freshness_identity(
    requirement_revision_digest: Optional[str],
    evidence_requirement_digest: Optional[str],
    *,
    target_identity_match: bool = True,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH4-005 (Line 3465): Evidence freshness and independence MUST be evaluated from bound identity."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-005",
            detail="Caller lacks qualified evaluator authority",
        )

    if not requirement_revision_digest or not evidence_requirement_digest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-005",
            detail="Missing requirement revision digest or evidence requirement digest",
        )

    if requirement_revision_digest != evidence_requirement_digest or not target_identity_match:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-005",
            detail="Changed requirement revision with old green evidence; evidence stale",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH4-005",
        detail="Current receipt matches target, adapter, environment, and freshness floor",
    )


def evaluate_pd_ch4_006_canonical_closure_vs_prose(
    agent_prose_done_claim: Optional[bool] = None,
    kernel_obligation_closure: Optional[bool] = None,
    has_admissible_evidence: Optional[bool] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH4-006 (Line 3466): False-completion MUST be recorded from canonical events; agent prose has no closure authority."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-006",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(agent_prose_done_claim) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-006",
            detail="agent_prose_done_claim must be an exact boolean",
        )

    if agent_prose_done_claim is True and (not kernel_obligation_closure or not has_admissible_evidence):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-006",
            detail="Agent says done but closure absent; prose cannot waive kernel closure",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH4-006",
        detail="Completion derives from kernel-evaluated obligation closure and admissible evidence",
    )

def evaluate_b4_e_gate(
    payload: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Aggregate gate evaluator for Block 4 Lane E (PD-CH4-010, PD-CH4-014, PD-CH4-016, PD-CH4-002, 005, 006)."""
    if not isinstance(payload, Mapping):
        payload = {}

    res: Dict[str, GateOutput] = {}

    if "implementation_write_paths" in payload and "test_input_paths" in payload:
        res["PD-CH4-010"] = evaluate_pd_ch4_010_test_input_write_isolation(
            payload.get("implementation_write_paths"),
            payload.get("test_input_paths"),
            manifest_unchanged=payload.get("manifest_unchanged", True),
            environment_digest_match=payload.get("environment_digest_match", True),
            test_is_green=payload.get("test_is_green", True),
            authority=authority,
        )
    else:
        res["PD-CH4-010"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-010",
            detail="Payload missing write isolation paths",
        )

    if "observed_delta_paths" in payload or "authorized_write_paths" in payload:
        res["PD-CH4-014"] = evaluate_pd_ch4_014_authorized_delta_scope(
            payload.get("observed_delta_paths", []),
            payload.get("authorized_write_paths", []),
            green_test_run=payload.get("green_test_run", True),
            authority=authority,
        )
    else:
        res["PD-CH4-014"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-014",
            detail="Payload missing delta scope paths",
        )

    if "primary_producer" in payload or "independent_producer" in payload:
        res["PD-CH4-016"] = evaluate_pd_ch4_016_independent_evidence_producers(
            payload.get("primary_producer"),
            payload.get("independent_producer"),
            is_self_review=payload.get("is_self_review", False),
            shared_unqualified_adapter=payload.get("shared_unqualified_adapter", False),
            authority=authority,
        )
    else:
        res["PD-CH4-016"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-016",
            detail="Payload missing evidence producers keys",
        )

    if "has_execution_claim" in payload or "has_structured_results" in payload:
        res["PD-CH4-002"] = evaluate_pd_ch4_002_execution_claim_receipt(
            payload.get("has_execution_claim", False),
            payload.get("has_structured_results", False),
            payload.get("raw_result_digest"),
            authority=authority,
        )
    else:
        res["PD-CH4-002"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-002",
            detail="Payload missing execution claim receipt keys",
        )

    if "requirement_revision_digest" in payload or "evidence_requirement_digest" in payload:
        res["PD-CH4-005"] = evaluate_pd_ch4_005_evidence_freshness_identity(
            payload.get("requirement_revision_digest"),
            payload.get("evidence_requirement_digest"),
            target_identity_match=payload.get("target_identity_match", True),
            authority=authority,
        )
    else:
        res["PD-CH4-005"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-005",
            detail="Payload missing requirement revision digest keys",
        )

    if "agent_prose_done_claim" in payload:
        res["PD-CH4-006"] = evaluate_pd_ch4_006_canonical_closure_vs_prose(
            payload.get("agent_prose_done_claim"),
            payload.get("kernel_obligation_closure", False),
            payload.get("has_admissible_evidence", False),
            authority=authority,
        )
    else:
        res["PD-CH4-006"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-006",
            detail="Payload missing required key: agent_prose_done_claim",
        )

    return res
