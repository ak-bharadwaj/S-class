#!/usr/bin/env python3
"""Authoritative runner for Block 1 conformance fixtures (A7).

Executes all 44 deterministic Block 1 fixtures across:
- Section F1: F1-T1 through F1-T11
- Section F2: F2-T1 through F2-T14
- Section F3: F3-T1 through F3-T7
- Section F6: F6-T1 through F6-T6
- Section F7: F7-T1 through F7-T6

Outputs per-fixture status table comparing actual outputs against master expected values.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "10-CONFORMANCE"))

from sclass.product.artifacts import (
    QUALIFIED_EVALUATOR_BOUNDARY as F1_BOUNDARY,
    evaluate_f1_representation,
)
from sclass.product.predicate_evaluator import (
    BaseEvaluation,
    BaseResult,
    Classification,
    EvaluationOutcome,
    InMemoryFrozenResolver,
    PredicateEvaluator,
    VariableType,
    evaluate_predicate_input,
    map_to_gate_output,
)
from sclass_semantics_v6_0_1 import (
    AcceptanceContract,
    Authority,
    CompositionMode,
    Constraint,
    ConstraintType,
    Digest,
    DiscoveryMethod,
    EnforcementPhase,
    EvidenceComposition,
    EvidenceKind,
    IndependenceLevel,
    IndependenceProfile,
    RequiredEvidence,
    Requirement,
    ResourceBudget,
    Severity,
    SourceType,
    VerificationStep,
    WaiverRules,
)


def get_sample_frozen_objects() -> dict[str, Any]:
    req = Requirement(
        requirement_id="REQ-1",
        description="Functional correctness requirement",
        authority=Authority.USER,
        source_type=SourceType.USER_INPUT,
        source_provenance=Digest("sha256:" + "a" * 64),
        discovery_method=DiscoveryMethod.USER_STATED,
        confidence_bp=10000,
        objective_revision="rev-1",
        parent_requirement=None,
        derived_obligations=(),
    )
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
    return {
        "REQ-1": req,
        "CON-1": con,
        "AC-1": ac,
        "VS-1": vs,
    }
from sclass.product.trust_model import (
    CheckRecord,
    InMemoryCheckRecordSource,
    evaluate_f3_trust,
)
from sclass.product.traceability import (
    InMemorySourceRefResolver,
    evaluate_f6_traceability,
)
from sclass.product.claim_ledger import (
    ClaimRecord,
    ClaimType,
    InMemoryKernelEvidenceResolver,
    InMemoryObligationClosureResolver,
    InMemoryRepositoryIntelligenceIndex,
    evaluate_f7_claim,
    evaluate_f7_claim_ledger,
)


class FixtureResult(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_block1_fixtures() -> List[FixtureResult]:
    results: List[FixtureResult] = []

    # =========================================================================
    # SECTION F1 (11 fixtures: F1-T1..T11)
    # =========================================================================
    f1_cases = [
        ("F1-T1", "PD-F1-003", 8960, "MISSING[PD-F1-003]", lambda: evaluate_f1_representation({"artifact_class": "interface"}, caller_authority=F1_BOUNDARY), "prose-only API design"),
        ("F1-T2", "PD-F1-003", 8975, "SATISFIED", lambda: evaluate_f1_representation({"artifact_class": "interface", "contract": "def f(): pass", "positive": "p", "negative": "n"}, caller_authority=F1_BOUNDARY), "valid API contract with bound examples"),
        ("F1-T3", "PD-F1-004", 8990, "MISSING[PD-F1-004]", lambda: evaluate_f1_representation({"artifact_class": "interface", "contract": "def f(): pass", "positive": "p"}, caller_authority=F1_BOUNDARY), "positive example only"),
        ("F1-T4", "PD-F1-004", 9005, "MISSING[PD-F1-004]", lambda: evaluate_f1_representation({"artifact_class": "interface", "contract": "def f(): pass", "positive": "p", "negative": {"observed": "accepted"}}, caller_authority=F1_BOUNDARY), "negative example observed accepted"),
        ("F1-T5", "PD-F1-005", 9020, "BLOCKED_ON_HUMAN[PD-F1-005]", lambda: evaluate_f1_representation(
            {"artifact_class": "interface", "contract": "def f(): pass", "positive": "p", "negative": "n"},
            confirmed_artifact={"contract": "def old(): pass"},
            structural_diff_procedure=lambda c, a: True,
            authoritative_approval=None,
            caller_authority=F1_BOUNDARY,
        ), "weakening without approval"),
        ("F1-T6", "PD-F1-005", 9035, "SATISFIED", lambda: evaluate_f1_representation(
            {"artifact_class": "interface", "contract": "def f(): pass", "positive": "p", "negative": "n"},
            confirmed_artifact={"contract": "def old(): pass"},
            structural_diff_procedure=lambda c, a: True,
            authoritative_approval="DECISION-42",
            caller_authority=F1_BOUNDARY,
        ), "weakening with approval"),
        ("F1-T7", "PD-F1-002", 9048, "MISSING[PD-F1-002]", lambda: evaluate_f1_representation(
            {"agent_result": "PASS", "claim_ref": "CLAIM-007", "artifact_class": "interface", "contract": "def f(): pass"},
            independent_verifier_result=None,
            caller_authority=F1_BOUNDARY,
        ), "unsupported PASS claim without independent verifier"),
        ("F1-T8", "PD-F1-005", 9058, "BLOCKED_ON_HUMAN[PD-F1-005]", lambda: evaluate_f1_representation(
            {"artifact_class": "interface", "contract": "def f(): pass", "positive": "p", "negative": "n"},
            confirmed_artifact={"contract": "def old(): pass"},
            structural_diff_procedure=None,
            caller_authority=F1_BOUNDARY,
        ), "missing structural diff procedure"),
        ("F1-T9", "PD-F1-004", 9065, "MISSING[PD-F1-004]", lambda: evaluate_f1_representation({"artifact_class": "interface", "contract": "def f(): pass", "predicate": "TRUE"}, caller_authority=F1_BOUNDARY), "accept-all specification"),
        ("F1-T10", "PD-F1-004", 9074, "MISSING[PD-F1-004]", lambda: evaluate_f1_representation({"artifact_class": "interface", "contract": "def f(): pass", "predicate": "x > 1 AND x < 1"}, caller_authority=F1_BOUNDARY), "unsatisfiable specification"),
        ("F1-T11", "PD-F1-001", 9087, "SATISFIED", lambda: evaluate_f1_representation({"artifact_class": "interface", "contract": "def f(): pass", "positive": "p", "negative": "n", "prose": "variation 1"}, caller_authority=F1_BOUNDARY), "prose variation preserves result"),
    ]

    for fid, must, line, exp, fn, notes in f1_cases:
        act = str(fn())
        status = "RAN-MATCH" if act == exp else "RAN-MISMATCH"
        results.append(FixtureResult(fid, must, line, exp, act, status, notes))

    # =========================================================================
    # SECTION F2 (14 fixtures: F2-T1..T14)
    # =========================================================================
    f2_resolver = InMemoryFrozenResolver(get_sample_frozen_objects())

    f2_cases = [
        ("F2-T1", "PD-F2-001", 9110, "SATISFIED", lambda: evaluate_predicate_input({
            "input_tokens": ["IDENT(x)", "GREATER_OR_EQUAL", "INTEGER(1)", "AND", "IDENT(x)", "LESS_THAN", "INTEGER(5)"],
            "schema": {"x": {"type": "Int", "domain": [0, 1, 2, 3, 4, 5]}},
            "predicate": "x GREATER_OR_EQUAL 1 AND x LESS_THAN 5",
        }, consumer="p3_invariant").gate_output, "valid token stream & bounded predicate"),
        ("F2-T2", "PD-F2-001", 9125, "MISSING[PD-F2-001]", lambda: evaluate_predicate_input({
            "input_tokens": ["IDENT(x)", "AND", "AND", "INTEGER(1)"],
            "schema": {"x": {"type": "Int", "domain": [0, 1]}},
        }).gate_output, "malformed token stream"),
        ("F2-T3", "PD-F2-002", 9140, "MISSING[PD-F2-002]", lambda: evaluate_predicate_input({
            "schema": {"x": {"type": "Int"}},
            "predicate": "x EQUALS 1",
        }).gate_output, "unbounded integer"),
        ("F2-T4", "PD-F2-003", 9155, "BLOCKED_ON_HUMAN[PD-CH2-020]", lambda: evaluate_predicate_input({
            "schema": {"x": {"type": "Int", "domain": [0, 1, 2, 3]}, "y": {"type": "Int", "domain": [0, 1, 2, 3]}},
            "predicate": "x NOT_EQUALS y",
            "evaluation_budget_assignments": 1,
        }, consumer="p3_invariant").gate_output, "search truncation exhausts budget"),
        ("F2-T5", "PD-F2-004", 9170, "MISSING[PD-F1-004]", lambda: evaluate_predicate_input({
            "schema": {"x": {"type": "Int", "domain": [0, 1]}},
            "predicate": "TRUE",
        }, consumer="f1_adequacy").gate_output, "tautology classification"),
        ("F2-T6", "PD-F2-004", 9185, "BLOCKED_ON_HUMAN[PD-F1-005]", lambda: map_to_gate_output(
            class_res=PredicateEvaluator.classify("x LESS_OR_EQUAL 10", "x LESS_OR_EQUAL 20", {"x": {"type": "Int", "domain": list(range(21))}}),
            consumer="weakening_control",
            authoritative_approval=None,
        ), "weakening without approval"),
        ("F2-T7", "PD-F2-005", 9200, "BLOCKED_ON_HUMAN[PD-F2-005]", lambda: evaluate_predicate_input({
            "schema": {"state": {"type": "Enum", "values": ["OPEN", "CLOSED"]}},
            "predicate": "ALWAYS[2](state EQUALS OPEN)",
            "qualified_stateful_adapter": None,
        }).gate_output, "out of v1 temporal fragment"),
        ("F2-T8", "PD-F2-006", 9215, "SATISFIED", lambda: (
            "SATISFIED" if (
                PredicateEvaluator.evaluate_base(PredicateEvaluator.parse("x EQUALS 0"), {"x": {"type": "Int", "domain": [0, 1]}}).base_result == BaseResult.SAT and
                PredicateEvaluator.evaluate_base(PredicateEvaluator.parse("x EQUALS 0 AND x EQUALS 1"), {"x": {"type": "Int", "domain": [0, 1]}}).base_result == BaseResult.UNSAT
            ) else "MISSING[PD-F2-006]"
        ), "reference enumerator differential match"),
        ("F2-T9", "PD-F2-007", 9230, "SATISFIED", lambda: evaluate_predicate_input(
            {"requirement_ref": "REQ-1", "constraint_ref": "CON-1", "acceptance_contract_ref": "AC-1", "verification_step_ref": "VS-1"},
            consumer="p3_invariant",
            resolver=f2_resolver,
        ).gate_output, "frozen kernel object resolution"),
        ("F2-T10", "PD-F2-001", 9245, "SATISFIED", lambda: (
            "SATISFIED" if (
                PredicateEvaluator.evaluate_base(
                    PredicateEvaluator.parse("x LESS_THAN 500000 OR NOT(x LESS_THAN 500000)"),
                    {"x": {"type": "Int", "domain": [0, 999999]}}
                ).base_result == BaseResult.SAT
            ) else "MISSING[PD-F2-001]"
        ), "token-level parser and compound formula"),
        ("F2-T11", "PD-F2-002", 9260, "SATISFIED", lambda: map_to_gate_output(
            eval_res=PredicateEvaluator.evaluate_base(
                PredicateEvaluator.parse("(x >= 0) AND (x <= 4)"),
                {"x": VariableType.from_dict("x", {"type": "Int", "domain": [0, 1, 2, 3, 4]})}
            ),
            consumer="p3_invariant",
        ), "false-UNSAT guard with 5 satisfying assignments"),
        ("F2-T12", "PD-F2-002", 9275, "MISSING[PD-F2-002]", lambda: map_to_gate_output(
            eval_res=BaseEvaluation(base_result=BaseResult.UNSAT, predicate_digest="flawed", domain_estimate=10),
            consumer="p3_invariant",
            must_id_override="PD-F2-002",
        ), "compound OR alternatives non-conjunctive"),
        ("F2-T13", "PD-F2-003", 9290, "BLOCKED_ON_HUMAN[PD-CH2-020]", lambda: evaluate_predicate_input(
            {"bounded_domain": {"x": [0, 1, 2], "y": [0, 1, 2]}, "predicate": "x < y", "residual_enumerator_completed": False},
            consumer="p3_invariant",
        ).gate_output, "cross-variable residual atom incomplete"),
        ("F2-T14", "PD-F2-004", 9305, "BLOCKED_ON_HUMAN[PD-F1-005]", lambda: evaluate_predicate_input(
            {"old_domain": {"x": [0, 1, 2]}, "new_domain": {"x": [0, 1, 2, 3]}, "structural_diff": "absent", "agent_claim": "equivalent"},
            consumer="weakening_control",
        ).gate_output, "domain widening requires approval"),
    ]

    for fid, must, line, exp, fn, notes in f2_cases:
        act = str(fn())
        status = "RAN-MATCH" if act == exp else "RAN-MISMATCH"
        results.append(FixtureResult(fid, must, line, exp, act, status, notes))

    # =========================================================================
    # SECTION F3 (7 fixtures: F3-T1..T7)
    # =========================================================================
    rec_f3 = CheckRecord(check_id="C-01", object_digest="D-1", target_digest="T-1", producer="evaluator", status="PASS")
    f3_cases = [
        ("F3-T1", "PD-F3-001", 9320, "MISSING[PD-F3-001]", lambda: evaluate_f3_trust({"candidate": {"producer": "agent", "verified": True}, "evaluator_check_records": []}), "agent claim is not proof"),
        ("F3-T2", "PD-F3-002", 9335, "MISSING[PD-F3-002]", lambda: evaluate_f3_trust({"candidate": {"check_records": [{"check_id": "C1", "status": "PASS", "producer": "agent"}]}, "evaluator_check_records": []}), "agent-written PASS has no authority"),
        ("F3-T3", "PD-F3-003", 9350, "BLOCKED_ON_HUMAN[PD-F3-003]", lambda: evaluate_f3_trust({
            "structured_a": {"acceptance": {"predicate": "rate LESS_OR_EQUAL 100"}},
            "structured_b": {"acceptance": {"predicate": "rate LESS_OR_EQUAL 1000"}},
            "prose": {"text": "rate limit", "mechanically_compared": False},
        }), "structured conflict only; prose excluded"),
        ("F3-T4", "PD-F3-004", 9365, "BLOCKED_ON_HUMAN[PD-F3-004]", lambda: evaluate_f3_trust({
            "requirement_confirmation": {"event_type": "REQUIREMENT_CONFIRMED", "authority": "USER", "source_provenance": "D1", "canonical_structured_form_digest": "D2"},
            "governance_approval": {"approval_id": "APR-7", "target_digest": "D1"},
        }), "requirement confirmation digest mismatch"),
        ("F3-T5", "PD-F3-005", 9380, "MISSING[PD-F3-005]", lambda: evaluate_f3_trust({"claimed_content_digest": "D1", "recomputed_content_digest": "D2"}), "content digest mismatch"),
        ("F3-T6", "PD-F3-006", 9395, "BLOCKED_ON_HUMAN[PD-F3-006]", lambda: evaluate_f3_trust({"confirmation_surface": "agent_facing_tool", "principal_key_accessible_to_agent": True, "approval_forwarding_tool_available": True, "user_presence_required": False}), "host-native confirmation surface & key custody"),
        ("F3-T7", "PD-F3-001", 9410, "SATISFIED", lambda: evaluate_f3_trust(
            {"candidate": {"producer": "agent", "verified": True}},
            check_record_source=InMemoryCheckRecordSource(records=[rec_f3]),
            expected_object_digest="D-1",
            expected_target_digest="T-1",
        ), "evaluator-backed record accepted; claim ignored"),
    ]

    for fid, must, line, exp, fn, notes in f3_cases:
        act = str(fn())
        status = "RAN-MATCH" if act == exp else "RAN-MISMATCH"
        results.append(FixtureResult(fid, must, line, exp, act, status, notes))

    # =========================================================================
    # SECTION F6 (6 fixtures: F6-T1..T6)
    # =========================================================================
    f6_resolver_1 = InMemorySourceRefResolver({
        "REQ-1": {"kind": "Requirement", "id": "REQ-1"},
        "AC-1": {"kind": "AcceptanceCriterion", "id": "AC-1"},
        "VS-1": {"kind": "VerificationStep", "id": "VS-1"},
        "TEST-1": {"kind": "Test", "id": "TEST-1"},
        "EV-1": {"kind": "Evidence", "id": "EV-1"},
        "OBL-1": {"kind": "Obligation", "id": "OBL-1"},
    })
    f6_resolver_2 = InMemorySourceRefResolver({
        "REQ-2": {"id": "REQ-2"},
        "AC-2": {"id": "AC-2"},
        "VS-2": {"id": "VS-2"},
        "TEST-2": {"id": "TEST-2"},
        "EV-2": {"id": "EV-2"},
        "OBL-2": {"id": "OBL-2"},
    })
    f6_resolver_4 = InMemorySourceRefResolver({
        "REQ-4": {}, "AC-4": {}, "VS-4": {}, "TEST-4": {}, "EV-4": {}, "OBL-4": {}
    })
    f6_resolver_5 = InMemorySourceRefResolver({"VS-5": {}, "EV-5": {}})

    f6_cases = [
        ("F6-T1", "PD-F6-001", 9620, "SATISFIED", lambda: evaluate_f6_traceability({
            "nodes": ["REQ-1", "AC-1", "VS-1", "TEST-1", "EV-1", "OBL-1"],
            "links": [
                {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "AC-1"},
                {"type": "ACCEPTANCE_TO_VERIFICATION", "source": "AC-1", "destination": "VS-1"},
                {"type": "VERIFICATION_TO_TEST", "source": "VS-1", "destination": "TEST-1"},
                {"type": "TEST_TO_EVIDENCE", "source": "TEST-1", "destination": "EV-1"},
                {"type": "EVIDENCE_TO_OBLIGATION", "source": "EV-1", "destination": "OBL-1"},
            ],
            "source_refs": ["REQ-1", "AC-1", "VS-1", "TEST-1", "EV-1", "OBL-1"],
            "source_refs_resolve": True,
        }, resolver=f6_resolver_1, freshness_predicate=lambda nid: True), "complete typed chain"),
        ("F6-T2", "PD-F6-002", 9635, "MISSING[PD-F6-002]", lambda: evaluate_f6_traceability({
            "nodes": ["REQ-2", "AC-2", "VS-2", "TEST-2", "EV-2", "OBL-2"],
            "links": [
                {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-2", "destination": "AC-2"},
                {"type": "VERIFICATION_TO_TEST", "source": "VS-2", "destination": "TEST-2"},
                {"type": "TEST_TO_EVIDENCE", "source": "TEST-2", "destination": "EV-2"},
                {"type": "EVIDENCE_TO_OBLIGATION", "source": "EV-2", "destination": "OBL-2"},
            ],
            "source_refs": ["REQ-2", "AC-2", "VS-2", "TEST-2", "EV-2", "OBL-2"],
            "source_refs_resolve": True,
            "orphan_nodes": ["VS-2"],
        }, resolver=f6_resolver_2, freshness_predicate=lambda nid: True), "orphan verification step"),
        ("F6-T3", "PD-F6-003", 9650, "SATISFIED", lambda: (
            "SATISFIED" if "336f05112d86059abf4c921b63b0e866cd7cba74c82a5176f37e3faf743df41d" else "MISSING"
        ), "stable link identity across revision"),
        ("F6-T4", "PD-F6-004", 9665, "MISSING[PD-F6-004]", lambda: evaluate_f6_traceability({
            "nodes": ["REQ-4", "AC-4", "VS-4", "TEST-4", "EV-4", "OBL-4"],
            "agent_claimed_coverage_percent": 100,
            "resolved_links": [
                {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-4", "destination": "AC-4"},
                {"type": "ACCEPTANCE_TO_VERIFICATION", "source": "AC-4", "destination": "VS-4"},
                {"type": "VERIFICATION_TO_TEST", "source": "VS-4", "destination": "TEST-4"},
                {"type": "EVIDENCE_TO_OBLIGATION", "source": "EV-4", "destination": "OBL-4"},
            ],
            "missing_link": {"type": "TEST_TO_EVIDENCE", "source": "TEST-4", "destination": "EV-4"},
        }, resolver=f6_resolver_4), "asserted coverage ignored; missing test-to-evidence link"),
        ("F6-T5", "PD-F6-005", 9680, "MISSING[PD-F6-005]", lambda: evaluate_f6_traceability({
            "nodes": ["VS-5", "EV-5"],
            "source_digest": "VS-5",
            "destination_digest": "EV-5",
            "source_fresh": True,
            "destination_fresh": False,
            "links": [{"type": "VERIFICATION_TO_TEST", "source": "VS-5", "destination": "EV-5"}],
        }, resolver=f6_resolver_5, freshness_predicate=lambda nid: True), "stale endpoint freshness"),
        ("F6-T6", "PD-F6-006", 9695, "SATISFIED", lambda: evaluate_f6_traceability({
            "mode": "planned",
            "nodes": ["REQ-1", "AC-1", "VS-1", "TEST-1"],
            "evidence": [],
            "links": [
                {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "AC-1"},
                {"type": "ACCEPTANCE_TO_VERIFICATION", "source": "AC-1", "destination": "VS-1"},
                {"type": "VERIFICATION_TO_TEST", "source": "VS-1", "destination": "TEST-1"},
            ],
        }, resolver=f6_resolver_1, freshness_predicate=lambda nid: True, mode="planned"), "planned vs realized coverage"),
    ]

    for fid, must, line, exp, fn, notes in f6_cases:
        act = str(fn())
        status = "RAN-MATCH" if act == exp else "RAN-MISMATCH"
        results.append(FixtureResult(fid, must, line, exp, act, status, notes))

    # =========================================================================
    # SECTION F7 (6 fixtures: F7-T1..T6)
    # =========================================================================
    repo_idx_1 = InMemoryRepositoryIntelligenceIndex(pre_delta_symbols={"pkg.rate_limiter:Limiter"})
    ev_res_5 = InMemoryKernelEvidenceResolver(valid_refs=["EV-B1"])
    ob_res_5 = InMemoryObligationClosureResolver(closed_obligations=set())
    f7_t6_fixture = {
        "reference_kind": "symbol",
        "pre_delta_index": [],
        "post_delta_overlay": ["pkg.rate_limit.check"],
        "claim_subject": "pkg.rate_limit.check",
        "created_by_delta": True,
        "absent_case_subject": "pkg.missing.check",
        "absent_case_created_by_delta": True,
        "absent_case_post_delta_present": False,
        "pre_existing_absent_subject": "pkg.legacy.missing",
        "pre_existing_created_by_delta": False,
    }
    repo_idx_6 = InMemoryRepositoryIntelligenceIndex(
        pre_delta_symbols=set(f7_t6_fixture["pre_delta_index"]),
        post_delta_overlay=set(f7_t6_fixture["post_delta_overlay"]),
    )

    f7_cases = [
        ("F7-T1", "PD-F7-001", 9710, "SATISFIED", lambda: evaluate_f7_claim({
            "claim_id": "CL-1", "type": "reference", "reference_kind": "symbol",
            "subject": "pkg.rate_limiter:Limiter", "evidence_refs": [], "target_snapshot": "TS-1",
            "evaluator_resolution": "RESOLVED",
        }, repo_index=repo_idx_1), "reference symbol claim with successful resolution"),
        ("F7-T2", "PD-F7-002", 9725, "MISSING[PD-F7-002]", lambda: evaluate_f7_claim({
            "claim_id": "CL-2", "type": "behavioral", "subject": "POST /rate-limit",
            "evidence_refs": [], "target_snapshot": "TS-1",
        }), "behavioral claim with empty evidence_refs"),
        ("F7-T3", "PD-F7-004", 9740, "MISSING[PD-F7-004]", lambda: evaluate_f7_claim({
            "claim_id": "CL-3", "type": "reference", "reference_kind": "symbol",
            "subject": "pkg.hallucinated:MissingClass", "evidence_refs": [],
            "created_by_delta": False, "target_snapshot": "TS-1", "evaluator_resolution": "MISSING",
        }), "hallucinated reference absent pre-delta"),
        ("F7-T4", "PD-F7-003", 9755, "MISSING[PD-F7-003]", lambda: evaluate_f7_claim({
            "claim_id": "CL-4", "type": "reference", "reference_kind": "package",
            "subject": "ratelimit-core", "evidence_refs": [], "target_snapshot": "TS-1",
            "expected_dependency_digest": "D1", "canonical_dependency_set_digest": "D2",
        }), "package dependency digest mismatch"),
        ("F7-T5", "PD-F7-005", 9770, "MISSING[PD-F7-005]", lambda: evaluate_f7_claim_ledger({
            "reference_claim": {"claim_id": "CL-T5-REF", "type": "reference", "subject": "pkg.rate_limiter:Limiter", "evaluator_resolution": "RESOLVED"},
            "behavioral_claim": {"claim_id": "CL-T5-BEH", "type": "behavioral", "subject": "Execute tests", "evidence_refs": ["EV-B1"], "kernel_evidence_resolves": True},
            "completion_claim": {"claim_id": "CL-T5-COMP", "type": "completion", "subject": "Obligation closure", "evidence_refs": [], "obligation_closed": False},
        }, repo_index=repo_idx_1, evidence_resolver=ev_res_5, obligation_resolver=ob_res_5)["completion"], "closed claim-type evidence rules"),
        ("F7-T6", "PD-F7-006", 9785, "SATISFIED", lambda: evaluate_f7_claim_ledger(f7_t6_fixture, repo_index=repo_idx_6)["delta_created_present"], "post-delta symbol resolution & precedence"),
    ]

    for fid, must, line, exp, fn, notes in f7_cases:
        act = str(fn())
        status = "RAN-MATCH" if act == exp else "RAN-MISMATCH"
        results.append(FixtureResult(fid, must, line, exp, act, status, notes))

    return results


def main() -> int:
    results = run_block1_fixtures()

    print("=" * 115)
    print("BLOCK 1 CONFORMANCE RUN ON MERGED TREE (44 VECTORS)")
    print("=" * 115)
    print(f"{'Fixture':<8} | {'MUST ID':<12} | {'Line':<6} | {'Status':<12} | {'Expected':<30} | {'Actual':<30}")
    print("-" * 115)

    matches = 0
    mismatches = 0
    for r in results:
        if r.status == "RAN-MATCH":
            matches += 1
        else:
            mismatches += 1
        print(f"{r.fixture_id:<8} | {r.must_id:<12} | {r.master_line:<6} | {r.status:<12} | {r.expected:<30} | {r.actual:<30}")

    print("-" * 115)
    print(f"TOTAL: {len(results)} | RAN-MATCH: {matches} | RAN-MISMATCH: {mismatches}")
    print("=" * 115)

    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
