"""Permanent negative tests for all 51 MUSTs identified by tools/audit_negative_branches.py."""
from __future__ import annotations

import hashlib
import pathlib
import sys
from typing import Any, Dict

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (REPO_ROOT / "src", REPO_ROOT / "10-CONFORMANCE"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from sclass import canonical_c1
from sclass.product.artifacts import freeze_to_c1_compatible
from sclass.product.adapter_qualification_contract import (
    FROZEN_ADAPTER_TESTS,
    ADDITIONAL_PRODUCT_TESTS,
)
from sclass.qualification.f10_validation import DEFAULT_RESOURCE_LIMITS
from sclass.product.claim_ledger import (
    InMemoryCanonicalDependencyResolver,
    InMemoryKernelEvidenceResolver,
    InMemoryObligationClosureResolver,
    InMemoryRepositoryIntelligenceIndex,
)
from sclass.product.gate import GateOutput, GateState
from sclass.product.predicate_evaluator import (
    AcceptanceContract,
    Constraint,
    ConstraintType,
    Digest,
    InMemoryFrozenResolver,
    Requirement,
    VerificationStep,
)
from sclass.product.registry import REGISTRY_AUTHORITY, evaluate
from sclass.product.traceability import InMemorySourceRefResolver
from sclass.qualification.adapter_registry import use_test_only_qualified_registry
from sclass_semantics_v6_0_1 import (
    Authority,
    CompositionMode,
    DiscoveryMethod,
    EnforcementPhase,
    EvidenceComposition,
    EvidenceKind,
    IndependenceLevel,
    IndependenceProfile,
    RequiredEvidence,
    ResourceBudget,
    Severity,
    SourceType,
    WaiverRules,
)


def _sha256_hex(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _c1_digest(obj: Any) -> str:
    return hashlib.sha256(canonical_c1(freeze_to_c1_compatible(obj))).hexdigest()


def _assert_negative_domain_failure(
    must_id: str, payload: Dict[str, Any], *, needs_engine: bool = False
) -> GateOutput:
    if needs_engine:
        # Unqualified default registry must fail closed with ENGINE_NOT_QUALIFIED
        no_eng = evaluate(must_id, payload, authority=REGISTRY_AUTHORITY)
        assert no_eng.state != GateState.SATISFIED
        with use_test_only_qualified_registry():
            out = evaluate(must_id, payload, authority=REGISTRY_AUTHORITY)
    else:
        out = evaluate(must_id, payload, authority=REGISTRY_AUTHORITY)

    assert out.state != GateState.SATISFIED, f"{must_id} unexpectedly satisfied on negative input"
    detail_text = out.detail or ""
    assert detail_text.strip() or (isinstance(out.must_id, str) and out.must_id.strip()), (
        f"{must_id} empty negative detail and must_id: {out}"
    )
    assert "unexpected evidence key" not in detail_text, f"{must_id} hit key-strip guard: {out.detail}"
    assert "Caller lacks qualified evaluator authority" not in detail_text
    assert "ENGINE_NOT_QUALIFIED" not in detail_text
    return out


_F5_BASE: Dict[str, Any] = {
    "phase": "P5",
    "canonical_state_binding": {"target": "t1"},
    "pinned_guidance": {"skill": "s1"},
    "policy_version": "v1",
    "evaluator_version": "1.0",
    "evaluation_instant": "2026-11-22T00:00:00Z",
}

_F6_CHAIN_SPEC: Dict[str, Any] = {
    "nodes": ["REQ-1", "ACC-1", "VER-1", "TEST-1", "EV-1", "OBL-1"],
    "obligations": ["OBL-1"],
    "source_refs": ["REQ-1", "OBL-1"],
    "links": [
        {"link_type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "ACC-1"},
        {"link_type": "ACCEPTANCE_TO_VERIFICATION", "source": "ACC-1", "destination": "VER-1"},
        {"link_type": "VERIFICATION_TO_TEST", "source": "VER-1", "destination": "TEST-1"},
        {"link_type": "TEST_TO_EVIDENCE", "source": "TEST-1", "destination": "EV-1"},
        {"link_type": "EVIDENCE_TO_OBLIGATION", "source": "EV-1", "destination": "OBL-1"},
    ],
}

_F8_STEP_PACK_ARGS: Dict[str, Any] = {
    "phase": "P5",
    "task_ref": "TASK-10",
    "canonical_state_binding": "SB-10",
    "pinned_skills": ["SK-1"],
    "context_budget_bytes": 4096,
}


def _build_frozen_resolver_missing_req() -> InMemoryFrozenResolver:
    con = Constraint(
        constraint_id="CON-1",
        description="Safety constraint",
        constraint_type=ConstraintType.SECURITY,
        authority=Authority.POLICY,
        enforcement_phase=EnforcementPhase.EXECUTION,
        severity=Severity.BLOCKING,
        scope=(),
        version=1,
    )
    ind = IndependenceProfile(
        IndependenceLevel.NONE,
        IndependenceLevel.NONE,
        IndependenceLevel.NONE,
        IndependenceLevel.NONE,
        IndependenceLevel.NONE,
    )
    req_ev = RequiredEvidence("req-key-1", EvidenceKind.BEHAVIORAL, "verifier-1", ind, (), True, 1)
    comp = EvidenceComposition(CompositionMode.ALL_OF, 0)
    ac = AcceptanceContract(
        "AC-1", "obl-1", 1, (req_ev,), comp, WaiverRules((), 1000, False), Authority.USER
    )
    budget = ResourceBudget(10, 10, 10, 1000, 10, 10, 10, 10, 10, 5000, 10)
    vs = VerificationStep(
        step_id="VS-1",
        evidence_kind=EvidenceKind.BEHAVIORAL,
        verifier_id="verifier-1",
        verifier_version="1.0",
        config_digest=Digest("sha256:" + "c" * 64),
        timeout_ms=5000,
        budget=budget,
    )
    # Intentionally omits REQ-1 to verify negative resolution failure
    return InMemoryFrozenResolver({"CON-1": con, "AC-1": ac, "VS-1": vs})


# ---- 1..5: PD-CH1 ----

def test_negative_pd_ch1_002() -> None:
    _assert_negative_domain_failure(
        "PD-CH1-002",
        {
            "subordinate_to_frozen_package": False,
            "conflicts_with_kernel": True,
            "overrides_kernel_predicate": True,
        },
    )


def test_negative_pd_ch1_004() -> None:
    _assert_negative_domain_failure(
        "PD-CH1-004",
        {
            "concept_name": "TestInputSet",
            "classifications": ["product_projection", "kernel_canonical"],
            "presented_as_kernel_type": True,
        },
    )


def test_negative_pd_ch1_005() -> None:
    _assert_negative_domain_failure("PD-CH1-005", {"authority_class": None})


def test_negative_pd_ch1_006() -> None:
    _assert_negative_domain_failure(
        "PD-CH1-006",
        {
            "source_namespace": "process",
            "target_namespace": "kernel",
            "defines_cross_namespace_authority": True,
            "isolation_enforced": False,
        },
    )


def test_negative_pd_ch1_007() -> None:
    _assert_negative_domain_failure(
        "PD-CH1-007",
        {
            "work_type": "BUG_FIX",
            "domain": "Backend",
            "removes_mandatory_control": True,
            "mandatory_controls_preserved": False,
        },
    )


# ---- 6: PD-CH10-007 ----

def test_negative_pd_ch10_007() -> None:
    _assert_negative_domain_failure(
        "PD-CH10-007",
        {"cross_linked_to_master": False, "unknown_references_present": True},
    )


# ---- 7..15: PD-CH3 ----

def test_negative_pd_ch3_001() -> None:
    _assert_negative_domain_failure(
        "PD-CH3-001",
        {
            "objective_revision": "rev-1",
            "spec_anchor_digests": ["a"],
            "expected_objective_revision": "rev-2",
            "expected_anchor_digests": ["a"],
        },
    )


def test_negative_pd_ch3_002() -> None:
    _assert_negative_domain_failure(
        "PD-CH3-002", {"requirements": [], "non_goals": []}, needs_engine=True
    )


def test_negative_pd_ch3_003() -> None:
    _assert_negative_domain_failure(
        "PD-CH3-003",
        {"scope_changed": True, "canonical_decision_recorded": False, "human_confirmed": False},
        needs_engine=True,
    )


def test_negative_pd_ch3_006() -> None:
    _assert_negative_domain_failure(
        "PD-CH3-006",
        {"tool_identity": "tool-x", "qualification_recorded": False, "claimed_authoritative": True},
        needs_engine=True,
    )


def test_negative_pd_ch3_007() -> None:
    _assert_negative_domain_failure(
        "PD-CH3-007",
        {
            "canonical_decision_outcome": "FEATURE",
            "projected_work_type": "SPIKE",
            "agent_override_attempted": True,
        },
    )


def test_negative_pd_ch3_009() -> None:
    _assert_negative_domain_failure(
        "PD-CH3-009",
        {
            "flow_identity": "FLOW-1",
            "contract_tests_present": False,
            "computed_lane": "CRITICAL",
            "agent_selected_lane": "FAST",
        },
        needs_engine=True,
    )


def test_negative_pd_ch3_010() -> None:
    _assert_negative_domain_failure(
        "PD-CH3-010",
        {
            "flow_type": "MIGRATION",
            "baseline_digest": "",
            "rollback_inputs_bound": False,
            "verification_inputs_bound": False,
        },
        needs_engine=True,
    )


def test_negative_pd_ch3_011() -> None:
    _assert_negative_domain_failure(
        "PD-CH3-011",
        {"adapter_identity": "tool-x", "is_qualified": False, "marked_supported": True},
        needs_engine=True,
    )


def test_negative_pd_ch3_012() -> None:
    _assert_negative_domain_failure(
        "PD-CH3-012",
        {
            "human_decision_required": True,
            "decision_suppressed_by_cap": True,
            "interruption_budget_exceeded": True,
        },
        needs_engine=True,
    )


# ---- 16..17: PD-CH4 ----

def test_negative_pd_ch4_002() -> None:
    _assert_negative_domain_failure(
        "PD-CH4-002",
        {"has_execution_claim": True, "has_structured_results": False, "raw_result_digest": ""},
        needs_engine=True,
    )


def test_negative_pd_ch4_008() -> None:
    _assert_negative_domain_failure(
        "PD-CH4-008",
        {"threat_matrix_rows": [{"threat_id": "T-01"}]},
    )


# ---- 18..20: PD-CH5 ----

def test_negative_pd_ch5_003() -> None:
    base = {
        "phase": "P5",
        "canonical_state_binding": {"policy_version": "v1", "target": "t1"},
        "task_ref": "TASK-CH5",
        "spec_anchor_digest": _sha256_hex("spec"),
        "input_digests": [_sha256_hex("in")],
        "pinned_guidance": "G1",
        "policy_version": "v1",
        "evaluator_version": "eval-1.0",
        "evaluation_instant": "2026-11-22T00:00:00Z",
    }
    changed = dict(base)
    changed["pinned_guidance"] = "G2"
    _assert_negative_domain_failure(
        "PD-CH5-003",
        {
            "cached_entry": base,
            "evaluation_tuple": changed,
            "cached_guidance_digest": "G1",
            "current_guidance_digest": "G2",
        },
    )


def test_negative_pd_ch5_004() -> None:
    _assert_negative_domain_failure(
        "PD-CH5-004",
        {"claim": "10x faster", "benchmark_corpus": "c", "measurement_window": "w"},
        needs_engine=True,
    )


def test_negative_pd_ch5_005() -> None:
    _assert_negative_domain_failure(
        "PD-CH5-005",
        {"numerator": 5, "denominator": -1},
        needs_engine=True,
    )


# ---- 21..22: PD-CH6 ----

def test_negative_pd_ch6_003() -> None:
    _assert_negative_domain_failure(
        "PD-CH6-003",
        {"scope_specific_qualification": True, "effective_revocation_present": True},
        needs_engine=True,
    )


def test_negative_pd_ch6_006() -> None:
    _assert_negative_domain_failure(
        "PD-CH6-006",
        {"playbook_content": {"phases": ["ingest"], "unqualified_adapter_claimed_usable": True}},
        needs_engine=True,
    )


# ---- 23..24: PD-F1 ----

def test_negative_pd_f1_001() -> None:
    _assert_negative_domain_failure(
        "PD-F1-001",
        {"artifact": {"artifact_class": "data", "prose": "only prose"}, "independent_verifier_result": "PASS"},
    )


def test_negative_pd_f1_005() -> None:
    _assert_negative_domain_failure(
        "PD-F1-005",
        {
            "artifact": {
                "artifact_class": "data",
                "contract": {"schema": "v1"},
                "confirmed": {"min": 2},
                "proposed": {"min": 1},
            },
            "confirmed_artifact": {"min": 2},
            "structural_diff_procedure": lambda _c, _p: True,
        },
        needs_engine=True,
    )


# ---- 25..29: PD-F10-001..005 ----

def test_negative_pd_f10_001() -> None:
    _assert_negative_domain_failure(
        "PD-F10-001",
        {
            "tool_call": {"tool_identity": "bandit", "version": "1.9.4"},
            "adapter_record": {"category": "security/supply-chain", "declared_contract": True},
            "category": "security/supply-chain",
        },
    )


def test_negative_pd_f10_002() -> None:
    _assert_negative_domain_failure(
        "PD-F10-002",
        {
            "adapter": {
                "adapter_id": "A-1",
                "tool_identity": "validator-x@1.2.3",
                "qualification_record_ref": None,
                "evidence_binding_fields": ["obligation_id"],
            }
        },
        needs_engine=True,
    )


def test_negative_pd_f10_003() -> None:
    _assert_negative_domain_failure(
        "PD-F10-003",
        {"actor": "agent", "operation": "REGISTER_ADAPTER", "approval_set": None},
        needs_engine=True,
    )


def test_negative_pd_f10_004() -> None:
    bad_limits = dict(DEFAULT_RESOURCE_LIMITS)
    bad_limits["max_executions"] = 0
    _assert_negative_domain_failure(
        "PD-F10-004",
        {
            "authorized_request": {"id": "REQ-1"},
            "execution_lease": {"lease_id": "L-1"},
            "budget_reservation": {"cost": 10},
            "fence": {"fence_id": "F-1"},
            "worker_execute_attempt": True,
            "execution_timeout": False,
            "resource_limits": bad_limits,
        },
        needs_engine=True,
    )


def test_negative_pd_f10_005() -> None:
    frozen = {t: {"result": "PASS"} for t in FROZEN_ADAPTER_TESTS}
    addl = {t: {"result": "PASS"} for t in ADDITIONAL_PRODUCT_TESTS}
    addl["A2_differential_result_detection"] = {"result": "FAIL"}
    _assert_negative_domain_failure(
        "PD-F10-005",
        {"frozen_required_tests": frozen, "additional_product_tests": addl},
        needs_engine=True,
    )


# ---- 30..36: PD-F2 ----

def test_negative_pd_f2_001() -> None:
    _assert_negative_domain_failure(
        "PD-F2-001",
        {"spec": {"predicate": "x @@ INVALID_TOKEN 5"}, "consumer": "p3_invariant"},
    )


def test_negative_pd_f2_002() -> None:
    _assert_negative_domain_failure(
        "PD-F2-002",
        {"spec": {"predicate": "x GREATER_THAN 1"}, "consumer": "p3_invariant"},
    )


def test_negative_pd_f2_003() -> None:
    _assert_negative_domain_failure(
        "PD-F2-003",
        {"base_result": "UNSAT", "budget_expired": True, "assignments_evaluated": 1, "budget_limit": 1},
        needs_engine=True,
    )


def test_negative_pd_f2_004() -> None:
    _assert_negative_domain_failure(
        "PD-F2-004",
        {"classification": "TAUTOLOGY", "domain_bounds_matched": False},
        needs_engine=True,
    )


def test_negative_pd_f2_005() -> None:
    _assert_negative_domain_failure(
        "PD-F2-005",
        {"spec": {"predicate": "ALWAYS EVENTUALLY x EQUALS 1"}, "consumer": "p3_invariant"},
        needs_engine=True,
    )


def test_negative_pd_f2_006() -> None:
    _assert_negative_domain_failure(
        "PD-F2-006",
        {
            "adapter_outputs": ["SAT"],
            "reference_outputs": ["UNSAT"],
            "uses_applicable_f4_budget": False,
        },
        needs_engine=True,
    )


def test_negative_pd_f2_007() -> None:
    _assert_negative_domain_failure(
        "PD-F2-007",
        {
            "bindings": {"requirement_ref": "REQ-1", "constraint_ref": "CON-1"},
            "resolver": _build_frozen_resolver_missing_req(),
        },
    )


# ---- 37: PD-F3-003 ----

def test_negative_pd_f3_003() -> None:
    _assert_negative_domain_failure(
        "PD-F3-003",
        {
            "structured_a": {"limit": 3},
            "structured_b": {"limit": 5},
            "prose": "non-authoritative prose cannot resolve conflict",
        },
    )


# ---- 38..41: PD-F5 ----

def test_negative_pd_f5_001() -> None:
    pl = dict(_F5_BASE)
    pl["evaluation_instant"] = ""
    _assert_negative_domain_failure("PD-F5-001", pl)


def test_negative_pd_f5_002() -> None:
    pl = dict(_F5_BASE)
    pl["checks"] = [{"check_id": "C-1", "must_id": "PD-F5-002", "status": "MISSING"}]
    _assert_negative_domain_failure("PD-F5-002", pl)


def test_negative_pd_f5_004() -> None:
    pl = dict(_F5_BASE)
    pl["pinned_evaluator_version"] = "2.0"
    _assert_negative_domain_failure("PD-F5-004", pl, needs_engine=True)


def test_negative_pd_f5_005() -> None:
    pl = dict(_F5_BASE)
    pl["skill_added_checks"] = [{"check_id": "SK-1", "must_id": "PD-F5-005", "status": "MISSING"}]
    _assert_negative_domain_failure("PD-F5-005", pl)


# ---- 42..44: PD-F6 ----

def test_negative_pd_f6_002() -> None:
    spec = dict(_F6_CHAIN_SPEC)
    spec["orphan_nodes"] = ["REQ-ORPHAN"]
    _assert_negative_domain_failure(
        "PD-F6-002",
        {
            "spec": spec,
            "resolver": InMemorySourceRefResolver({"REQ-1": {"id": "REQ-1"}, "OBL-1": {"id": "OBL-1"}}),
            "freshness_predicate": lambda _n: True,
            "mode": "realized",
        },
    )


def test_negative_pd_f6_003() -> None:
    _assert_negative_domain_failure(
        "PD-F6-003",
        {
            "spec": {"nodes": ["REQ-1"], "links": []},
            "resolver": InMemorySourceRefResolver({"REQ-1": {"id": "REQ-1"}}),
            "freshness_predicate": lambda _n: True,
            "mode": "realized",
        },
    )


def test_negative_pd_f6_006() -> None:
    _assert_negative_domain_failure(
        "PD-F6-006",
        {
            "spec": {
                "nodes": ["REQ-1", "ACC-1", "VER-1", "TEST-1"],
                "obligations": ["OBL-1"],
                "source_refs": ["REQ-1"],
                "links": _F6_CHAIN_SPEC["links"][:3],
            },
            "resolver": InMemorySourceRefResolver({"REQ-1": {"id": "REQ-1"}}),
            "freshness_predicate": lambda _n: True,
            "mode": "realized",
        },
    )


# ---- 45..48: PD-F8 ----

def test_negative_pd_f8_001() -> None:
    _assert_negative_domain_failure(
        "PD-F8-001", {"repeat_1_digest": "D1", "repeat_2_digest": "D2"}
    )


def test_negative_pd_f8_002() -> None:
    _assert_negative_domain_failure(
        "PD-F8-002",
        {"items": ["it1"], "item_bytes": {"it1": 10}, "precedence": ["it1"], "byte_budget": -1},
    )


def test_negative_pd_f8_003() -> None:
    _assert_negative_domain_failure(
        "PD-F8-003",
        {
            "canonical_state_binding": "",
            "anchors": ["REQ-1"],
            "transcript_present": False,
        },
    )


def test_negative_pd_f8_004() -> None:
    _assert_negative_domain_failure(
        "PD-F8-004",
        {"step_pack_args": dict(_F8_STEP_PACK_ARGS), "expected_digest": "wrong-digest"},
        needs_engine=True,
    )


# ---- 49..51: PD-F9 ----

def test_negative_pd_f9_002() -> None:
    _assert_negative_domain_failure("PD-F9-002", {"numerator": 5, "denominator": None})


def test_negative_pd_f9_003() -> None:
    _assert_negative_domain_failure(
        "PD-F9-003",
        {"paired_evaluation": False},
        needs_engine=True,
    )


def test_negative_pd_f9_004() -> None:
    _assert_negative_domain_failure(
        "PD-F9-004",
        {
            "canonical_cost": 10,
            "canonical_time_seconds": 20,
            "agent_reported_cost": 1,
            "agent_reported_time_seconds": 2,
            "expected_metric_cost": 1,
            "expected_metric_time_seconds": 2,
        },
    )
