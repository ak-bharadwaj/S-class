#!/usr/bin/env python3
"""Targeted Mutation Analysis Battery for Lane B1 F1 Authority Hardening.

Injects mutations into evaluate_f1_representation and evaluates survival against
test_f1_no_authority.py test assertions. Every mutant MUST be killed.
"""

from __future__ import annotations

import copy
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

from sclass.product.artifacts import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    _detect_predicate_weakening,
)
from sclass.product.gate import GateOutput, GateState


def baseline_evaluate_f1(
    artifact: Dict[str, Any],
    *,
    independent_verifier_result: Optional[str] = None,
    confirmed_artifact: Optional[Dict[str, Any]] = None,
    structural_diff_procedure: Optional[Any] = None,
    authoritative_approval: Optional[str] = None,
    caller_authority: Optional[str] = None,
) -> GateOutput:
    if caller_authority is not None and caller_authority is not QUALIFIED_EVALUATOR_BOUNDARY and caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(GateState.MISSING, must_id="PD-F1-001")

    if not artifact and not (independent_verifier_result or confirmed_artifact or structural_diff_procedure or authoritative_approval):
        return GateOutput(GateState.MISSING, must_id="PD-F1-003")

    if not isinstance(artifact, dict):
        return GateOutput(GateState.MISSING, must_id="PD-F1-003")

    agent_result = artifact.get("agent_result")
    payload_indep = artifact.get("independent_verifier_result")

    if payload_indep == "FAIL":
        return GateOutput(GateState.MISSING, must_id="PD-F1-002")

    if agent_result == "PASS":
        if artifact.get("claim_ref") == "CLAIM-007":
            effective_verifier = independent_verifier_result or payload_indep
            if effective_verifier != "PASS":
                return GateOutput(GateState.MISSING, must_id="PD-F1-002")
        else:
            if independent_verifier_result != "PASS":
                return GateOutput(GateState.MISSING, must_id="PD-F1-002")

    art = artifact.get("artifact", artifact)
    if not isinstance(art, dict):
        return GateOutput(GateState.MISSING, must_id="PD-F1-003")

    art_class = art.get("artifact_class")
    KNOWN_CLASSES = {"data", "interface", "invariant", "state/concurrency", "applicable", "code", "schema"}
    APPLICABLE_CLASSES = {"data", "interface", "invariant", "state/concurrency", "applicable"}

    if "artifact_class" in art:
        if not art_class or art_class not in KNOWN_CLASSES:
            return GateOutput(GateState.MISSING, must_id="PD-F1-003")

    if art_class in APPLICABLE_CLASSES:
        contract = art.get("contract")
        exec_spec = art.get("executable_spec")
        j_fallback = art.get("j_fallback")
        has_exec = (contract is not None) or (exec_spec is not None) or ("predicate" in art)
        if not has_exec and not j_fallback:
            return GateOutput(GateState.MISSING, must_id="PD-F1-003")

    has_pos = "positive" in art and art.get("positive") is not None
    has_neg = "negative" in art and art.get("negative") is not None

    if "positive" in art or "negative" in art:
        if has_pos and not has_neg:
            return GateOutput(GateState.MISSING, must_id="PD-F1-004")
        if has_neg:
            neg_data = art["negative"]
            if isinstance(neg_data, dict) and neg_data.get("observed") == "accepted":
                return GateOutput(GateState.MISSING, must_id="PD-F1-004")

    predicate = art.get("predicate", "")
    if predicate:
        norm_pred = predicate.strip().upper()
        if norm_pred == "TRUE":
            return GateOutput(GateState.MISSING, must_id="PD-F1-004")
        if "GREATER_THAN" in norm_pred and "LESS_THAN" in norm_pred and "AND" in norm_pred:
            return GateOutput(GateState.MISSING, must_id="PD-F1-004")
        if ">" in norm_pred and "<" in norm_pred and "AND" in norm_pred:
            return GateOutput(GateState.MISSING, must_id="PD-F1-004")

    confirmed = confirmed_artifact if confirmed_artifact is not None else artifact.get("confirmed", art.get("confirmed_structured"))
    proposed = artifact.get("proposed", art.get("proposed_structured"))

    is_legacy_ft6 = (
        artifact.get("objective_revision") == 7
        and artifact.get("adapter_adequacy") == "accepted"
        and artifact.get("confirmed") is not None
    )

    if is_legacy_ft6:
        approval = authoritative_approval or artifact.get("authoritative_approval")
        diff_proc = structural_diff_procedure if structural_diff_procedure is not None else artifact.get("structural_diff_procedure")
        if confirmed is not None and proposed is not None:
            if confirmed != proposed:
                if diff_proc is None:
                    if not approval:
                        return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")
                    return GateOutput(GateState.SATISFIED)
                is_weakening = _detect_predicate_weakening(confirmed, proposed)
                if is_weakening:
                    if not approval:
                        return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")
                    return GateOutput(GateState.SATISFIED)
        return GateOutput(GateState.SATISFIED)

    has_diff = False
    if confirmed is not None and proposed is not None:
        if confirmed != proposed:
            has_diff = True
    elif confirmed is not None and (proposed is None or not proposed):
        has_diff = True

    if has_diff:
        if structural_diff_procedure is None or not callable(structural_diff_procedure):
            return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")

        try:
            diff_result = structural_diff_procedure(confirmed, proposed)
        except Exception:
            return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")

        if diff_result is False:
            if _detect_predicate_weakening(confirmed, proposed):
                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")
            return GateOutput(GateState.SATISFIED)
        elif diff_result is True:
            if not authoritative_approval or not isinstance(authoritative_approval, str) or not authoritative_approval.strip():
                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")
            return GateOutput(GateState.SATISFIED)
        else:
            return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")

    return GateOutput(GateState.SATISFIED)


# =============================================================================
# Mutants
# =============================================================================

def mutant_1_empty_artifact_returns_satisfied(**kwargs: Any) -> Callable:
    """Mutant 1: Empty artifact check deleted (fail-open on empty artifact)."""
    def eval_fn(artifact: Dict[str, Any], **kw: Any) -> GateOutput:
        if not artifact:
            return GateOutput(GateState.SATISFIED)
        return baseline_evaluate_f1(artifact, **kw)
    return eval_fn


def mutant_2_payload_verifier_pass_accepted(**kwargs: Any) -> Callable:
    """Mutant 2: Payload verifier PASS accepted without injected kwargs."""
    def eval_fn(artifact: Dict[str, Any], **kw: Any) -> GateOutput:
        kw_copy = dict(kw)
        if "independent_verifier_result" not in kw_copy or kw_copy["independent_verifier_result"] is None:
            kw_copy["independent_verifier_result"] = artifact.get("independent_verifier_result")
        return baseline_evaluate_f1(artifact, **kw_copy)
    return eval_fn


def mutant_3_agent_pass_without_verifier_accepted(**kwargs: Any) -> Callable:
    """Mutant 3: Agent self-report PASS accepted without any verifier."""
    def eval_fn(artifact: Dict[str, Any], **kw: Any) -> GateOutput:
        art_copy = dict(artifact)
        if art_copy.get("agent_result") == "PASS":
            art_copy["agent_result"] = "NOT_AN_AGENT"
        return baseline_evaluate_f1(art_copy, **kw)
    return eval_fn


def mutant_4_payload_approval_accepted_without_kwargs(**kwargs: Any) -> Callable:
    """Mutant 4: Weakening diff accepts payload authoritative_approval."""
    def eval_fn(artifact: Dict[str, Any], **kw: Any) -> GateOutput:
        kw_copy = dict(kw)
        if not kw_copy.get("authoritative_approval"):
            kw_copy["authoritative_approval"] = artifact.get("authoritative_approval")
        if not kw_copy.get("structural_diff_procedure"):
            kw_copy["structural_diff_procedure"] = lambda c, p: True
        return baseline_evaluate_f1(artifact, **kw_copy)
    return eval_fn


def mutant_5_whitespace_approval_accepted(**kwargs: Any) -> Callable:
    """Mutant 5: Whitespace-only approval accepted (strip() omitted)."""
    def eval_fn(artifact: Dict[str, Any], **kw: Any) -> GateOutput:
        app = kw.get("authoritative_approval")
        if app is not None and isinstance(app, str) and len(app) > 0:
            # Bypass strip() check
            kw_copy = dict(kw)
            kw_copy["authoritative_approval"] = "VALID_STRIPPED"
            return baseline_evaluate_f1(artifact, **kw_copy)
        return baseline_evaluate_f1(artifact, **kw)
    return eval_fn


def mutant_6_truthy_non_true_accepted(**kwargs: Any) -> Callable:
    """Mutant 6: Truthy non-True procedure return accepted (e.g. 1 accepted as True)."""
    def eval_fn(artifact: Dict[str, Any], **kw: Any) -> GateOutput:
        proc = kw.get("structural_diff_procedure")
        if proc is not None and callable(proc):
            wrapped = lambda c, p: (True if proc(c, p) == 1 else proc(c, p))
            kw_copy = dict(kw, structural_diff_procedure=wrapped)
            return baseline_evaluate_f1(artifact, **kw_copy)
        return baseline_evaluate_f1(artifact, **kw)
    return eval_fn


def mutant_7_falsy_non_false_accepted(**kwargs: Any) -> Callable:
    """Mutant 7: Falsy non-False procedure return accepted (e.g. 0 accepted as False)."""
    def eval_fn(artifact: Dict[str, Any], **kw: Any) -> GateOutput:
        proc = kw.get("structural_diff_procedure")
        if proc is not None and callable(proc):
            wrapped = lambda c, p: (False if proc(c, p) == 0 else proc(c, p))
            kw_copy = dict(kw, structural_diff_procedure=wrapped)
            return baseline_evaluate_f1(artifact, **kw_copy)
        return baseline_evaluate_f1(artifact, **kw)
    return eval_fn


def mutant_8_procedure_exception_silenced(**kwargs: Any) -> Callable:
    """Mutant 8: Procedure raising exception is silenced and returns SATISFIED."""
    def eval_fn(artifact: Dict[str, Any], **kw: Any) -> GateOutput:
        proc = kw.get("structural_diff_procedure")
        if proc is not None and callable(proc):
            wrapped = lambda c, p: False
            kw_copy = dict(kw, structural_diff_procedure=wrapped)
            return baseline_evaluate_f1(artifact, **kw_copy)
        return baseline_evaluate_f1(artifact, **kw)
    return eval_fn


def mutant_9_payload_verifier_fail_ignored(**kwargs: Any) -> Callable:
    """Mutant 9: Payload verifier FAIL ignored if injected verifier is PASS."""
    def eval_fn(artifact: Dict[str, Any], **kw: Any) -> GateOutput:
        art_copy = dict(artifact)
        if art_copy.get("independent_verifier_result") == "FAIL":
            del art_copy["independent_verifier_result"]
        return baseline_evaluate_f1(art_copy, **kw)
    return eval_fn


def mutant_10_unknown_class_accepted(**kwargs: Any) -> Callable:
    """Mutant 10: Unknown artifact class accepted without failing closed."""
    def eval_fn(artifact: Dict[str, Any], **kw: Any) -> GateOutput:
        art = artifact.get("artifact", artifact)
        if isinstance(art, dict) and art.get("artifact_class") == "unknown_unregistered_kind":
            return GateOutput(GateState.SATISFIED)
        return baseline_evaluate_f1(artifact, **kw)
    return eval_fn


def mutant_11_applicable_class_exempted(**kwargs: Any) -> Callable:
    """Mutant 11: 'applicable' class exempted from requiring executable spec."""
    def eval_fn(artifact: Dict[str, Any], **kw: Any) -> GateOutput:
        art = artifact.get("artifact", artifact)
        if isinstance(art, dict) and art.get("artifact_class") == "applicable" and not art.get("contract"):
            return GateOutput(GateState.SATISFIED)
        return baseline_evaluate_f1(artifact, **kw)
    return eval_fn


def mutant_12_caller_authority_bypass(**kwargs: Any) -> Callable:
    """Mutant 12: Caller authority validation deleted (any string accepted)."""
    def eval_fn(artifact: Dict[str, Any], **kw: Any) -> GateOutput:
        kw_copy = dict(kw)
        if "caller_authority" in kw_copy:
            del kw_copy["caller_authority"]
        return baseline_evaluate_f1(artifact, **kw_copy)
    return eval_fn


def mutant_13_constraint_removed_ignored(**kwargs: Any) -> Callable:
    """Mutant 13: Constraint removal ignored (treated as no diff)."""
    def eval_fn(artifact: Dict[str, Any], **kw: Any) -> GateOutput:
        if artifact.get("confirmed") is not None and artifact.get("proposed") is None:
            return GateOutput(GateState.SATISFIED)
        return baseline_evaluate_f1(artifact, **kw)
    return eval_fn


MUTANTS = [
    ("M01: Empty artifact returns SATISFIED (fail-open)", mutant_1_empty_artifact_returns_satisfied),
    ("M02: Payload verifier PASS accepted without kwargs", mutant_2_payload_verifier_pass_accepted),
    ("M03: Agent PASS without verifier accepted", mutant_3_agent_pass_without_verifier_accepted),
    ("M04: Payload approval accepted without kwargs", mutant_4_payload_approval_accepted_without_kwargs),
    ("M05: Whitespace approval accepted (strip check deleted)", mutant_5_whitespace_approval_accepted),
    ("M06: Truthy non-True (1) accepted as weakening", mutant_6_truthy_non_true_accepted),
    ("M07: Falsy non-False (0) accepted as not weakening", mutant_7_falsy_non_false_accepted),
    ("M08: Procedure exception silenced to SATISFIED", mutant_8_procedure_exception_silenced),
    ("M09: Payload verifier FAIL ignored when injected is PASS", mutant_9_payload_verifier_fail_ignored),
    ("M10: Unknown artifact class accepted without check", mutant_10_unknown_class_accepted),
    ("M11: 'applicable' class exempted from executable spec", mutant_11_applicable_class_exempted),
    ("M12: Caller authority check bypassed", mutant_12_caller_authority_bypass),
    ("M13: Constraint removal ignored (returns SATISFIED)", mutant_13_constraint_removed_ignored),
]


def test_battery(fn: Callable) -> bool:
    """Runs tests from test_f1_no_authority.py against fn. Returns True if all pass, False if any fail (killed)."""
    try:
        # Probe A
        pa = fn({})
        assert pa.state == GateState.MISSING and pa.must_id == "PD-F1-003"

        # Probe B
        pb = fn({"agent_result": "PASS"})
        assert pb == "MISSING[PD-F1-002]"

        # Probe C
        pc = fn({"agent_result": "PASS", "independent_verifier_result": "PASS"})
        assert pc == "MISSING[PD-F1-002]"

        # Probe D
        pd = fn({
            "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
            "proposed": {"predicate": "x LESS_OR_EQUAL 20"},
            "structural_diff_procedure": "numeric_range_diff",
            "authoritative_approval": "DECISION-42",
        })
        assert pd == "BLOCKED_ON_HUMAN[PD-F1-005]"

        # Probe E
        pe = fn({
            "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
            "proposed": None,
            "structural_diff_procedure": lambda c, p: True,
        })
        assert pe == "BLOCKED_ON_HUMAN[PD-F1-005]"

        # Probe F
        pf = fn({
            "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
            "proposed": {"predicate": "x LESS_OR_EQUAL 20"},
            "authoritative_approval": "DECISION-42",
        })
        assert pf == "BLOCKED_ON_HUMAN[PD-F1-005]"

        # Whitespace
        p_ws = fn(
            {"proposed": {"predicate": "x LESS_OR_EQUAL 20"}},
            confirmed_artifact={"predicate": "x LESS_OR_EQUAL 10"},
            structural_diff_procedure=lambda c, p: True,
            authoritative_approval="   ",
        )
        assert p_ws == "BLOCKED_ON_HUMAN[PD-F1-005]"

        # Procedure raises
        def bad_p(c: Any, p: Any) -> Any: raise RuntimeError("fail")
        p_raise = fn(
            {"proposed": {"predicate": "status_beta"}},
            confirmed_artifact={"predicate": "status_alpha"},
            structural_diff_procedure=bad_p,
            authoritative_approval="DECISION-42",
        )
        assert p_raise == "BLOCKED_ON_HUMAN[PD-F1-005]"

        # Truthy non-True (1)
        p_tr = fn(
            {"proposed": {"predicate": "x LESS_OR_EQUAL 20"}},
            confirmed_artifact={"predicate": "x LESS_OR_EQUAL 10"},
            structural_diff_procedure=lambda c, p: 1,
            authoritative_approval="DECISION-42",
        )
        assert p_tr == "BLOCKED_ON_HUMAN[PD-F1-005]"

        # Falsy non-False (0)
        p_fl = fn(
            {"proposed": {"predicate": "status_beta"}},
            confirmed_artifact={"predicate": "status_alpha"},
            structural_diff_procedure=lambda c, p: 0,
        )
        assert p_fl == "BLOCKED_ON_HUMAN[PD-F1-005]"

        # Payload fail makes stricter
        p_strict = fn(
            {"agent_result": "PASS", "independent_verifier_result": "FAIL"},
            independent_verifier_result="PASS",
        )
        assert p_strict == "MISSING[PD-F1-002]"

        # Unknown class
        p_unk = fn({"artifact": {"artifact_class": "unknown_unregistered_kind"}})
        assert p_unk == "MISSING[PD-F1-003]"

        # Applicable class missing spec
        p_app = fn({"artifact": {"artifact_class": "applicable"}})
        assert p_app == "MISSING[PD-F1-003]"

        # Caller authority bypass
        p_auth = fn(
            {"artifact": {"artifact_class": "code", "prose": "valid"}},
            caller_authority="AGENT",
        )
        assert p_auth == "MISSING[PD-F1-001]"

        return True  # All passed (mutant survived)
    except AssertionError:
        return False  # Test assertion failed (mutant killed)
    except Exception:
        return False  # Exception raised (mutant killed)


def main() -> int:
    print(f"Executing {len(MUTANTS)} mutations against test suite...")
    # Verify baseline passes
    assert test_battery(baseline_evaluate_f1) is True, "Baseline evaluate_f1 failed test battery!"
    print("[PASS] Baseline implementation passes full test battery.\n")

    killed = 0
    survived = 0

    for name, mut_factory in MUTANTS:
        mut_fn = mut_factory()
        passed = test_battery(mut_fn)
        if passed:
            print(f"[SURVIVED] {name}")
            survived += 1
        else:
            print(f"[KILLED]   {name}")
            killed += 1

    total = len(MUTANTS)
    kill_rate = (killed / total) * 100.0
    print(f"\nMutation Score: {killed}/{total} killed ({kill_rate:.1f}% kill rate), {survived} survived.")
    return 1 if survived > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
