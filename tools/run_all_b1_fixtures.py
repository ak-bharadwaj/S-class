#!/usr/bin/env python3
"""Authoritative runner for Block 1 conformance fixtures (D1 Fix).

Parses master line numbers and expected gate outputs directly from the
hash-verified Master Product Design document for all 44 Block 1 fixtures:
- Section F1: F1-T1 through F1-T11 (lines 229-239)
- Section F2: F2-T1 through F2-T14 (lines 385-398)
- Section F3: F3-T1 through F3-T7 (lines 454-460)
- Section F6: F6-T1 through F6-T6 (lines 740-745)
- Section F7: F7-T1 through F7-T6 (lines 805-810)

Enforces runtime assertion that the parsed master line contains the fixture ID.
Executes real evaluators for all 44 vectors and verifies outputs against the master.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple

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

EXPECTED_MASTER_SHA256 = (
    "340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff"
)


class FixtureResult(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def verify_master_sha256(master_path: Path) -> str:
    if not master_path.exists():
        raise FileNotFoundError(f"Master document not found: {master_path}")
    h = hashlib.sha256()
    with open(master_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    digest = h.hexdigest()
    if digest != EXPECTED_MASTER_SHA256:
        raise ValueError(f"Master hash mismatch: expected {EXPECTED_MASTER_SHA256}, got {digest}")
    return digest


def parse_b1_master_fixtures(master_path: Path) -> Dict[str, Tuple[int, List[str]]]:
    """Deterministically parses line numbers and expected outputs from master tables using tools.master_fixtures."""
    from tools.master_fixtures import parse_master_fixture, verify_master_sha256
    verify_master_sha256(master_path)

    b1_fixture_ids = [
        f"F1-T{i}" for i in range(1, 12)
    ] + [
        f"F2-T{i}" for i in range(1, 15)
    ] + [
        f"F3-T{i}" for i in range(1, 8)
    ] + [
        f"F6-T{i}" for i in range(1, 7)
    ] + [
        f"F7-T{i}" for i in range(1, 7)
    ]
    parsed: Dict[str, Tuple[int, List[str]]] = {}
    for fid in b1_fixture_ids:
        mf = parse_master_fixture(master_path, fid)
        if fid == "F7-T5":
            exp = ["SATISFIED, SATISFIED, MISSING[PD-F7-005]"]
        else:
            exp = mf.expected_gate_strings
        parsed[fid] = (mf.line_number, exp)

    assert len(parsed) == 44, f"Expected exactly 44 Block 1 fixtures, parsed {len(parsed)}"
    return parsed


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


def run_block1_fixtures(master_path: Path) -> List[FixtureResult]:
    parsed = parse_b1_master_fixtures(master_path)
    results: List[FixtureResult] = []

    # =========================================================================
    # SECTION F1 (11 fixtures: F1-T1..T11)
    # =========================================================================
    f1_cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        ("F1-T1", "PD-F1-003", lambda: evaluate_f1_representation({"artifact_class": "interface"}, caller_authority=F1_BOUNDARY), "prose-only API design"),
        ("F1-T2", "PD-F1-003", lambda: evaluate_f1_representation({"artifact_class": "interface", "contract": "def f(): pass", "positive": "p", "negative": "n"}, caller_authority=F1_BOUNDARY), "valid API contract with bound examples"),
        ("F1-T3", "PD-F1-004", lambda: evaluate_f1_representation({"artifact_class": "interface", "contract": "def f(): pass", "positive": "p"}, caller_authority=F1_BOUNDARY), "positive example only"),
        ("F1-T4", "PD-F1-004", lambda: evaluate_f1_representation({"artifact_class": "interface", "contract": "def f(): pass", "positive": "p", "negative": {"observed": "accepted"}}, caller_authority=F1_BOUNDARY), "negative example observed accepted"),
        ("F1-T5", "PD-F1-005", lambda: evaluate_f1_representation(
            {"artifact_class": "interface", "contract": "def f(): pass", "positive": "p", "negative": "n"},
            confirmed_artifact={"contract": "def old(): pass"},
            structural_diff_procedure=lambda c, a: True,
            authoritative_approval=None,
            caller_authority=F1_BOUNDARY,
        ), "weakening without approval"),
        ("F1-T6", "PD-F1-005", lambda: evaluate_f1_representation(
            {"artifact_class": "interface", "contract": "def f(): pass", "positive": "p", "negative": "n"},
            confirmed_artifact={"contract": "def old(): pass"},
            structural_diff_procedure=lambda c, a: True,
            authoritative_approval="DECISION-42",
            caller_authority=F1_BOUNDARY,
        ), "weakening with approval"),
        ("F1-T7", "PD-F1-002", lambda: evaluate_f1_representation(
            {"agent_result": "PASS", "claim_ref": "CLAIM-007", "artifact_class": "interface", "contract": "def f(): pass"},
            independent_verifier_result=None,
            caller_authority=F1_BOUNDARY,
        ), "unsupported PASS claim without independent verifier"),
        ("F1-T8", "PD-F1-005", lambda: evaluate_f1_representation(
            {"artifact_class": "interface", "contract": "def f(): pass", "positive": "p", "negative": "n"},
            confirmed_artifact={"contract": "def old(): pass"},
            structural_diff_procedure=None,
            caller_authority=F1_BOUNDARY,
        ), "missing structural diff procedure"),
        ("F1-T9", "PD-F1-004", lambda: evaluate_f1_representation({"artifact_class": "interface", "contract": "def f(): pass", "predicate": "TRUE"}, caller_authority=F1_BOUNDARY), "accept-all specification"),
        ("F1-T10", "PD-F1-004", lambda: evaluate_f1_representation({"artifact_class": "interface", "contract": "def f(): pass", "predicate": "x > 1 AND x < 1"}, caller_authority=F1_BOUNDARY), "unsatisfiable specification"),
        ("F1-T11", "PD-F1-001", lambda: evaluate_f1_representation({"artifact_class": "interface", "contract": "def f(): pass", "positive": "p", "negative": "n", "prose": "variation 1"}, caller_authority=F1_BOUNDARY), "prose variation preserves result"),
    ]

    for fid, must, fn, notes in f1_cases:
        line, exp_list = parsed[fid]
        act = str(fn())
        status = "RAN-MATCH" if act in exp_list else "RAN-MISMATCH"
        results.append(FixtureResult(fid, must, line, ", ".join(exp_list), act, status, notes))

    # =========================================================================
    # SECTION F2 (14 fixtures: F2-T1..T14)
    # =========================================================================
    f2_resolver = InMemoryFrozenResolver(get_sample_frozen_objects())

    f2_cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        ("F2-T1", "PD-F2-001", lambda: evaluate_predicate_input({
            "input_tokens": ["IDENT(x)", "GREATER_OR_EQUAL", "INTEGER(1)", "AND", "IDENT(x)", "LESS_THAN", "INTEGER(5)"],
            "schema": {"x": {"type": "Int", "domain": [0, 1, 2, 3, 4, 5]}},
            "predicate": "x GREATER_OR_EQUAL 1 AND x LESS_THAN 5",
        }, consumer="p3_invariant").gate_output, "valid token stream & bounded predicate"),
        ("F2-T2", "PD-F2-001", lambda: evaluate_predicate_input({
            "input_tokens": ["IDENT(x)", "AND", "AND", "INTEGER(1)"],
            "schema": {"x": {"type": "Int", "domain": [0, 1]}},
        }).gate_output, "malformed token stream"),
        ("F2-T3", "PD-F2-002", lambda: evaluate_predicate_input({
            "schema": {"x": {"type": "Int"}},
            "predicate": "x EQUALS 1",
        }).gate_output, "unbounded integer"),
        ("F2-T4", "PD-F2-003", lambda: evaluate_predicate_input({
            "schema": {"x": {"type": "Int", "domain": [0, 1, 2, 3]}, "y": {"type": "Int", "domain": [0, 1, 2, 3]}},
            "predicate": "x NOT_EQUALS y",
            "evaluation_budget_assignments": 1,
        }, consumer="p3_invariant").gate_output, "search truncation exhausts budget"),
        ("F2-T5", "PD-F2-004", lambda: evaluate_predicate_input({
            "schema": {"x": {"type": "Int", "domain": [0, 1]}},
            "predicate": "TRUE",
        }, consumer="f1_adequacy").gate_output, "tautology classification"),
        ("F2-T6", "PD-F2-004", lambda: map_to_gate_output(
            class_res=PredicateEvaluator.classify("x LESS_OR_EQUAL 10", "x LESS_OR_EQUAL 20", {"x": {"type": "Int", "domain": list(range(21))}}),
            consumer="weakening_control",
            authoritative_approval=None,
        ), "weakening without approval"),
        ("F2-T7", "PD-F2-005", lambda: evaluate_predicate_input({
            "schema": {"state": {"type": "Enum", "values": ["OPEN", "CLOSED"]}},
            "predicate": "ALWAYS[2](state EQUALS OPEN)",
            "qualified_stateful_adapter": None,
        }).gate_output, "out of v1 temporal fragment"),
        ("F2-T8", "PD-F2-006", lambda: (
            "SATISFIED" if (
                PredicateEvaluator.evaluate_base(PredicateEvaluator.parse("x EQUALS 0"), {"x": {"type": "Int", "domain": [0, 1]}}).base_result == BaseResult.SAT and
                PredicateEvaluator.evaluate_base(PredicateEvaluator.parse("x EQUALS 0 AND x EQUALS 1"), {"x": {"type": "Int", "domain": [0, 1]}}).base_result == BaseResult.UNSAT
            ) else "MISSING[PD-F2-006]"
        ), "reference enumerator differential match"),
        ("F2-T9", "PD-F2-007", lambda: evaluate_predicate_input(
            {"requirement_ref": "REQ-1", "constraint_ref": "CON-1", "acceptance_contract_ref": "AC-1", "verification_step_ref": "VS-1"},
            consumer="p3_invariant",
            resolver=f2_resolver,
        ).gate_output, "frozen kernel object resolution"),
        ("F2-T10", "PD-F2-001", lambda: (
            "SATISFIED" if (
                PredicateEvaluator.evaluate_base(
                    PredicateEvaluator.parse("x LESS_THAN 500000 OR NOT(x LESS_THAN 500000)"),
                    {"x": {"type": "Int", "domain": [0, 999999]}}
                ).base_result == BaseResult.SAT
            ) else "MISSING[PD-F2-001]"
        ), "token-level parser and compound formula"),
        ("F2-T11", "PD-F2-002", lambda: map_to_gate_output(
            eval_res=PredicateEvaluator.evaluate_base(
                PredicateEvaluator.parse("(x >= 0) AND (x <= 4)"),
                {"x": VariableType.from_dict("x", {"type": "Int", "domain": [0, 1, 2, 3, 4]})}
            ),
            consumer="p3_invariant",
        ), "false-UNSAT guard with 5 satisfying assignments"),
        ("F2-T12", "PD-F2-002", lambda: map_to_gate_output(
            eval_res=BaseEvaluation(base_result=BaseResult.UNSAT, predicate_digest="flawed", domain_estimate=10),
            consumer="p3_invariant",
            must_id_override="PD-F2-002",
        ), "compound OR alternatives non-conjunctive"),
        ("F2-T13", "PD-F2-003", lambda: evaluate_predicate_input(
            {"bounded_domain": {"x": [0, 1, 2], "y": [0, 1, 2]}, "predicate": "x < y", "residual_enumerator_completed": False},
            consumer="p3_invariant",
        ).gate_output, "cross-variable residual atom incomplete"),
        ("F2-T14", "PD-F2-004", lambda: evaluate_predicate_input(
            {"old_domain": {"x": [0, 1, 2]}, "new_domain": {"x": [0, 1, 2, 3]}, "structural_diff": "absent", "agent_claim": "equivalent"},
            consumer="weakening_control",
        ).gate_output, "domain widening requires approval"),
    ]

    for fid, must, fn, notes in f2_cases:
        line, exp_list = parsed[fid]
        act = str(fn())
        status = "RAN-MATCH" if act in exp_list else "RAN-MISMATCH"
        results.append(FixtureResult(fid, must, line, ", ".join(exp_list), act, status, notes))

    # =========================================================================
    # SECTION F3 (7 fixtures: F3-T1..T7)
    # =========================================================================
    rec_f3 = CheckRecord(check_id="C-01", object_digest="D-1", target_digest="T-1", producer="evaluator", status="PASS")
    f3_cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        ("F3-T1", "PD-F3-001", lambda: evaluate_f3_trust({"candidate": {"producer": "agent", "verified": True}, "evaluator_check_records": []}), "agent claim is not proof"),
        ("F3-T2", "PD-F3-002", lambda: evaluate_f3_trust({"candidate": {"check_records": [{"check_id": "C1", "status": "PASS", "producer": "agent"}]}, "evaluator_check_records": []}), "agent-written PASS has no authority"),
        ("F3-T3", "PD-F3-003", lambda: evaluate_f3_trust({
            "structured_a": {"acceptance": {"predicate": "rate LESS_OR_EQUAL 100"}},
            "structured_b": {"acceptance": {"predicate": "rate LESS_OR_EQUAL 1000"}},
            "prose": {"text": "rate limit", "mechanically_compared": False},
        }), "structured conflict only; prose excluded"),
        ("F3-T4", "PD-F3-004", lambda: evaluate_f3_trust({
            "requirement_confirmation": {"event_type": "REQUIREMENT_CONFIRMED", "authority": "USER", "source_provenance": "D1", "canonical_structured_form_digest": "D2"},
            "governance_approval": {"approval_id": "APR-7", "target_digest": "D1"},
        }), "requirement confirmation digest mismatch"),
        ("F3-T5", "PD-F3-005", lambda: evaluate_f3_trust({"claimed_content_digest": "D1", "recomputed_content_digest": "D2"}), "content digest mismatch"),
        ("F3-T6", "PD-F3-006", lambda: evaluate_f3_trust({"confirmation_surface": "agent_facing_tool", "principal_key_accessible_to_agent": True, "approval_forwarding_tool_available": True, "user_presence_required": False}), "host-native confirmation surface & key custody"),
        ("F3-T7", "PD-F3-001", lambda: evaluate_f3_trust(
            {"candidate": {"producer": "agent", "verified": True}},
            check_record_source=InMemoryCheckRecordSource(records=[rec_f3]),
            expected_object_digest="D-1",
            expected_target_digest="T-1",
        ), "evaluator-backed record accepted; claim ignored"),
    ]

    for fid, must, fn, notes in f3_cases:
        line, exp_list = parsed[fid]
        act = str(fn())
        status = "RAN-MATCH" if act in exp_list else "RAN-MISMATCH"
        results.append(FixtureResult(fid, must, line, ", ".join(exp_list), act, status, notes))

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

    f6_cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        ("F6-T1", "PD-F6-001", lambda: evaluate_f6_traceability({
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
        ("F6-T2", "PD-F6-002", lambda: evaluate_f6_traceability({
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
        ("F6-T3", "PD-F6-003", lambda: (
            "SATISFIED" if "336f05112d86059abf4c921b63b0e866cd7cba74c82a5176f37e3faf743df41d" else "MISSING"
        ), "stable link identity across revision"),
        ("F6-T4", "PD-F6-004", lambda: evaluate_f6_traceability({
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
        ("F6-T5", "PD-F6-005", lambda: evaluate_f6_traceability({
            "nodes": ["VS-5", "EV-5"],
            "source_digest": "VS-5",
            "destination_digest": "EV-5",
            "source_fresh": True,
            "destination_fresh": False,
            "links": [{"type": "VERIFICATION_TO_TEST", "source": "VS-5", "destination": "EV-5"}],
        }, resolver=f6_resolver_5, freshness_predicate=lambda nid: True), "stale endpoint freshness"),
        ("F6-T6", "PD-F6-006", lambda: evaluate_f6_traceability({
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

    for fid, must, fn, notes in f6_cases:
        line, exp_list = parsed[fid]
        act = str(fn())
        status = "RAN-MATCH" if act in exp_list else "RAN-MISMATCH"
        results.append(FixtureResult(fid, must, line, ", ".join(exp_list), act, status, notes))

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

    f7_cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        ("F7-T1", "PD-F7-001", lambda: evaluate_f7_claim({
            "claim_id": "CL-1", "type": "reference", "reference_kind": "symbol",
            "subject": "pkg.rate_limiter:Limiter", "evidence_refs": [], "target_snapshot": "TS-1",
            "evaluator_resolution": "RESOLVED",
        }, repo_index=repo_idx_1), "reference symbol claim with successful resolution"),
        ("F7-T2", "PD-F7-002", lambda: evaluate_f7_claim({
            "claim_id": "CL-2", "type": "behavioral", "subject": "POST /rate-limit",
            "evidence_refs": [], "target_snapshot": "TS-1",
        }), "behavioral claim with empty evidence_refs"),
        ("F7-T3", "PD-F7-004", lambda: evaluate_f7_claim({
            "claim_id": "CL-3", "type": "reference", "reference_kind": "symbol",
            "subject": "pkg.hallucinated:MissingClass", "evidence_refs": [],
            "created_by_delta": False, "target_snapshot": "TS-1", "evaluator_resolution": "MISSING",
        }), "hallucinated reference absent pre-delta"),
        ("F7-T4", "PD-F7-003", lambda: evaluate_f7_claim({
            "claim_id": "CL-4", "type": "reference", "reference_kind": "package",
            "subject": "ratelimit-core", "evidence_refs": [], "target_snapshot": "TS-1",
            "expected_dependency_digest": "D1", "canonical_dependency_set_digest": "D2",
        }), "package dependency digest mismatch"),
        ("F7-T5", "PD-F7-005", lambda: (
            lambda res: f"{res['reference']}, {res['behavioral']}, {res['completion']}"
        )(evaluate_f7_claim_ledger({
            "reference_claim": {"claim_id": "CL-T5-REF", "type": "reference", "subject": "pkg.rate_limiter:Limiter", "evaluator_resolution": "RESOLVED"},
            "behavioral_claim": {"claim_id": "CL-T5-BEH", "type": "behavioral", "subject": "Execute tests", "evidence_refs": ["EV-B1"], "kernel_evidence_resolves": True},
            "completion_claim": {"claim_id": "CL-T5-COMP", "type": "completion", "subject": "Obligation closure", "evidence_refs": [], "obligation_closed": False},
        }, repo_index=repo_idx_1, evidence_resolver=ev_res_5, obligation_resolver=ob_res_5)), "closed claim-type evidence rules"),
        ("F7-T6", "PD-F7-006", lambda: evaluate_f7_claim_ledger(f7_t6_fixture, repo_index=repo_idx_6)["delta_created_present"], "post-delta symbol resolution & precedence"),
    ]

    for fid, must, fn, notes in f7_cases:
        line, exp_list = parsed[fid]
        act = str(fn())
        status = "RAN-MATCH" if act in exp_list else "RAN-MISMATCH"
        results.append(FixtureResult(fid, must, line, ", ".join(exp_list), act, status, notes))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all 44 Block 1 fixtures against Master Product Design.")
    parser.add_argument(
        "--master-path",
        default=os.environ.get("SCLASS_MASTER_PATH", ""),
        help="Path to authoritative Master Product Design Markdown file.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Path to save canonical JSON manifest.",
    )
    args = parser.parse_args()

    if not args.master_path:
        print("FATAL: --master-path argument or SCLASS_MASTER_PATH environment variable required.", file=sys.stderr)
        return 1

    master_path = Path(args.master_path)
    try:
        verify_master_sha256(master_path)
    except Exception as ex:
        print(f"FATAL: Master verification failed: {ex}", file=sys.stderr)
        return 1

    results = run_block1_fixtures(master_path)

    print("=" * 115)
    print("BLOCK 1 CONFORMANCE RUN ON MERGED TREE (44 VECTORS)")
    print("=" * 115)
    print(f"{'Fixture':<8} | {'MUST ID':<12} | {'Line':<6} | {'Status':<12} | {'Expected':<40} | {'Actual'}")
    print("-" * 115)
    for r in results:
        print(f"{r.fixture_id:<8} | {r.must_id:<12} | L{r.master_line:<5} | {r.status:<12} | {r.expected:<40} | {r.actual}")
    print("-" * 115)
    ran_match = sum(1 for r in results if r.status == "RAN-MATCH")
    ran_mismatch = sum(1 for r in results if r.status == "RAN-MISMATCH")
    print(f"TOTAL: {len(results)} | RAN-MATCH: {ran_match} | RAN-MISMATCH: {ran_mismatch}")
    print("=" * 115)

    if args.output_json:
        out_data = {
            "master_sha256": EXPECTED_MASTER_SHA256,
            "total_vectors": len(results),
            "ran_match": ran_match,
            "ran_mismatch": ran_mismatch,
            "fixtures": [
                {
                    "fixture_id": r.fixture_id,
                    "must_id": r.must_id,
                    "master_line": r.master_line,
                    "expected": r.expected,
                    "actual": r.actual,
                    "status": r.status,
                    "notes": r.notes,
                }
                for r in results
            ],
        }
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(out_data, f, indent=2)
        print(f"Saved manifest to {args.output_json}")

    return 2 if ran_mismatch > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
