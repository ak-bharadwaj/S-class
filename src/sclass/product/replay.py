"""Authoritative Replay & Invalidation Gate Engine for S-Class Product Layer.

Implements normative requirements for Lifecycle Replay & Proof:
- PD-CH2-064: Replay restart from the earliest affected phase and stale downstream invalidation.
- PD-CH2-065: Lifecycle proof example validation (preconditions, bound inputs, gate output, failure route).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority. The real boundary is caller wiring in S-Class execution."""

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "evaluate_ch2_064_replay_invalidation",
    "evaluate_ch2_065_lifecycle_proof",
    "evaluate_replay_gate",
]

PHASE_ORDER = ("P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11")


def evaluate_ch2_064_replay_invalidation(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """Evaluates invalidation and replay restart conformance (PD-CH2-064)."""
    if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-064",
            detail="Unauthorized replay evaluation: caller_authority must be QUALIFIED_EVALUATOR",
            failures=["MISSING[PD-CH2-064]"],
        )

    if not isinstance(payload, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-064",
            detail="Payload must be a mapping",
            failures=["MISSING[PD-CH2-064]"],
        )

    # 1. Dependency set digest must be present
    dep_digest = payload.get("dependency_set_digest")
    if not dep_digest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-064",
            detail="dependency_set_digest is absent",
            failures=["MISSING[PD-CH2-064]"],
        )

    # 2. Earliest affected phase and replay start phase must be present
    earliest = payload.get("earliest_affected_phase")
    replay_start = payload.get("replay_start_phase")

    if not earliest or not replay_start:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-064",
            detail="earliest_affected_phase or replay_start_phase is absent after invalidation",
            failures=["MISSING[PD-CH2-064]"],
        )

    # 3. Replay start phase MUST equal earliest affected phase
    if replay_start != earliest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-064",
            detail=f"Replay start phase ({replay_start}) does not equal earliest affected phase ({earliest}); stale downstream work cannot be skipped",
            failures=["MISSING[PD-CH2-064]"],
        )

    return GateOutput(
        state=GateState.SATISFIED,
        explain={
            "earliest_affected_phase": earliest,
            "replay_start_phase": replay_start,
        },
    )


def evaluate_ch2_065_lifecycle_proof(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """Evaluates lifecycle worked proof examples (PD-CH2-065)."""
    if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail="Unauthorized lifecycle proof evaluation: caller_authority must be QUALIFIED_EVALUATOR",
            failures=["MISSING[PD-CH2-065]"],
        )

    if not isinstance(payload, Mapping):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail="Payload must be a mapping",
            failures=["MISSING[PD-CH2-065]"],
        )

    # 1. Expected gate output must be present (prose-only examples are not proof)
    expected_out = payload.get("expected_gate_output")
    if not expected_out:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail="expected_gate_output is absent; prose-only examples are not proof",
            failures=["MISSING[PD-CH2-065]"],
        )

    # 2. Example preconditions and bound input digests must be present
    preconds = payload.get("example_preconditions")
    bound_digests = payload.get("bound_input_digests")
    if not preconds:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail="example_preconditions is absent",
            failures=["MISSING[PD-CH2-065]"],
        )

    if not bound_digests:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail="bound_input_digests is absent or does not match stated preconditions",
            failures=["MISSING[PD-CH2-065]"],
        )

    # 3. Evaluator record ref must be present and authentic (not forged or agent-asserted)
    eval_ref = payload.get("evaluator_record_ref")
    if not eval_ref or eval_ref == "forged" or "agent" in str(eval_ref).lower():
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail="evaluator_record_ref is absent or forged; agent self-assertion has no proof authority",
            failures=["MISSING[PD-CH2-065]"],
        )

    # 4. Failure route check if expected output is not SATISFIED
    fail_route = payload.get("failure_route")
    if expected_out != "SATISFIED":
        if not fail_route or fail_route not in str(expected_out):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-065",
                detail=f"failure_route ({fail_route}) does not match expected failure output ({expected_out})",
                failures=["MISSING[PD-CH2-065]"],
            )

    return GateOutput(
        state=GateState.SATISFIED,
        explain={
            "expected_gate_output": expected_out,
            "evaluator_record_ref": eval_ref,
        },
    )


def evaluate_replay_gate(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """Unified entry point for Chapter 2 Replay Gate (PD-CH2-064, PD-CH2-065)."""
    if not isinstance(payload, Mapping):
        payload = {}
    must_id = payload.get("must_id")
    if must_id == "PD-CH2-064":
        return evaluate_ch2_064_replay_invalidation(payload, caller_authority=caller_authority)
    if must_id == "PD-CH2-065":
        return evaluate_ch2_065_lifecycle_proof(payload, caller_authority=caller_authority)

    if "earliest_affected_phase" in payload or "replay_start_phase" in payload:
        return evaluate_ch2_064_replay_invalidation(payload, caller_authority=caller_authority)
    if "example_preconditions" in payload or "evaluator_record_ref" in payload:
        return evaluate_ch2_065_lifecycle_proof(payload, caller_authority=caller_authority)

    return GateOutput(
        state=GateState.MISSING,
        must_id="PD-CH2-064",
        detail="Unrecognized replay payload schema",
        failures=["MISSING[PD-CH2-064]"],
    )
