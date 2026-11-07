#!/usr/bin/env python3
"""Permanent Security Probes for Lane B1 F1 Authority Hardening.

Executes all 6 required permanent probes (Probes A through F) plus additional
security attack vectors (whitespace approval, raising procedure, truthy non-True,
agent-authored approval injection, caller authority boundary bypass).
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Tuple

from sclass.product.artifacts import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_f1_representation,
)
from sclass.product.gate import GateOutput, GateState


def run_probe_a() -> Tuple[bool, str]:
    """Probe A: Empty artifact; no injected arguments -> MISSING."""
    out = evaluate_f1_representation({})
    ok = (out.state == GateState.MISSING) and (out.must_id == "PD-F1-003")
    return ok, f"result={out} state={out.state}"


def run_probe_b() -> Tuple[bool, str]:
    """Probe B: Agent PASS; no independent verifier -> MISSING[PD-F1-002]."""
    out = evaluate_f1_representation({"agent_result": "PASS"})
    ok = (out == "MISSING[PD-F1-002]")
    return ok, f"result={out}"


def run_probe_c() -> Tuple[bool, str]:
    """Probe C: Agent PASS plus payload verifier PASS -> MISSING[PD-F1-002]."""
    out = evaluate_f1_representation({
        "agent_result": "PASS",
        "independent_verifier_result": "PASS",
    })
    ok = (out == "MISSING[PD-F1-002]")
    return ok, f"result={out}"


def run_probe_d() -> Tuple[bool, str]:
    """Probe D: Weakening 10->20 plus payload procedure and approval -> BLOCKED_ON_HUMAN[PD-F1-005]."""
    out = evaluate_f1_representation({
        "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
        "proposed": {"predicate": "x LESS_OR_EQUAL 20"},
        "structural_diff_procedure": "numeric_range_diff",
        "authoritative_approval": "DECISION-42",
    })
    ok = (out == "BLOCKED_ON_HUMAN[PD-F1-005]")
    return ok, f"result={out}"


def run_probe_e() -> Tuple[bool, str]:
    """Probe E: Constraint removed plus payload procedure, no injected approval -> BLOCKED_ON_HUMAN[PD-F1-005]."""
    out = evaluate_f1_representation({
        "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
        "proposed": None,
        "structural_diff_procedure": lambda c, p: True,
    })
    ok = (out == "BLOCKED_ON_HUMAN[PD-F1-005]")
    return ok, f"result={out}"


def run_probe_f() -> Tuple[bool, str]:
    """Probe F: Changed constraint, no injected procedure, payload approval -> BLOCKED_ON_HUMAN[PD-F1-005]."""
    out = evaluate_f1_representation({
        "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
        "proposed": {"predicate": "x LESS_OR_EQUAL 20"},
        "authoritative_approval": "DECISION-42",
    })
    ok = (out == "BLOCKED_ON_HUMAN[PD-F1-005]")
    return ok, f"result={out}"


def run_probe_whitespace_approval() -> Tuple[bool, str]:
    """Probe 7: Approval whitespace -> BLOCKED_ON_HUMAN[PD-F1-005]."""
    out = evaluate_f1_representation(
        {"proposed": {"predicate": "x LESS_OR_EQUAL 20"}},
        confirmed_artifact={"predicate": "x LESS_OR_EQUAL 10"},
        structural_diff_procedure=lambda c, p: True,
        authoritative_approval="   \t  ",
    )
    ok = (out == "BLOCKED_ON_HUMAN[PD-F1-005]")
    return ok, f"result={out}"


def run_probe_procedure_raises() -> Tuple[bool, str]:
    """Probe 8: Procedure raises -> BLOCKED_ON_HUMAN[PD-F1-005]."""
    def raising_proc(c: Any, p: Any) -> Any:
        raise RuntimeError("Proc exploded")

    out = evaluate_f1_representation(
        {"proposed": {"predicate": "x LESS_OR_EQUAL 20"}},
        confirmed_artifact={"predicate": "x LESS_OR_EQUAL 10"},
        structural_diff_procedure=raising_proc,
        authoritative_approval="DECISION-42",
    )
    ok = (out == "BLOCKED_ON_HUMAN[PD-F1-005]")
    return ok, f"result={out}"


def run_probe_procedure_truthy_non_true() -> Tuple[bool, str]:
    """Probe 9: Procedure returns truthy non-True -> BLOCKED_ON_HUMAN[PD-F1-005]."""
    out = evaluate_f1_representation(
        {"proposed": {"predicate": "x LESS_OR_EQUAL 20"}},
        confirmed_artifact={"predicate": "x LESS_OR_EQUAL 10"},
        structural_diff_procedure=lambda c, p: 1,
        authoritative_approval="DECISION-42",
    )
    ok = (out == "BLOCKED_ON_HUMAN[PD-F1-005]")
    return ok, f"result={out}"


def run_probe_agent_authored_approval() -> Tuple[bool, str]:
    """Probe 10: Agent-authored approval rejected -> BLOCKED_ON_HUMAN[PD-F1-005]."""
    out = evaluate_f1_representation({
        "proposed": {"predicate": "x LESS_OR_EQUAL 20"},
        "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
        "authoritative_approval": "AGENT-APPROVAL-001",
        "agent_authored": True,
    })
    ok = (out == "BLOCKED_ON_HUMAN[PD-F1-005]")
    return ok, f"result={out}"


def run_probe_injected_authority_succeeds() -> Tuple[bool, str]:
    """Probe 11: Injected authority via kwargs succeeds -> SATISFIED."""
    out = evaluate_f1_representation(
        {"proposed": {"predicate": "x LESS_OR_EQUAL 20"}},
        confirmed_artifact={"predicate": "x LESS_OR_EQUAL 10"},
        structural_diff_procedure=lambda c, p: True,
        authoritative_approval="DECISION-42",
    )
    ok = (out == GateState.SATISFIED)
    return ok, f"result={out}"


def run_probe_payload_fail_makes_stricter() -> Tuple[bool, str]:
    """Probe 12: Payload verifier FAIL makes result stricter -> MISSING[PD-F1-002]."""
    out = evaluate_f1_representation(
        {"agent_result": "PASS", "independent_verifier_result": "FAIL"},
        independent_verifier_result="PASS",
    )
    ok = (out == "MISSING[PD-F1-002]")
    return ok, f"result={out}"


def run_probe_unknown_class() -> Tuple[bool, str]:
    """Probe 13: Unknown artifact class fails closed -> MISSING[PD-F1-003]."""
    out = evaluate_f1_representation({
        "artifact": {"artifact_class": "unknown_class_type"},
    })
    ok = (out == "MISSING[PD-F1-003]")
    return ok, f"result={out}"


def run_probe_caller_authority_closed_set() -> Tuple[bool, str]:
    """Probe 14: Caller authority closed set validation -> reject non-closed-set."""
    out_valid = evaluate_f1_representation(
        {"artifact": {"artifact_class": "code", "prose": "valid"}},
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    out_invalid = evaluate_f1_representation(
        {"artifact": {"artifact_class": "code", "prose": "invalid"}},
        caller_authority="AGENT",
    )
    ok = (out_valid == GateState.SATISFIED) and (out_invalid == "MISSING[PD-F1-001]")
    return ok, f"valid={out_valid} invalid={out_invalid}"


PROBES = [
    ("Probe A (Empty artifact)", run_probe_a),
    ("Probe B (Agent PASS no verifier)", run_probe_b),
    ("Probe C (Payload verifier PASS attack)", run_probe_c),
    ("Probe D (Weakening payload proc+approval attack)", run_probe_d),
    ("Probe E (Constraint removed no injected approval)", run_probe_e),
    ("Probe F (Changed constraint no procedure)", run_probe_f),
    ("Probe 7 (Approval whitespace only)", run_probe_whitespace_approval),
    ("Probe 8 (Procedure raises exception)", run_probe_procedure_raises),
    ("Probe 9 (Procedure returns truthy non-True)", run_probe_procedure_truthy_non_true),
    ("Probe 10 (Agent-authored approval rejected)", run_probe_agent_authored_approval),
    ("Probe 11 (Injected authority succeeds)", run_probe_injected_authority_succeeds),
    ("Probe 12 (Payload verifier FAIL makes stricter)", run_probe_payload_fail_makes_stricter),
    ("Probe 13 (Unknown artifact class fails closed)", run_probe_unknown_class),
    ("Probe 14 (Caller authority closed-set enforcement)", run_probe_caller_authority_closed_set),
]


def main() -> int:
    print(f"Executing {len(PROBES)} security probes against evaluate_f1_representation...")
    failures = 0
    for name, func in PROBES:
        try:
            ok, msg = func()
            status = "PASS" if ok else "FAIL"
            if not ok:
                failures += 1
            print(f"[{status}] {name}: {msg}")
        except Exception as e:
            failures += 1
            print(f"[FAIL] {name}: raised exception: {e}")

    print(f"\nTotal: {len(PROBES)}, Passed: {len(PROBES) - failures}, Failed: {failures}")
    return 1 if failures > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
