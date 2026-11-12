"""Authoritative Replay & Invalidation Gate Engine for S-Class Product Layer.

Implements normative requirements for Lifecycle Replay & Proof:
- PD-CH2-064: Replay restart from the earliest affected phase and stale downstream invalidation.
- PD-CH2-065: Lifecycle proof example validation (preconditions, bound inputs, gate output, failure route).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

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
    record_verifier: Optional[Callable[[str], Optional[Mapping[str, Any]]]] = None,
) -> GateOutput:
    """Evaluates lifecycle worked proof examples (PD-CH2-065)."""
    # 1. Authority validation
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
            detail=f"Payload must be a mapping, got {type(payload).__name__}",
            failures=["MISSING[PD-CH2-065]"],
        )

    # 2. Example preconditions and bound input digests must be present
    preconds = payload.get("example_preconditions")
    bound_digests = payload.get("bound_input_digests")
    if not preconds or not isinstance(preconds, (dict, Mapping, list, tuple)):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail="example_preconditions is absent or malformed",
            failures=["MISSING[PD-CH2-065]"],
        )

    if not bound_digests or not isinstance(bound_digests, (list, tuple)) or not all(isinstance(d, str) and d.strip() for d in bound_digests):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail="bound_input_digests is absent or malformed",
            failures=["MISSING[PD-CH2-065]"],
        )

    # 3. Expected gate output claim must be present (prose-only examples are not proof)
    expected_out = payload.get("expected_gate_output")
    if not expected_out or not isinstance(expected_out, str) or not expected_out.strip():
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail="expected_gate_output is absent; prose-only examples are not proof",
            failures=["MISSING[PD-CH2-065]"],
        )

    # Validate that expected_out conforms to closed vocabulary
    if expected_out != "SATISFIED" and not expected_out.startswith("MISSING") and not expected_out.startswith("BLOCKED_ON_HUMAN"):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail=f"expected_gate_output '{expected_out}' is outside closed gate vocabulary",
            failures=["MISSING[PD-CH2-065]"],
        )

    # 4. Failure route check if expected output is not SATISFIED
    fail_route = payload.get("failure_route")
    if expected_out != "SATISFIED":
        if not fail_route or not isinstance(fail_route, str) or fail_route not in expected_out:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-065",
                detail=f"failure_route ({fail_route}) does not match expected failure output ({expected_out})",
                failures=["MISSING[PD-CH2-065]"],
            )

    # 5. Evaluator record ref must be present, non-forged, non-agent
    eval_ref = payload.get("evaluator_record_ref")
    if not eval_ref or not isinstance(eval_ref, str) or eval_ref == "forged" or "agent" in eval_ref.lower():
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail="evaluator_record_ref is absent or forged; agent self-assertion has no proof authority",
            failures=["MISSING[PD-CH2-065]"],
        )

    # 6. Verify canonical evaluator record using injected authority path
    # Caller-supplied expected_out, eval_ref, and payload records are UNTRUSTED claims; they are NOT proof!
    # A canonical record verified by authority must be provided via the injected record_verifier.
    # Fallback to payload-supplied evaluator_record / authority_verified_record is strictly prohibited (D1).
    if record_verifier is None:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail="Authority-backed record_verifier is required: payload records and caller claims are not proof",
            failures=["MISSING[PD-CH2-065]"],
        )

    try:
        record = record_verifier(eval_ref)
    except Exception as exc:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail=f"Record verifier raised exception: {exc}",
            failures=["MISSING[PD-CH2-065]"],
        )

    if record is None or not isinstance(record, (dict, Mapping)):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail="Missing or unverified canonical evaluator record: verifier returned empty or invalid record",
            failures=["MISSING[PD-CH2-065]"],
        )

    # Validate canonical record integrity: require explicit VERIFIED status from authority.
    # Caller's verified=True field must NOT be treated as authority verification.
    rec_status = record.get("status")
    if rec_status != "VERIFIED":
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail=f"Canonical record has unverified status: {rec_status}",
            failures=["MISSING[PD-CH2-065]"],
        )

    # Record ref in verified record must match claimed eval_ref
    rec_ref = record.get("evaluator_record_ref") or record.get("record_ref") or record.get("ref")
    if rec_ref is not None and rec_ref != eval_ref:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-065",
            detail=f"Record reference mismatch: claimed {eval_ref} vs record {rec_ref}",
            failures=["MISSING[PD-CH2-065]"],
        )

    # Verified output state in canonical record must match expected_out
    rec_out = record.get("gate_output") or record.get("output_state") or record.get("state")
    if rec_out is not None:
        rec_out_str = rec_out.value if hasattr(rec_out, "value") else str(rec_out)
        if rec_out_str != expected_out:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-065",
                detail=f"Verified record output '{rec_out_str}' contradicts claimed expected output '{expected_out}'",
                failures=["MISSING[PD-CH2-065]"],
            )

    return GateOutput(
        state=GateState.SATISFIED,
        explain={
            "expected_gate_output": expected_out,
            "evaluator_record_ref": eval_ref,
            "canonical_record_verified": True,
        },
    )


def evaluate_replay_gate(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
    record_verifier: Optional[Callable[[str], Optional[Mapping[str, Any]]]] = None,
) -> GateOutput:
    """Unified entry point for Chapter 2 Replay Gate (PD-CH2-064, PD-CH2-065)."""
    if not isinstance(payload, Mapping):
        payload = {}
    must_id = payload.get("must_id")
    if must_id == "PD-CH2-064":
        return evaluate_ch2_064_replay_invalidation(payload, caller_authority=caller_authority)
    if must_id == "PD-CH2-065":
        return evaluate_ch2_065_lifecycle_proof(payload, caller_authority=caller_authority, record_verifier=record_verifier)

    if "earliest_affected_phase" in payload or "replay_start_phase" in payload:
        return evaluate_ch2_064_replay_invalidation(payload, caller_authority=caller_authority)
    if "example_preconditions" in payload or "evaluator_record_ref" in payload:
        return evaluate_ch2_065_lifecycle_proof(payload, caller_authority=caller_authority, record_verifier=record_verifier)

    return GateOutput(
        state=GateState.MISSING,
        must_id="PD-CH2-064",
        detail="Unrecognized replay payload schema",
        failures=["MISSING[PD-CH2-064]"],
    )
