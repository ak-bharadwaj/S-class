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

from types import MappingProxyType
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

# Normative six F10 adapter categories from Master F10 L973.
DECLARED_ADAPTER_CATEGORIES: FrozenSet[str] = frozenset({
    "schema validators",
    "contract testers",
    "type checkers",
    "property-test adapters",
    "mutation adapters",
    "repository-intelligence / symbol resolution",
})

UNMAPPED_IN_MASTER = "UNMAPPED_IN_MASTER"

# V3 capability-family labels not among the six Master F10 L973 categories.
# Where the Master text does not state an explicit category mapping, marked UNMAPPED_IN_MASTER.
CAPABILITY_FAMILY_TO_CATEGORY: Mapping[str, str] = MappingProxyType({
    "security-scanner": UNMAPPED_IN_MASTER,
    "test-runner": UNMAPPED_IN_MASTER,
    "verifier": UNMAPPED_IN_MASTER,
    "bounded-predicate-evaluator": UNMAPPED_IN_MASTER,
    "pack-qualification": UNMAPPED_IN_MASTER,
    "conformance-evaluator": UNMAPPED_IN_MASTER,
    "syntax-validator": UNMAPPED_IN_MASTER,
    "linter": UNMAPPED_IN_MASTER,
    "UNSPECIFIED_IN_MASTER": UNMAPPED_IN_MASTER,
})

# Category 7 extension from WI-014 (Master amendment pending owner Item H).
# NOT accepted as an F10 category by F10 evaluators until approved.
EXTENSION_CATEGORIES: FrozenSet[str] = frozenset({
    "security/supply-chain",
})

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "FROZEN_EVIDENCE_BINDING_FIELDS",
    "FROZEN_ADAPTER_TESTS",
    "ADDITIONAL_PRODUCT_TESTS",
    "DECLARED_ADAPTER_CATEGORIES",
    "UNMAPPED_IN_MASTER",
    "CAPABILITY_FAMILY_TO_CATEGORY",
    "EXTENSION_CATEGORIES",
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

    if (
        not isinstance(tool_call, Mapping)
        or not tool_call
        or not isinstance(adapter_record, Mapping)
        or not adapter_record
    ):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-001",
            detail="Executable-spec tooling invoked without declared F10 adapter record",
        )

    if type(category) is not str:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-001",
            detail=f"Undeclared adapter category: category must be a string in DECLARED_ADAPTER_CATEGORIES: {category}",
        )

    if category in EXTENSION_CATEGORIES:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-001",
            detail=f"Extension category '{category}' is not accepted as an F10 category pending Master amendment (Item H)",
        )

    if category not in DECLARED_ADAPTER_CATEGORIES:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-001",
            detail=f"Undeclared adapter category: category must be provided and in DECLARED_ADAPTER_CATEGORIES: {category}",
        )

    if "category" in adapter_record:
        rec_cat = adapter_record.get("category")
        if rec_cat in EXTENSION_CATEGORIES:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F10-001",
                detail=f"Adapter record declares extension category '{rec_cat}', not accepted pending Master amendment (Item H)",
            )
        if type(rec_cat) is not str or rec_cat != category:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F10-001",
                detail=f"Adapter record category '{rec_cat}' does not match declared category '{category}'",
            )

    if "declared_contract" in adapter_record and adapter_record.get("declared_contract") is not True:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-001",
            detail="Adapter record declared_contract must be True",
        )

    if adapter_record.get("self_attested") is True:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-001",
            detail="Self-attested adapter claim rejected; declared F10 contract required",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-F10-001",
        detail="Tooling invoked through declared F10 adapter contract and category",
    )


def evaluate_pd_f10_002_usable_adapter_binding(
    adapter: Optional[Mapping[str, Any]],
    *,
    conformance_report: Optional[Mapping[str, Any]] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-F10-002 (Line 1021): A usable adapter MUST bind immutable identity, schemas, qualification and evidence fields."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-002",
            detail="Caller lacks qualified evaluator authority",
        )

    if not isinstance(adapter, Mapping) or not adapter:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-002",
            detail="Missing adapter payload",
        )

    if adapter.get("self_attested") is True:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-002",
            detail="Self-attested adapter cannot satisfy usable adapter binding",
        )

    qref = adapter.get("qualification_record_ref")
    if type(qref) is not str or not qref.strip():
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-002",
            detail="Adapter missing qualification record reference",
        )

    raw_fields = adapter.get("evidence_binding_fields")
    if not isinstance(raw_fields, (list, tuple, set, frozenset)):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-002",
            detail="Adapter evidence_binding_fields must be a collection",
        )
    bound_fields = set(raw_fields)
    missing = FROZEN_EVIDENCE_BINDING_FIELDS - bound_fields
    if missing:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-002",
            detail=f"Adapter omits frozen evidence-binding fields: {sorted(missing)}",
        )

    ident = adapter.get("adapter_digest") or adapter.get("tool_identity")
    if type(ident) is not str or not ident.strip() or ident.strip() == "0" * 64:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-002",
            detail="Adapter missing valid immutable tool_identity or adapter_digest",
        )

    if "schemas" in adapter:
        schemas = adapter.get("schemas")
        if not isinstance(schemas, Mapping) or not schemas.get("input_schema") or not schemas.get("output_schema"):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F10-002",
                detail="Adapter schemas binding incomplete",
            )

    if conformance_report is not None:
        if not isinstance(conformance_report, Mapping) or conformance_report.get("verdict") != "QUALIFIED":
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F10-002",
                detail="Bound conformance_report is missing or UNQUALIFIED",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-F10-002",
        detail="Usable adapter binds qualification record and all frozen evidence-binding fields",
    )


def evaluate_pd_f10_003_adapter_registration_authority(
    actor: str,
    operation: str,
    canonical_write_authorized: Optional[bool] = None,
    *,
    approval_set: Optional[Any] = None,
    approval_context: Optional[Mapping[str, Any]] = None,
    evidence_adapter_digest: Optional[str] = None,
    current_adapter_digest: Optional[str] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-F10-003 (Line 1022): Only authorized non-agent authority via ApprovalSet/ApprovalRecord may register/change adapters; changed identity stales evidence."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-003",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(actor) is not str or not actor.strip() or type(operation) is not str or not operation.strip():
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-003",
            detail="Arguments actor and operation must be non-empty strings",
        )

    if actor.strip().lower().startswith("agent"):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-003",
            detail="Agent attempts adapter registration or unauthorized non-agent write",
        )

    if canonical_write_authorized is not None and type(canonical_write_authorized) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-003",
            detail="canonical_write_authorized must be exact bool when provided",
        )

    if canonical_write_authorized is False:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-003",
            detail="Unauthorized write rejected",
        )

    if evidence_adapter_digest and current_adapter_digest and evidence_adapter_digest != current_adapter_digest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-003",
            detail="Adapter digest changed after evidence receipt; dependent evidence staled",
        )

    if approval_set is None:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-003",
            detail="ApprovalSet/ApprovalRecord authorization required; caller boolean alone is insufficient",
        )

    from sclass.qualification.f10_validation import verify_non_agent_approval_set

    ok_apr, msg_apr = verify_non_agent_approval_set(approval_set, approval_context)
    if not ok_apr:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-003",
            detail=f"Adapter registration ApprovalSet verification failed: {msg_apr}",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-F10-003",
        detail="Adapter registration authorized by non-agent ApprovalSet with pinned qualification",
    )


def evaluate_pd_f10_004_execution_gate_enforcement(
    authorized_request: Optional[Any],
    execution_lease: Optional[Any],
    budget_reservation: Optional[Any],
    fence: Optional[Any],
    worker_execute_attempt: bool = False,
    execution_timeout: bool = False,
    *,
    resource_limits: Optional[Mapping[str, Any]] = None,
    policy_override_authorized: bool = False,
    resource_usage: Optional[Mapping[str, Any]] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-F10-004 (Line 1023): Adapter execution MUST pass through ExecutionGate with lease, budget, fence, and bounded resource limits."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-004",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(worker_execute_attempt) is not bool or type(execution_timeout) is not bool or type(policy_override_authorized) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-004",
            detail="Flags must be exact bool",
        )

    if (
        not isinstance(authorized_request, Mapping) or not authorized_request
        or not isinstance(execution_lease, Mapping) or not execution_lease
        or not isinstance(budget_reservation, Mapping) or not budget_reservation
        or not isinstance(fence, Mapping) or not fence
    ):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-004",
            detail="ExecutionGate bypass: missing or invalid authorized request, lease, budget reservation, or fence",
        )

    from sclass.qualification.f10_validation import validate_resource_limits

    limits_ok, limit_reasons = validate_resource_limits(
        resource_limits, policy_override_authorized=policy_override_authorized
    )
    if not limits_ok:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-004",
            detail=f"Invalid or unbounded adapter resource_limits: {', '.join(limit_reasons)}",
        )

    if execution_timeout:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-004",
            detail="Adapter execution timed out exceeding declared bounded limit",
        )

    if resource_usage is not None:
        if not isinstance(resource_usage, Mapping):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F10-004",
                detail="Invalid resource_usage payload",
            )
        assert resource_limits is not None
        if (
            float(resource_usage.get("cpu_s", 0)) > float(resource_limits["cpu_s"])
            or int(resource_usage.get("memory_bytes", 0)) > int(resource_limits["memory_bytes"])
            or int(resource_usage.get("tokens", 0)) > int(resource_limits["tokens"])
        ):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F10-004",
                detail="Adapter execution exceeded declared CPU, memory, or token limit",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-F10-004",
        detail="ExecutionGate passed with valid lease, budget reservation, fence, and bounded resource limits",
    )


def evaluate_pd_f10_005_qualification_matrix(
    frozen_required_tests: Optional[Mapping[str, Mapping[str, Any]]],
    additional_product_tests: Optional[Mapping[str, Mapping[str, Any]]],
    *,
    conformance_report: Optional[Mapping[str, Any]] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-F10-005 (Line 1024): Qualification MUST pass all 14 frozen adapter tests, A1, A2, and A3."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-005",
            detail="Caller lacks qualified evaluator authority",
        )

    if not isinstance(frozen_required_tests, Mapping) or not isinstance(additional_product_tests, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-005",
            detail="Qualification matrix missing test results payload",
        )

    for test_name in FROZEN_ADAPTER_TESTS:
        t_data = frozen_required_tests.get(test_name)
        if not isinstance(t_data, Mapping) or t_data.get("self_attested") is True or t_data.get("result") != "PASS":
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F10-005",
                detail=f"Frozen adapter qualification test failed or missing: {test_name}",
            )

    for test_name in ADDITIONAL_PRODUCT_TESTS:
        t_data = additional_product_tests.get(test_name)
        if not isinstance(t_data, Mapping) or t_data.get("self_attested") is True or t_data.get("result") != "PASS":
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F10-005",
                detail=f"Additional qualification test failed or missing: {test_name}",
            )

    if conformance_report is not None:
        from sclass.qualification.f10_validation import compute_sha256_json

        if not isinstance(conformance_report, Mapping) or conformance_report.get("verdict") != "QUALIFIED":
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F10-005",
                detail="Conformance runner report verdict is not QUALIFIED",
            )
        expected_digest = compute_sha256_json({
            "adapter_id": conformance_report.get("adapter_id"),
            "adapter_version": conformance_report.get("adapter_version"),
            "adapter_digest": conformance_report.get("adapter_digest"),
            "category": conformance_report.get("category"),
            "verdict": conformance_report.get("verdict"),
            "frozen_results": conformance_report.get("frozen_results"),
            "additional_results": conformance_report.get("additional_results"),
            "provenance_bindings": conformance_report.get("provenance_bindings"),
            "failures": conformance_report.get("failures"),
        })
        if conformance_report.get("report_digest") != expected_digest:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F10-005",
                detail="Conformance runner report_digest tampered or mismatched",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-F10-005",
        detail="All 14 frozen adapter tests and A1-A3 additional product tests passed",
    )


def evaluate_pd_f10_006_independent_verification(
    is_critical_lane: Optional[bool] = None,
    qualified_independent_verifier: Optional[str] = None,
    primary_result: Optional[str] = None,
    independent_result: Optional[str] = None,
    *,
    primary_verifier: Optional[str] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-F10-006 (Line 1025): CRITICAL-lane independent verification MUST use qualified independent verifier."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-006",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(is_critical_lane) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-006",
            detail="is_critical_lane must be an exact boolean",
        )

    if is_critical_lane is True:
        if type(qualified_independent_verifier) is not str or not qualified_independent_verifier.strip():
            return GateOutput(
                state=GateState.BLOCKED_ON_HUMAN,
                must_id="PD-F10-006",
                detail="No qualified independent verifier available for CRITICAL lane",
            )
        if type(primary_verifier) is str and primary_verifier.strip() == qualified_independent_verifier.strip():
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F10-006",
                detail="Independent verifier must be distinct from primary verifier",
            )
        if (
            primary_result is None
            or independent_result is None
            or primary_result != independent_result
        ):
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
    if not isinstance(payload, Mapping):
        payload = {}

    res: Dict[str, GateOutput] = {}

    if "tool_call" in payload or "adapter_record" in payload:
        res["PD-F10-001"] = evaluate_pd_f10_001_contract_invocation(
            payload.get("tool_call"),
            payload.get("adapter_record"),
            payload.get("category"),
            authority=authority,
        )
    else:
        res["PD-F10-001"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-001",
            detail="Payload missing required key: tool_call or adapter_record",
        )

    if "adapter" in payload:
        res["PD-F10-002"] = evaluate_pd_f10_002_usable_adapter_binding(
            payload.get("adapter"),
            conformance_report=payload.get("conformance_report"),
            authority=authority,
        )
    else:
        res["PD-F10-002"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-002",
            detail="Payload missing required key: adapter",
        )

    if "actor" in payload or "operation" in payload:
        res["PD-F10-003"] = evaluate_pd_f10_003_adapter_registration_authority(
            payload.get("actor", ""),
            payload.get("operation", ""),
            payload.get("canonical_write_authorized"),
            approval_set=payload.get("approval_set"),
            approval_context=payload.get("approval_context"),
            evidence_adapter_digest=payload.get("evidence_adapter_digest"),
            current_adapter_digest=payload.get("current_adapter_digest"),
            authority=authority,
        )
    else:
        res["PD-F10-003"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-003",
            detail="Payload missing required key: actor or operation",
        )

    if "authorized_request" in payload or "execution_lease" in payload:
        res["PD-F10-004"] = evaluate_pd_f10_004_execution_gate_enforcement(
            payload.get("authorized_request"),
            payload.get("execution_lease"),
            payload.get("budget_reservation"),
            payload.get("fence"),
            worker_execute_attempt=payload.get("worker_execute_attempt", False),
            execution_timeout=payload.get("execution_timeout", False),
            resource_limits=payload.get("resource_limits"),
            policy_override_authorized=payload.get("policy_override_authorized", False),
            resource_usage=payload.get("resource_usage"),
            authority=authority,
        )
    else:
        res["PD-F10-004"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-004",
            detail="Payload missing required execution gate keys",
        )

    if "frozen_required_tests" in payload or "additional_product_tests" in payload:
        res["PD-F10-005"] = evaluate_pd_f10_005_qualification_matrix(
            payload.get("frozen_required_tests"),
            payload.get("additional_product_tests"),
            conformance_report=payload.get("conformance_report"),
            authority=authority,
        )
    else:
        res["PD-F10-005"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-005",
            detail="Payload missing required qualification matrix keys",
        )

    if "is_critical_lane" in payload:
        res["PD-F10-006"] = evaluate_pd_f10_006_independent_verification(
            payload.get("is_critical_lane"),
            qualified_independent_verifier=payload.get("qualified_independent_verifier"),
            primary_result=payload.get("primary_result"),
            independent_result=payload.get("independent_result"),
            primary_verifier=payload.get("primary_verifier"),
            authority=authority,
        )
    else:
        res["PD-F10-006"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-F10-006",
            detail="Payload missing required key: is_critical_lane",
        )

    return res
