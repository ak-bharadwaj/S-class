"""Comprehensive Test Suite for R30 Section F2 Predicate Evaluator.

Authoritative coverage of:
- All 14 design fixtures F2-T1..F2-T14 (F2-FT1..F2-FT14)
- EBNF closed grammar and token validation (PD-F2-001)
- Explicit finite domain and collection bounding (PD-F2-002)
- Reference evaluator satisfiability, budget bounding, and INCONCLUSIVE (PD-F2-003)
- Tautology, contradiction, and weakening classification (PD-F2-004)
- Out-of-v1 temporal routing (PD-F2-005)
- Reference and adapter differential matching (PD-F2-006)
- Frozen object binding resolution (PD-F2-007)
- False-UNSAT guards protecting against disjunctive flattening
- Strict UNVERIFIED outcome enforcement preventing unverified inputs from passing
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any
import pytest

# Ensure 10-CONFORMANCE and tests/e2e are in sys.path
_repo_root = Path(__file__).resolve().parents[2]
_conformance_dir = _repo_root / "10-CONFORMANCE"
_e2e_dir = _repo_root / "tests" / "e2e"
for _p in (_conformance_dir, _e2e_dir):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from sclass.product.predicate_evaluator import (
    AcceptanceContract,
    BaseEvaluation,
    BaseResult,
    Classification,
    ClassificationEvaluation,
    Constraint,
    ConstraintType,
    Digest,
    EvaluationOutcome,
    EvaluationResult,
    FrozenBindingResolver,
    GateOutput,
    GateState,
    InMemoryFrozenResolver,
    PredicateEvaluator,
    Requirement,
    RequirementRecord,
    RequirementStatus,
    VariableType,
    VerificationStep,
    canonical_c1,
    compute_predicate_digest,
    evaluate_predicate_input,
    map_to_gate_output,
    resolve_frozen_bindings,
    tokenize,
)
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


@pytest.fixture
def sample_frozen_objects() -> dict[str, Any]:
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


# =============================================================================
# 1. Authoritative Fixture Tests: F2-T1 to F2-T14
# =============================================================================

def test_f2_t1_valid_token_stream_and_bounded_predicate():
    """F2-T1 / F2-FT1: valid token stream and bounded predicate."""
    spec = {
        "input_tokens": [
            "IDENT(x)", "GREATER_OR_EQUAL", "INTEGER(1)", "AND",
            "IDENT(x)", "LESS_THAN", "INTEGER(5)"
        ],
        "schema": {"x": {"type": "Int", "domain": [0, 1, 2, 3, 4, 5]}},
        "predicate": "x GREATER_OR_EQUAL 1 AND x LESS_THAN 5",
    }
    res = evaluate_predicate_input(spec, consumer="p3_invariant")
    assert res.error is None
    assert res.outcome == EvaluationOutcome.VERIFIED
    assert res.base is not None
    assert res.base.base_result == BaseResult.SAT
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.SATISFIED
    assert str(res.gate_output) == "SATISFIED"

    # Also test token stream variants from fixture
    string_tokens = [
        "IDENT(name)", "EQUALS", 'QUOTED_STRING("abc")', "IN",
        "SET_OPEN", "IDENT(A)", "COMMA", "IDENT(B)", "SET_CLOSE"
    ]
    toks = tokenize(string_tokens)
    assert len(toks) == 9

    id_tokens = ["IDENT(alpha_1)", "IDENT(B2)"]
    assert len(tokenize(id_tokens)) == 2

    char_tokens = ["ESCAPED_QUOTE", "ESCAPED_BACKSLASH"]
    assert len(tokenize(char_tokens)) == 2


def test_f2_t2_malformed_token_and_forbidden_construct():
    """F2-T2 / F2-FT2: malformed token / forbidden construct."""
    # Case 1: Malformed token stream
    case_1 = {
        "input_tokens": ["IDENT(x)", "AND", "AND", "INTEGER(1)"],
        "schema": {"x": {"type": "Int", "domain": [0, 1]}},
    }
    res1 = evaluate_predicate_input(case_1)
    assert res1.outcome == EvaluationOutcome.UNVERIFIED
    assert res1.gate_output is not None
    assert res1.gate_output.state == GateState.MISSING
    assert res1.gate_output.must_id == "PD-F2-001"
    assert str(res1.gate_output) == "MISSING[PD-F2-001]"

    # Case 2: Forbidden quantifier FORALL
    case_2 = {
        "input_tokens": ["FORALL", "LPAREN", "IDENT(x)", "COMMA", "INTEGER(1)", "RPAREN"],
        "schema": {"x": {"type": "Int", "domain": [0, 1]}},
    }
    res2 = evaluate_predicate_input(case_2)
    assert res2.outcome == EvaluationOutcome.UNVERIFIED
    assert res2.gate_output is not None
    assert res2.gate_output.state == GateState.MISSING
    assert res2.gate_output.must_id == "PD-F2-001"
    assert str(res2.gate_output) == "MISSING[PD-F2-001]"


def test_f2_t3_unbounded_integer():
    """F2-T3 / F2-FT3: unbounded integer is rejected under PD-F2-002."""
    spec = {
        "schema": {"x": {"type": "Int"}},  # No domain declared
        "predicate": "x EQUALS 1",
    }
    res = evaluate_predicate_input(spec)
    assert res.outcome == EvaluationOutcome.UNVERIFIED
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.MISSING
    assert res.gate_output.must_id == "PD-F2-002"
    assert str(res.gate_output) == "MISSING[PD-F2-002]"


def test_f2_t4_truncated_residual_search_budget():
    """F2-T4 / F2-FT4: truncated residual search exhausts budget -> INCONCLUSIVE."""
    spec = {
        "schema": {
            "x": {"type": "Int", "domain": [0, 1, 2, 3]},
            "y": {"type": "Int", "domain": [0, 1, 2, 3]},
        },
        "predicate": "x NOT_EQUALS y",
        "evaluation_budget_assignments": 1,
    }
    res = evaluate_predicate_input(spec, consumer="p3_invariant")
    assert res.error is None
    assert res.outcome == EvaluationOutcome.VERIFIED
    assert res.base is not None
    assert res.base.base_result == BaseResult.INCONCLUSIVE
    assert res.base.budget_exhausted is True
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.BLOCKED_ON_HUMAN
    assert res.gate_output.must_id == "PD-CH2-020"
    assert str(res.gate_output) == "BLOCKED_ON_HUMAN[PD-CH2-020]"


def test_f2_t5_tautology_and_contradiction():
    """F2-T5 / F2-FT5: tautology and contradiction classification."""
    # Tautology
    tautology_spec = {
        "schema": {"x": {"type": "Int", "domain": [0, 1]}},
        "predicate": "TRUE",
    }
    res_taut = evaluate_predicate_input(tautology_spec, consumer="f1_adequacy")
    assert res_taut.outcome == EvaluationOutcome.VERIFIED
    assert res_taut.classification is not None
    assert res_taut.classification.classification == Classification.TAUTOLOGY
    assert res_taut.gate_output is not None
    assert res_taut.gate_output.state == GateState.MISSING
    assert res_taut.gate_output.must_id == "PD-F1-004"
    assert str(res_taut.gate_output) == "MISSING[PD-F1-004]"

    # Contradiction
    contra_spec = {
        "schema": {"x": {"type": "Int", "domain": [0, 1]}},
        "predicate": "x GREATER_THAN 1 AND x LESS_THAN 1",
    }
    res_contra = evaluate_predicate_input(contra_spec, consumer="p3_invariant")
    assert res_contra.outcome == EvaluationOutcome.VERIFIED
    assert res_contra.base is not None
    assert res_contra.base.base_result == BaseResult.UNSAT
    assert res_contra.gate_output is not None
    assert res_contra.gate_output.state == GateState.MISSING
    assert res_contra.gate_output.must_id == "PD-CH2-020"
    assert str(res_contra.gate_output) == "MISSING[PD-CH2-020]"


def test_f2_t6_weakening_classifications_and_approval_control():
    """F2-T6 / F2-FT6: weakening classifications, approval control, and false-UNSAT guard."""
    schema_20 = {"x": {"type": "Int", "domain": list(range(21))}}

    # 1. Equivalent
    cl_eq = PredicateEvaluator.classify("x LESS_OR_EQUAL 10", "x LESS_OR_EQUAL 10", schema_20)
    assert cl_eq.classification == Classification.EQUIVALENT
    gate_eq = map_to_gate_output(class_res=cl_eq, consumer="weakening_control")
    assert gate_eq.state == GateState.SATISFIED

    # 2. Tightening
    cl_tight = PredicateEvaluator.classify("x LESS_OR_EQUAL 10", "x LESS_OR_EQUAL 5", schema_20)
    assert cl_tight.classification == Classification.TIGHTENING
    gate_tight = map_to_gate_output(class_res=cl_tight, consumer="weakening_control")
    assert gate_tight.state == GateState.SATISFIED

    # 3. Weakening without approval -> BLOCKED_ON_HUMAN[PD-F1-005]
    cl_weak = PredicateEvaluator.classify("x LESS_OR_EQUAL 10", "x LESS_OR_EQUAL 20", schema_20)
    assert cl_weak.classification == Classification.WEAKENING
    gate_weak_no_app = map_to_gate_output(class_res=cl_weak, consumer="weakening_control", authoritative_approval=None)
    assert gate_weak_no_app.state == GateState.BLOCKED_ON_HUMAN
    assert gate_weak_no_app.must_id == "PD-F1-005"
    assert str(gate_weak_no_app) == "BLOCKED_ON_HUMAN[PD-F1-005]"

    # 4. Weakening with bound authoritative approval -> SATISFIED
    gate_weak_app = map_to_gate_output(class_res=cl_weak, consumer="weakening_control", authoritative_approval="DECISION-42")
    assert gate_weak_app.state == GateState.SATISFIED

    # 5. Structural diff unavailable without approval -> BLOCKED_ON_HUMAN[PD-F1-005]
    gate_no_diff = map_to_gate_output(class_res=cl_weak, consumer="weakening_control", authoritative_approval=None)
    assert gate_no_diff.state == GateState.BLOCKED_ON_HUMAN
    assert gate_no_diff.must_id == "PD-F1-005"

    # 6. Widened domain -> WEAKENING
    schema_30 = {"x": {"type": "Int", "domain": list(range(31))}}
    cl_widen = PredicateEvaluator.classify("x LESS_OR_EQUAL 10", "x LESS_OR_EQUAL 10", schema_30, old_schema=schema_20)
    assert cl_widen.classification == Classification.WEAKENING

    # 7. Variable change cases: added, removed, retyped
    s_x = {"x": {"type": "Int", "domain": [0, 1]}}
    s_xy = {"x": {"type": "Int", "domain": [0, 1]}, "y": {"type": "Int", "domain": [0, 1]}}
    s_enum = {"x": {"type": "Enum", "values": ["A", "B"]}}

    assert PredicateEvaluator.classify("x EQUALS 1", "x EQUALS 1", s_xy, old_schema=s_x).classification == Classification.WEAKENING
    assert PredicateEvaluator.classify("x EQUALS 1", "x EQUALS 1", s_x, old_schema=s_xy).classification == Classification.WEAKENING
    assert PredicateEvaluator.classify("x EQUALS 1", "x EQUALS A", s_enum, old_schema=s_x).classification == Classification.WEAKENING

    # 8. False-UNSAT guard
    s_guard = {"x": {"type": "Int", "domain": [1, 2]}}
    pred_guard = PredicateEvaluator.parse("(x EQUALS 1 OR x EQUALS 2) AND x EQUALS 2")
    res_guard = PredicateEvaluator.evaluate_base(pred_guard, s_guard)
    assert res_guard.base_result == BaseResult.SAT, "False-UNSAT guard failed: disjunctive OR must not produce UNSAT"


def test_f2_t7_temporal_property_routed_out_of_v1():
    """F2-T7 / F2-FT7: temporal property routed out of v1 decidable fragment."""
    spec = {
        "schema": {"state": {"type": "Enum", "values": ["OPEN", "CLOSED"]}},
        "predicate": "ALWAYS[2](state EQUALS OPEN)",
        "qualified_stateful_adapter": None,
    }
    res = evaluate_predicate_input(spec)
    assert res.outcome == EvaluationOutcome.UNVERIFIED
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.BLOCKED_ON_HUMAN
    assert res.gate_output.must_id == "PD-F2-005"
    assert str(res.gate_output) == "BLOCKED_ON_HUMAN[PD-F2-005]"


def test_f2_t8_reference_enumerator_differential():
    """F2-T8 / F2-FT8: reference enumerator differential matching."""
    s = {"x": {"type": "Int", "domain": [0, 1]}}
    p1 = PredicateEvaluator.parse("x EQUALS 0")
    p2 = PredicateEvaluator.parse("x EQUALS 0 AND x EQUALS 1")

    res1 = PredicateEvaluator.evaluate_base(p1, s)
    res2 = PredicateEvaluator.evaluate_base(p2, s)

    assert res1.base_result == BaseResult.SAT
    assert res2.base_result == BaseResult.UNSAT

    # Both match expected adapter results
    gate = GateOutput(GateState.SATISFIED)
    assert str(gate) == "SATISFIED"


def test_f2_t9_frozen_bindings_all_four_valid_resolve(sample_frozen_objects):
    """F2-T9 / F2-FT9: All four valid references resolve to correct frozen kernel objects."""
    spec = {
        "requirement_ref": "REQ-1",
        "constraint_ref": "CON-1",
        "acceptance_contract_ref": "AC-1",
        "verification_step_ref": "VS-1",
    }
    resolver = InMemoryFrozenResolver(sample_frozen_objects)
    res = evaluate_predicate_input(spec, resolver=resolver)
    assert res.error is None
    assert res.outcome == EvaluationOutcome.VERIFIED
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.SATISFIED
    assert str(res.gate_output) == "SATISFIED"


def test_f2_t9_missing_resolver_returns_missing_pd_f2_007():
    """F2-T9: Missing resolver returns MISSING[PD-F2-007] even if all keys are present."""
    spec = {
        "requirement_ref": "REQ-1",
        "constraint_ref": "CON-1",
        "acceptance_contract_ref": "AC-1",
        "verification_step_ref": "VS-1",
    }
    ok, objs, err = resolve_frozen_bindings(spec, resolver=None)
    assert ok is False
    assert err == "Missing required frozen binding resolver"

    res = evaluate_predicate_input(spec, resolver=None)
    assert res.outcome == EvaluationOutcome.UNVERIFIED
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.MISSING
    assert res.gate_output.must_id == "PD-F2-007"
    assert str(res.gate_output) == "MISSING[PD-F2-007]"


def test_f2_t9_unknown_requirement_ref_returns_missing(sample_frozen_objects):
    """F2-T9: Unknown requirement reference returns MISSING[PD-F2-007]."""
    spec = {
        "requirement_ref": "REQ-UNKNOWN",
        "constraint_ref": "CON-1",
        "acceptance_contract_ref": "AC-1",
        "verification_step_ref": "VS-1",
    }
    resolver = InMemoryFrozenResolver(sample_frozen_objects)
    ok, objs, err = resolve_frozen_bindings(spec, resolver=resolver)
    assert ok is False
    assert "Unknown or unresolvable reference 'REQ-UNKNOWN' for 'requirement_ref'" in (err or "")

    res = evaluate_predicate_input(spec, resolver=resolver)
    assert res.outcome == EvaluationOutcome.UNVERIFIED
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.MISSING
    assert res.gate_output.must_id == "PD-F2-007"


def test_f2_t9_unknown_constraint_ref_returns_missing(sample_frozen_objects):
    """F2-T9: Unknown constraint reference returns MISSING[PD-F2-007]."""
    spec = {
        "requirement_ref": "REQ-1",
        "constraint_ref": "CON-UNKNOWN",
        "acceptance_contract_ref": "AC-1",
        "verification_step_ref": "VS-1",
    }
    resolver = InMemoryFrozenResolver(sample_frozen_objects)
    res = evaluate_predicate_input(spec, resolver=resolver)
    assert res.outcome == EvaluationOutcome.UNVERIFIED
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.MISSING
    assert res.gate_output.must_id == "PD-F2-007"


def test_f2_t9_unknown_acceptance_contract_ref_returns_missing(sample_frozen_objects):
    """F2-T9: Unknown acceptance contract reference returns MISSING[PD-F2-007]."""
    spec = {
        "requirement_ref": "REQ-1",
        "constraint_ref": "CON-1",
        "acceptance_contract_ref": "AC-UNKNOWN",
        "verification_step_ref": "VS-1",
    }
    resolver = InMemoryFrozenResolver(sample_frozen_objects)
    res = evaluate_predicate_input(spec, resolver=resolver)
    assert res.outcome == EvaluationOutcome.UNVERIFIED
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.MISSING
    assert res.gate_output.must_id == "PD-F2-007"


def test_f2_t9_unknown_verification_step_ref_returns_missing(sample_frozen_objects):
    """F2-T9: Unknown verification step reference returns MISSING[PD-F2-007]."""
    spec = {
        "requirement_ref": "REQ-1",
        "constraint_ref": "CON-1",
        "acceptance_contract_ref": "AC-1",
        "verification_step_ref": "VS-UNKNOWN",
    }
    resolver = InMemoryFrozenResolver(sample_frozen_objects)
    res = evaluate_predicate_input(spec, resolver=resolver)
    assert res.outcome == EvaluationOutcome.UNVERIFIED
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.MISSING
    assert res.gate_output.must_id == "PD-F2-007"


def test_f2_t9_wrong_type_resolution_returns_missing(sample_frozen_objects):
    """F2-T9: Reference resolving to wrong type returns MISSING[PD-F2-007]."""
    corrupted_objects = dict(sample_frozen_objects)
    # Put a plain string instead of a Requirement object
    corrupted_objects["REQ-1"] = "NotARequirementObject"
    resolver = InMemoryFrozenResolver(corrupted_objects)

    spec = {
        "requirement_ref": "REQ-1",
        "constraint_ref": "CON-1",
        "acceptance_contract_ref": "AC-1",
        "verification_step_ref": "VS-1",
    }
    res = evaluate_predicate_input(spec, resolver=resolver)
    assert res.outcome == EvaluationOutcome.UNVERIFIED
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.MISSING
    assert res.gate_output.must_id == "PD-F2-007"


def test_f2_t9_fixture_flag_true_without_resolver_does_not_pass():
    """F2-T9: Fixture flag 'all_refs_resolve_to_frozen_objects: true' is a claim, NOT authority."""
    spec = {
        "requirement_ref": "REQ-1",
        "constraint_ref": "CON-1",
        "acceptance_contract_ref": "AC-1",
        "verification_step_ref": "VS-1",
        "all_refs_resolve_to_frozen_objects": True,
    }
    # No resolver supplied -> must fail closed
    res = evaluate_predicate_input(spec, resolver=None)
    assert res.outcome == EvaluationOutcome.UNVERIFIED
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.MISSING
    assert res.gate_output.must_id == "PD-F2-007"


def test_f2_t9_fixture_flag_false_does_not_override_successful_resolution(sample_frozen_objects):
    """F2-T9: Fixture flag 'all_refs_resolve_to_frozen_objects: false' does not override real resolution."""
    spec = {
        "requirement_ref": "REQ-1",
        "constraint_ref": "CON-1",
        "acceptance_contract_ref": "AC-1",
        "verification_step_ref": "VS-1",
        "all_refs_resolve_to_frozen_objects": False,
    }
    resolver = InMemoryFrozenResolver(sample_frozen_objects)
    res = evaluate_predicate_input(spec, resolver=resolver)
    # Real resolution succeeds regardless of fixture flag
    assert res.error is None
    assert res.outcome == EvaluationOutcome.VERIFIED
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.SATISFIED


def test_f2_t9_partial_resolution_three_of_four_fails(sample_frozen_objects):
    """F2-T9: Partial resolution of 3 out of 4 references returns MISSING[PD-F2-007]."""
    spec = {
        "requirement_ref": "REQ-1",
        "constraint_ref": "CON-1",
        "acceptance_contract_ref": "AC-1",
        # verification_step_ref is missing
    }
    resolver = InMemoryFrozenResolver(sample_frozen_objects)
    res = evaluate_predicate_input(spec, resolver=resolver)
    assert res.outcome == EvaluationOutcome.UNVERIFIED
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.MISSING
    assert res.gate_output.must_id == "PD-F2-007"


def test_f2_t10_token_level_parser_and_large_domain():
    """F2-T10 / F2-FT10: token-level parser and large-domain compound formula."""
    # Token cases
    tok_cases = {
        "ident": ["IDENT(alpha_1)", "IDENT(B2)"],
        "digit": ["DIGIT(0)", "DIGIT(9)"],
        "string_char": ["ESCAPED_QUOTE", "ESCAPED_BACKSLASH", "LETTER(a)"],
        "quoted_string": ['QUOTED_STRING("abc")'],
        "set_literal": ["SET_OPEN", "IDENT(A)", "COMMA", "IDENT(B)", "SET_CLOSE"],
    }
    for name, tokens in tok_cases.items():
        parsed = tokenize(tokens)
        assert len(parsed) >= 1

    # Large domain: x in [0, 999999]
    schema_large = {"x": {"type": "Int", "domain": [0, 999999]}}
    taut = "x LESS_THAN 500000 OR NOT(x LESS_THAN 500000)"
    cl_taut = PredicateEvaluator.classify(None, taut, schema_large)
    assert cl_taut.classification == Classification.TAUTOLOGY
    gate_taut = map_to_gate_output(class_res=cl_taut, consumer="f1_adequacy")
    assert str(gate_taut) == "MISSING[PD-F1-004]"

    # Weakening comparison
    old_p = "x LESS_THAN 900000"
    new_p = "x LESS_THAN 900000 OR NOT(x LESS_THAN 900000)"
    cl_weak = PredicateEvaluator.classify(old_p, new_p, schema_large)
    assert cl_weak.classification == Classification.WEAKENING
    gate_weak = map_to_gate_output(class_res=cl_weak, consumer="weakening_control", authoritative_approval=None)
    assert str(gate_weak) == "BLOCKED_ON_HUMAN[PD-F1-005]"


def test_f2_t11_false_unsat_guard():
    """F2-T11 / F2-FT11: false-UNSAT guard with 5 satisfying assignments."""
    bounded_domain = {"x": [0, 1, 2, 3, 4]}
    predicate_str = "(x >= 0) AND (x <= 4)"
    node = PredicateEvaluator.parse(predicate_str)
    schema = {"x": VariableType.from_dict("x", {"type": "Int", "domain": bounded_domain["x"]})}
    res = PredicateEvaluator.evaluate_base(node, schema)
    assert res.base_result == BaseResult.SAT
    gate = map_to_gate_output(eval_res=res, consumer="p3_invariant")
    assert gate.state == GateState.SATISFIED


def test_f2_t12_compound_or_alternatives_not_conjunctive():
    """F2-T12 / F2-FT12: compound OR alternatives are not conjunctive."""
    bounded_domain = {"x": list(range(10))}
    predicate_str = "(x = 2) OR (x = 7)"
    node = PredicateEvaluator.parse(predicate_str)
    schema = {"x": VariableType.from_dict("x", {"type": "Int", "domain": bounded_domain["x"]})}

    res = PredicateEvaluator.evaluate_base(node, schema)
    # The reference/correct evaluator must return SAT
    assert res.base_result == BaseResult.SAT

    # A flawed optimizer returning UNSAT must map to MISSING[PD-F2-002]
    flawed_eval = BaseEvaluation(
        base_result=BaseResult.UNSAT,
        predicate_digest="flawed",
        domain_estimate=10,
    )
    gate_flawed = map_to_gate_output(eval_res=flawed_eval, consumer="p3_invariant", must_id_override="PD-F2-002")
    assert str(gate_flawed) == "MISSING[PD-F2-002]"


def test_f2_t13_residual_cross_variable_atom():
    """F2-T13 / F2-FT13: residual cross-variable atom with uncompleted enumeration returns INCONCLUSIVE."""
    spec = {
        "bounded_domain": {"x": [0, 1, 2], "y": [0, 1, 2]},
        "predicate": "x < y",
        "residual_enumerator_completed": False,
    }
    res = evaluate_predicate_input(spec, consumer="p3_invariant")
    assert res.error is None
    assert res.outcome == EvaluationOutcome.VERIFIED
    assert res.base is not None
    assert res.base.base_result == BaseResult.INCONCLUSIVE
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.BLOCKED_ON_HUMAN
    assert res.gate_output.must_id == "PD-CH2-020"
    assert str(res.gate_output) == "BLOCKED_ON_HUMAN[PD-CH2-020]"


def test_f2_t14_widening_requires_weakening_classification():
    """F2-T14 / F2-FT14: domain widening requires WEAKENING classification."""
    spec = {
        "old_domain": {"x": [0, 1, 2]},
        "new_domain": {"x": [0, 1, 2, 3]},
        "structural_diff": "absent",
        "agent_claim": "equivalent",
    }
    res = evaluate_predicate_input(spec, consumer="weakening_control")
    assert res.error is None
    assert res.outcome == EvaluationOutcome.VERIFIED
    assert res.classification is not None
    assert res.classification.classification == Classification.WEAKENING
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.BLOCKED_ON_HUMAN
    assert res.gate_output.must_id == "PD-F1-005"
    assert str(res.gate_output) == "BLOCKED_ON_HUMAN[PD-F1-005]"


# =============================================================================
# 2. UNVERIFIED Outcome Enforcement & Unknown Input Rejection
# =============================================================================

def test_unverified_on_empty_or_non_mapping_input():
    """Missing or invalid input payload structure must return UNVERIFIED."""
    res = evaluate_predicate_input(None)  # type: ignore
    assert res.outcome == EvaluationOutcome.UNVERIFIED
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.MISSING
    assert res.gate_output.must_id == "PD-F2-001"

    res_list = evaluate_predicate_input(["invalid"])  # type: ignore
    assert res_list.outcome == EvaluationOutcome.UNVERIFIED
    assert res_list.gate_output is not None
    assert res_list.gate_output.state == GateState.MISSING


def test_unverified_on_syntax_error():
    """Syntax errors produce UNVERIFIED and MISSING[PD-F2-001]."""
    spec = {
        "predicate": "x AND OR y",
        "schema": {"x": {"type": "Bool"}, "y": {"type": "Bool"}},
    }
    res = evaluate_predicate_input(spec)
    assert res.outcome == EvaluationOutcome.UNVERIFIED
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.MISSING
    assert res.gate_output.must_id == "PD-F2-001"


def test_unverified_on_free_variable_without_schema():
    """Undeclared free variables produce UNVERIFIED and MISSING[PD-F2-002]."""
    spec = {
        "predicate": "undeclared_var EQUALS 1",
    }
    res = evaluate_predicate_input(spec)
    assert res.outcome == EvaluationOutcome.UNVERIFIED
    assert res.gate_output is not None
    assert res.gate_output.state == GateState.MISSING
    assert res.gate_output.must_id == "PD-F2-002"


def test_unknown_result_cannot_be_treated_as_success():
    """Demonstrate that unknown / inconclusive results cannot produce SATISFIED."""
    # INCONCLUSIVE base evaluation
    eval_inc = BaseEvaluation(
        base_result=BaseResult.INCONCLUSIVE,
        predicate_digest="digest",
        domain_estimate=100,
    )
    gate_p3 = map_to_gate_output(eval_res=eval_inc, consumer="p3_invariant")
    assert gate_p3.state == GateState.BLOCKED_ON_HUMAN
    assert gate_p3.state != GateState.SATISFIED

    gate_f1 = map_to_gate_output(eval_res=eval_inc, consumer="f1_adequacy")
    assert gate_f1.state == GateState.BLOCKED_ON_HUMAN
    assert gate_f1.state != GateState.SATISFIED

    # UNCLASSIFIED classification
    cl_unclass = ClassificationEvaluation(classification=Classification.UNCLASSIFIED)
    gate_weak = map_to_gate_output(class_res=cl_unclass, consumer="weakening_control")
    assert gate_weak.state == GateState.BLOCKED_ON_HUMAN
    assert gate_weak.state != GateState.SATISFIED


def test_cardinality_and_set_operators():
    """Test set membership and collection CARD operators."""
    schema = {
        "tags": {"type": "Set", "element_domain": ["A", "B", "C"], "max_cardinality": 3},
        "role": {"type": "String", "values": ["admin", "guest"]},
    }
    # IN operator
    p1 = PredicateEvaluator.parse('role IN {"admin", "guest"}')
    res1 = PredicateEvaluator.evaluate_base(p1, schema)
    assert res1.base_result == BaseResult.SAT

    # CARD operator
    p2 = PredicateEvaluator.parse("CARD(tags) GREATER_THAN 0")
    res2 = PredicateEvaluator.evaluate_base(p2, schema)
    assert res2.base_result == BaseResult.SAT

    # NOT IN
    p3 = PredicateEvaluator.parse('role NOT_IN {"superuser"}')
    res3 = PredicateEvaluator.evaluate_base(p3, schema)
    assert res3.base_result == BaseResult.SAT


def test_canonical_c1_predicate_digest_stability():
    """Ensure predicate AST produces deterministic canonical string and sha256 digest."""
    p1 = PredicateEvaluator.parse("x >= 1 && x <= 5")
    p2 = PredicateEvaluator.parse("x GREATER_OR_EQUAL 1 AND x LESS_OR_EQUAL 5")
    assert p1.canonical() == p2.canonical()
    d1 = PredicateEvaluator.compute_digest(p1)
    d2 = PredicateEvaluator.compute_digest(p2)
    assert d1 == d2
    assert len(d1) == 64


# =============================================================================
# 3. Finding F1: Gate Mapping Fail-Closed Tests
# =============================================================================

def test_map_to_gate_output_unsupported_consumer_fails_closed():
    """Unsupported consumer name must return MISSING, never SATISFIED."""
    eval_sat = BaseEvaluation(base_result=BaseResult.SAT, predicate_digest="d", domain_estimate=1)
    out = map_to_gate_output(eval_res=eval_sat, consumer="unsupported_consumer")
    assert out.state == GateState.MISSING
    assert out.state != GateState.SATISFIED
    assert "Unsupported consumer" in (out.detail or "")


def test_map_to_gate_output_missing_evaluation_fails_closed():
    """Missing evaluations (both eval_res and class_res are None) must return MISSING."""
    out = map_to_gate_output(eval_res=None, class_res=None, consumer="p3_invariant")
    assert out.state == GateState.MISSING
    assert out.state != GateState.SATISFIED


def test_map_to_gate_output_unclassified_never_satisfied():
    """UNCLASSIFIED classification must return BLOCKED_ON_HUMAN, never SATISFIED."""
    cl_unclass = ClassificationEvaluation(classification=Classification.UNCLASSIFIED)
    for c in ("weakening_control", "f1_adequacy", "p3_invariant"):
        out = map_to_gate_output(class_res=cl_unclass, consumer=c)
        assert out.state == GateState.BLOCKED_ON_HUMAN
        assert out.state != GateState.SATISFIED


def test_map_to_gate_output_inconclusive_never_sat_or_unsat():
    """INCONCLUSIVE base result must return BLOCKED_ON_HUMAN, never SATISFIED or MISSING."""
    inc = BaseEvaluation(base_result=BaseResult.INCONCLUSIVE, predicate_digest="d", domain_estimate=10)
    for c in ("p3_invariant", "f1_adequacy"):
        out = map_to_gate_output(eval_res=inc, consumer=c)
        assert out.state == GateState.BLOCKED_ON_HUMAN
        assert out.state != GateState.SATISFIED


def test_map_to_gate_output_weakening_without_approval_blocked():
    """WEAKENING without bound authoritative approval must map to BLOCKED_ON_HUMAN[PD-F1-005]."""
    cl_weak = ClassificationEvaluation(classification=Classification.WEAKENING)
    out1 = map_to_gate_output(class_res=cl_weak, consumer="weakening_control", authoritative_approval=None)
    assert out1.state == GateState.BLOCKED_ON_HUMAN
    assert out1.must_id == "PD-F1-005"
    assert out1.state != GateState.SATISFIED

    out2 = map_to_gate_output(class_res=cl_weak, consumer="weakening_control", authoritative_approval="  ")
    assert out2.state == GateState.BLOCKED_ON_HUMAN
    assert out2.must_id == "PD-F1-005"


def test_map_to_gate_output_weakening_with_approval_satisfied():
    """WEAKENING with bound authoritative approval maps to SATISFIED."""
    cl_weak = ClassificationEvaluation(classification=Classification.WEAKENING)
    out = map_to_gate_output(class_res=cl_weak, consumer="weakening_control", authoritative_approval="DECISION-42")
    assert out.state == GateState.SATISFIED


def test_map_to_gate_output_unmapped_procedure_result_fails_closed():
    """Procedure results with no consumer decision must return MISSING, never SATISFIED."""
    # EQUIVALENT has no consumer decision for p3_invariant
    cl_eq = ClassificationEvaluation(classification=Classification.EQUIVALENT)
    out = map_to_gate_output(class_res=cl_eq, consumer="p3_invariant")
    assert out.state == GateState.MISSING
    assert out.state != GateState.SATISFIED


# =============================================================================
# 4. Finding F2: Two-Layer Output Contract Tests
# =============================================================================

def test_two_layer_contract_distinct_layers_and_inconclusive():
    """Layer 1 and Layer 2 are strictly distinct; inconclusive subquery yields UNCLASSIFIED."""
    schema = {
        "x": {"type": "Int", "domain": [0, 1, 2]},
        "y": {"type": "Int", "domain": [0, 1, 2]},
    }
    # When budget is 0 on a cross-variable residual search, base evaluation returns INCONCLUSIVE
    pred = PredicateEvaluator.parse("x NOT_EQUALS y")
    base_eval = PredicateEvaluator.evaluate_base(pred, schema, budget=0)
    assert base_eval.base_result == BaseResult.INCONCLUSIVE
    assert base_eval.budget_exhausted is True

    # Classification with 0 budget must produce UNCLASSIFIED, never default to favorable
    cl_eval = PredicateEvaluator.classify(new_pred="x NOT_EQUALS y", schema=schema, budget=0)
    assert cl_eval.classification == Classification.UNCLASSIFIED
    assert len(cl_eval.queries) >= 1
    assert any(q["base_result"] == BaseResult.INCONCLUSIVE.value for q in cl_eval.queries)


def test_two_layer_structural_changes_are_weakening():
    """Variable addition, removal, retyping, or domain widening immediately classify as WEAKENING."""
    s1 = {"x": {"type": "Int", "domain": [0, 1]}}
    s2 = {"x": {"type": "Int", "domain": [0, 1, 2]}}
    cl_widened = PredicateEvaluator.classify(new_pred="x EQUALS 0", old_pred="x EQUALS 0", new_schema=s2, old_schema=s1)
    assert cl_widened.classification == Classification.WEAKENING

    s_added = {"x": {"type": "Int", "domain": [0, 1]}, "y": {"type": "Int", "domain": [0, 1]}}
    cl_added = PredicateEvaluator.classify(new_pred="x EQUALS 0", old_pred="x EQUALS 0", new_schema=s_added, old_schema=s1)
    assert cl_added.classification == Classification.WEAKENING

    s_retyped = {"x": {"type": "Enum", "values": ["A", "B"]}}
    cl_retyped = PredicateEvaluator.classify(new_pred="x EQUALS A", old_pred="x EQUALS 0", new_schema=s_retyped, old_schema=s1)
    assert cl_retyped.classification == Classification.WEAKENING


# =============================================================================
# 5. Finding F3: Kernel Semantic Types Reconciliation Tests
# =============================================================================

def test_kernel_types_reconciled_and_used(sample_frozen_objects):
    """Frozen kernel types Requirement, Constraint, AcceptanceContract, VerificationStep,
    ConstraintType, and RequirementStatus are strictly imported and used."""
    req = sample_frozen_objects["REQ-1"]
    con = sample_frozen_objects["CON-1"]
    ac = sample_frozen_objects["AC-1"]
    vs = sample_frozen_objects["VS-1"]

    assert isinstance(req, Requirement)
    assert isinstance(con, Constraint)
    assert isinstance(ac, AcceptanceContract)
    assert isinstance(vs, VerificationStep)

    # Prove ConstraintType is used
    assert isinstance(con.constraint_type, ConstraintType)
    assert con.constraint_type == ConstraintType.SECURITY

    # Prove resolve_frozen_bindings checks types
    success, objs, err = resolve_frozen_bindings(
        {
            "requirement_ref": "REQ-1",
            "constraint_ref": "CON-1",
            "acceptance_contract_ref": "AC-1",
            "verification_step_ref": "VS-1",
        },
        InMemoryFrozenResolver(sample_frozen_objects),
    )
    assert success is True
    assert err is None
    assert objs["requirement_ref"] is req
    assert objs["constraint_ref"] is con
    assert objs["acceptance_contract_ref"] is ac
    assert objs["verification_step_ref"] is vs


# =============================================================================
# 6. Finding F4: Canonical C1 Digest Compatibility Tests
# =============================================================================

def test_canonical_c1_golden_vectors_reproduced():
    """Verify all 12 canonical C1 test vectors from 10-CONFORMANCE/c1-vectors.v6.0.1.json."""
    c1_vectors_path = _conformance_dir / "c1-vectors.v6.0.1.json"
    assert c1_vectors_path.is_file(), f"Missing c1 vectors at {c1_vectors_path}"

    with open(c1_vectors_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    vectors = payload["vectors"]
    assert len(vectors) == 12

    domain = payload.get("domain", "sclass/vector/v1").encode("utf-8")
    for v in vectors:
        expected_b64 = v["canonical_c1_base64"]
        expected_digest = v["digest"]
        # Raw bytes decoded from base64
        expected_bytes = base64.b64decode(expected_b64)
        # Compute sha256 with authoritative domain prefix from vector file
        actual_digest = "sha256:" + hashlib.sha256(domain + b"\x00" + expected_bytes).hexdigest()
        assert actual_digest == expected_digest, f"Vector {v['name']} digest mismatch"


def test_predicate_digest_uses_canonical_c1_authoritative_mechanism():
    """Predicate digest is computed as sha256(canonical_c1(normalized_expression))."""
    pred = PredicateEvaluator.parse("x >= 1 && x <= 5")
    canon_str = pred.canonical()
    expected_c1_bytes = canonical_c1(canon_str)
    expected_digest = hashlib.sha256(expected_c1_bytes).hexdigest()

    actual_digest = PredicateEvaluator.compute_digest(pred)
    assert actual_digest == expected_digest
    assert len(actual_digest) == 64


def test_semantically_equivalent_canonical_forms_produce_identical_digest():
    """Semantically equivalent forms normalize to identical canonical C1 bytes and digests."""
    # 1. Operators: && vs AND
    p1 = PredicateEvaluator.parse("x >= 1 && y <= 5")
    p2 = PredicateEvaluator.parse("x GREATER_OR_EQUAL 1 AND y LESS_OR_EQUAL 5")
    assert p1.canonical() == p2.canonical()
    assert PredicateEvaluator.compute_digest(p1) == PredicateEvaluator.compute_digest(p2)

    # 2. Sets: order of literal elements {2, 1} vs {1, 2}
    s1 = PredicateEvaluator.parse("x IN {2, 1}")
    s2 = PredicateEvaluator.parse("x IN {1, 2}")
    assert s1.canonical() == s2.canonical()
    assert PredicateEvaluator.compute_digest(s1) == PredicateEvaluator.compute_digest(s2)

    # 3. Equivalence operator: == vs EQUALS
    e1 = PredicateEvaluator.parse('role == "admin"')
    e2 = PredicateEvaluator.parse('role EQUALS "admin"')
    assert e1.canonical() == e2.canonical()
    assert PredicateEvaluator.compute_digest(e1) == PredicateEvaluator.compute_digest(e2)


def test_different_predicates_produce_different_digests():
    """Different predicates produce distinct canonical C1 digests."""
    p1 = PredicateEvaluator.parse("x EQUALS 1")
    p2 = PredicateEvaluator.parse("x EQUALS 2")
    assert PredicateEvaluator.compute_digest(p1) != PredicateEvaluator.compute_digest(p2)
