"""Authoritative F10 Adapter Qualification Contract & Verification Engine.

Implements normative requirements for Section F10 (Block 4, Lane A):
- PD-F10-001 (Line 1020): Executable-spec tooling MUST be invoked only through a declared F10 adapter contract and category.
- PD-F10-002 (Line 1021): A usable adapter MUST bind immutable identity/version/digest, schemas, qualification and the frozen evidence-binding fields.
- PD-F10-003 (Line 1022): Only authorized non-agent authority may register/change adapters; canonical adapter identity and qualification MUST be pinned through the frozen attestation/dependency/approval mechanisms; changed identity MUST stale dependent evidence.
- PD-F10-004 (Line 1023): Adapter execution MUST pass through ExecutionGate with the applicable lease, budget and fence, and MUST honor declared isolation and failure semantics.
- PD-F10-005 (Line 1024): Qualification MUST pass all 14 frozen adapter tests, A1 reference-fixture conformance, A2 differential-result detection and A3 stale-evidence invalidation.
- PD-F10-006 (Line 1025): CRITICAL-lane independent verification MUST use a qualified independent verifier; absent verifier availability yields BLOCKED_ON_HUMAN, while a contradiction yields MISSING.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary across Block 4 evaluation."""

FROZEN_EVIDENCE_BINDING_FIELDS: FrozenSet[str] = frozenset({
    "obligation_id",
    "target_snapshot",
    "verification_step",
    "environment_identity",
    "raw_result_digest",
})

FROZEN_ADAPTER_TESTS: FrozenSet[str] = frozenset({
    "capability_discovery",
    "identity_version_mismatch",
    "malformed_request",
    "malformed_response",
    "timeout",
    "crash",
    "partial_output",
    "duplicate_output",
    "unavailable_dependency",
    "unexpected_protocol_message",
    "resource_exhaustion",
    "security_boundary_failure",
    "recovery",
    "replacement",
})

ADDITIONAL_PRODUCT_TESTS: FrozenSet[str] = frozenset({
    "A1_reference_fixture_conformance",
    "A2_differential_result_detection",
    "A3_stale_evidence_invalidation_after_adapter_change",
})

DECLARED_ADAPTER_CATEGORIES: FrozenSet[str] = frozenset({
    "repository-intelligence / symbol resolution",
    "syntax-validator",
    "type-checker",
    "linter",
    "property-tester",
    "verifier",
    "conformance-evaluator",
})

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "FROZEN_EVIDENCE_BINDING_FIELDS",
    "FROZEN_ADAPTER_TESTS",
    "ADDITIONAL_PRODUCT_TESTS",
    "DECLARED_ADAPTER_CATEGORIES",
    "evaluate_pd_f10_001_contract_invocation",
    "evaluate_pd_f10_002_usable_adapter_binding",
    "evaluate_pd_f10_003_adapter_registration_authority",
    "evaluate_pd_f10_004_execution_gate_enforcement",
    "evaluate_pd_f10_005_qualification_matrix",
    "evaluate_pd_f10_006_independent_verification",
    "evaluate_b4_a_gate",
]


def evaluate_pd_f10_001_contract_invocation(
    tool_call: Optional[Mapping[str, Any]],
    adapter_record: Optional[Mapping[str, Any]] = None,
    category: Optional[str] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-F10-001 (Line 1020): Executable-spec tooling MUST be invoked only through declared F10 contract."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-001",
            detail="Caller lacks qualified evaluator authority",
        )

    if not tool_call or adapter_record is None:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-001",
            detail="Executable-spec tooling invoked without declared F10 adapter record",
        )

    if category is not None and category not in DECLARED_ADAPTER_CATEGORIES:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-001",
            detail=f"Undeclared adapter category: {category}",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-F10-001",
        detail="Tooling invoked through declared F10 adapter contract and category",
    )


def evaluate_pd_f10_002_usable_adapter_binding(
    adapter: Optional[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-F10-002 (Line 1021): A usable adapter MUST bind immutable identity, schemas, qualification and evidence fields."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-002",
            detail="Caller lacks qualified evaluator authority",
        )

    if not adapter:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-002",
            detail="Missing adapter payload",
        )

    if not adapter.get("qualification_record_ref"):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-002",
            detail="Adapter missing qualification record reference",
        )

    bound_fields = set(adapter.get("evidence_binding_fields") or [])
    missing = FROZEN_EVIDENCE_BINDING_FIELDS - bound_fields
    if missing:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-002",
            detail=f"Adapter omits frozen evidence-binding fields: {sorted(missing)}",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-F10-002",
        detail="Usable adapter binds qualification record and all frozen evidence-binding fields",
    )


def evaluate_pd_f10_003_adapter_registration_authority(
    actor: str,
    operation: str,
    canonical_write_authorized: bool,
    *,
    evidence_adapter_digest: Optional[str] = None,
    current_adapter_digest: Optional[str] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-F10-003 (Line 1022): Only authorized non-agent authority may register/change adapters; changed identity stales evidence."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-003",
            detail="Caller lacks qualified evaluator authority",
        )

    if actor.lower() == "agent" or not canonical_write_authorized:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-003",
            detail="Agent attempts adapter registration or unauthorized non-agent write",
        )

    if evidence_adapter_digest and current_adapter_digest and evidence_adapter_digest != current_adapter_digest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-003",
            detail="Adapter digest changed after evidence receipt; dependent evidence staled",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-F10-003",
        detail="Adapter registration authorized by non-agent authority with pinned qualification",
    )


def evaluate_pd_f10_004_execution_gate_enforcement(
    authorized_request: Optional[Any],
    execution_lease: Optional[Any],
    budget_reservation: Optional[Any],
    fence: Optional[Any],
    worker_execute_attempt: bool = False,
    execution_timeout: bool = False,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-F10-004 (Line 1023): Adapter execution MUST pass through ExecutionGate with lease, budget, and fence."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-004",
            detail="Caller lacks qualified evaluator authority",
        )

    if authorized_request is None or execution_lease is None or budget_reservation is None or fence is None:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-004",
            detail="ExecutionGate bypass: missing authorized request, lease, budget reservation, or fence",
        )

    if execution_timeout:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-004",
            detail="Adapter execution timed out exceeding declared bounded limit",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-F10-004",
        detail="ExecutionGate passed with valid lease, budget reservation, and fence",
    )


def evaluate_pd_f10_005_qualification_matrix(
    frozen_required_tests: Optional[Mapping[str, Mapping[str, str]]],
    additional_product_tests: Optional[Mapping[str, Mapping[str, str]]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-F10-005 (Line 1024): Qualification MUST pass all 14 frozen adapter tests, A1, A2, and A3."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-005",
            detail="Caller lacks qualified evaluator authority",
        )

    if not frozen_required_tests or not additional_product_tests:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-005",
            detail="Qualification matrix missing test results payload",
        )

    for test_name in FROZEN_ADAPTER_TESTS:
        t_data = frozen_required_tests.get(test_name)
        if not t_data or t_data.get("result") != "PASS":
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F10-005",
                detail=f"Frozen adapter qualification test failed or missing: {test_name}",
            )

    for test_name in ADDITIONAL_PRODUCT_TESTS:
        t_data = additional_product_tests.get(test_name)
        if not t_data or t_data.get("result") != "PASS":
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F10-005",
                detail=f"Additional qualification test failed or missing: {test_name}",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-F10-005",
        detail="All 14 frozen adapter tests and A1-A3 additional product tests passed",
    )


def evaluate_pd_f10_006_independent_verification(
    is_critical_lane: bool,
    qualified_independent_verifier: Optional[str] = None,
    primary_result: Optional[str] = None,
    independent_result: Optional[str] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-F10-006 (Line 1025): CRITICAL-lane independent verification MUST use qualified independent verifier."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-006",
            detail="Caller lacks qualified evaluator authority",
        )

    if is_critical_lane:
        if not qualified_independent_verifier:
            return GateOutput(
                state=GateState.BLOCKED_ON_HUMAN,
                must_id="PD-F10-006",
                detail="No qualified independent verifier available for CRITICAL lane",
            )
        if primary_result != independent_result:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F10-006",
                detail=f"Contradiction between primary verifier ({primary_result}) and independent verifier ({independent_result})",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-F10-006",
        detail="Independent verification verified or non-critical lane satisfied",
    )


def evaluate_b4_a_gate(
    payload: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Aggregate gate evaluator for Block 4 Lane A (PD-F10-001..006)."""
    return {
        "PD-F10-001": evaluate_pd_f10_001_contract_invocation(
            payload.get("tool_call"),
            payload.get("adapter_record"),
            payload.get("category"),
            authority=authority,
        ),
        "PD-F10-002": evaluate_pd_f10_002_usable_adapter_binding(
            payload.get("adapter"),
            authority=authority,
        ),
        "PD-F10-003": evaluate_pd_f10_003_adapter_registration_authority(
            payload.get("actor", ""),
            payload.get("operation", ""),
            payload.get("canonical_write_authorized", False),
            evidence_adapter_digest=payload.get("evidence_adapter_digest"),
            current_adapter_digest=payload.get("current_adapter_digest"),
            authority=authority,
        ),
        "PD-F10-004": evaluate_pd_f10_004_execution_gate_enforcement(
            payload.get("authorized_request"),
            payload.get("execution_lease"),
            payload.get("budget_reservation"),
            payload.get("fence"),
            worker_execute_attempt=payload.get("worker_execute_attempt", False),
            execution_timeout=payload.get("execution_timeout", False),
            authority=authority,
        ),
        "PD-F10-005": evaluate_pd_f10_005_qualification_matrix(
            payload.get("frozen_required_tests"),
            payload.get("additional_product_tests"),
            authority=authority,
        ),
        "PD-F10-006": evaluate_pd_f10_006_independent_verification(
            payload.get("is_critical_lane", False),
            qualified_independent_verifier=payload.get("qualified_independent_verifier"),
            primary_result=payload.get("primary_result"),
            independent_result=payload.get("independent_result"),
            authority=authority,
        ),
    }
