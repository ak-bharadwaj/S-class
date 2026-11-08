#!/usr/bin/env python3
"""Authoritative F2 predicate evaluator probe on base commit 10fd034.

Verifies F2 spec behavior and tests/product/test_predicate_evaluator.py:
1. Attempt 1: Structured input_tokens & valid predicate string.
   Shows whether WEAKENING classification can be reached through token input.
2. Attempt 2: F2-T14 domain widening specification.
   Reaches WEAKENING classification with VERIFIED outcome.
3. Evaluates cases (a), (b), (c):
   (a) payload spec['authoritative_approval'] = 'DECISION-42' and no caller argument
   (b) no approval anywhere
   (c) caller-injected approval (prints raw rejection from high-level function)
"""
from __future__ import annotations

import os
import sys
import traceback

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from sclass.product.predicate_evaluator import (
    Classification,
    EvaluationOutcome,
    PredicateEvaluator,
    evaluate_predicate_input,
    map_to_gate_output,
)


def run_probe() -> None:
    print("=" * 60)
    print("F2 PREDICATE EVALUATOR PROBE (Commit 10fd034)")
    print("=" * 60)
    print(f"Interpreter: {sys.version.replace(chr(10), ' ')}")
    print("-" * 60)

    # -------------------------------------------------------------------------
    # Attempt 1: Structured valid input_tokens + predicate
    # -------------------------------------------------------------------------
    print("--- ATTEMPT 1: Valid input_tokens & predicate input ---")
    tokens = [
        "IDENT(x)", "GREATER_OR_EQUAL", "INTEGER(1)", "AND",
        "IDENT(x)", "LESS_OR_EQUAL", "INTEGER(10)",
    ]
    schema = {"x": {"type": "Int", "domain": list(range(21))}}
    pred_str = "x GREATER_OR_EQUAL 1 AND x LESS_OR_EQUAL 10"

    # Case 1a: payload approval, no caller arg
    spec_1a = {
        "input_tokens": tokens,
        "predicate": pred_str,
        "schema": schema,
        "authoritative_approval": "DECISION-42",
    }
    res_1a = evaluate_predicate_input(spec_1a, consumer="weakening_control")
    print(f"Attempt 1 Case (a): outcome={res_1a.outcome} classification={res_1a.classification} gate={res_1a.gate_output}")

    # Case 1b: no approval anywhere
    spec_1b = {
        "input_tokens": tokens,
        "predicate": pred_str,
        "schema": schema,
    }
    res_1b = evaluate_predicate_input(spec_1b, consumer="weakening_control")
    print(f"Attempt 1 Case (b): outcome={res_1b.outcome} classification={res_1b.classification} gate={res_1b.gate_output}")

    # Case 1c: caller-injected approval
    print("Attempt 1 Case (c): caller-injected approval")
    try:
        res_1c = evaluate_predicate_input(spec_1b, consumer="weakening_control", authoritative_approval="DECISION-42")  # type: ignore
        print(f"  Result: outcome={res_1c.outcome} classification={res_1c.classification} gate={res_1c.gate_output}")
    except TypeError as te:
        print(f"  Raw Rejection (TypeError): {te}")

    print("\nAttempt 1 Finding: High-level evaluate_predicate_input with input_tokens/predicate")
    print("does NOT execute PredicateEvaluator.classify (classification is None).")
    print("BaseResult cannot decide weakening_control without classification.\n")

    # -------------------------------------------------------------------------
    # Attempt 2: F2-T14 Domain Widening Specification (test_predicate_evaluator.py L642)
    # -------------------------------------------------------------------------
    print("--- ATTEMPT 2: F2-T14 Domain Widening Specification ---")
    base_widening_spec = {
        "old_domain": {"x": [0, 1]},
        "new_domain": {"x": [0, 1, 2]},
        "structural_diff": "absent",
        "agent_claim": "equivalent",
    }

    # Case 2a: payload spec['authoritative_approval']='DECISION-42' and no caller argument
    spec_2a = dict(base_widening_spec)
    spec_2a["authoritative_approval"] = "DECISION-42"
    res_2a = evaluate_predicate_input(spec_2a, consumer="weakening_control")
    cl_str_2a = res_2a.classification.classification.value if res_2a.classification else "None"
    print(f"Attempt 2 Case (a): outcome={res_2a.outcome.value} classification={cl_str_2a} gate={res_2a.gate_output}")

    # Case 2b: no approval anywhere
    spec_2b = dict(base_widening_spec)
    res_2b = evaluate_predicate_input(spec_2b, consumer="weakening_control")
    cl_str_2b = res_2b.classification.classification.value if res_2b.classification else "None"
    print(f"Attempt 2 Case (b): outcome={res_2b.outcome.value} classification={cl_str_2b} gate={res_2b.gate_output}")

    # Case 2c: caller-injected approval to evaluate_predicate_input
    print("Attempt 2 Case (c): caller-injected approval")
    try:
        res_2c = evaluate_predicate_input(spec_2b, consumer="weakening_control", authoritative_approval="DECISION-42")  # type: ignore
        cl_str_2c = res_2c.classification.classification.value if res_2c.classification else "None"
        print(f"  Result: outcome={res_2c.outcome.value} classification={cl_str_2c} gate={res_2c.gate_output}")
    except TypeError as te:
        print(f"  Raw Rejection (TypeError): {te}")

    # Direct map_to_gate_output demonstration (lower-level API)
    if res_2b.classification:
        direct_gate = map_to_gate_output(
            class_res=res_2b.classification,
            consumer="weakening_control",
            authoritative_approval="DECISION-42",
        )
        print(f"Lower-level map_to_gate_output(authoritative_approval='DECISION-42'): gate={direct_gate}")

    print("=" * 60)


if __name__ == "__main__":
    run_probe()
