"""Gate caching, replay evaluation, and verification outcome checks for S-Class product layer.

Implements cache key derivation and evaluates Block 2 MUSTs:
- PD-CH5-003: Full canonical input digest tuple; guidance mismatch returns MISSING[PD-CH5-003].
- PD-CH5-007: Complete explicit gate input tuple required in cache key and replay record.
- PD-CH5-008: Additive evidence alone cannot bypass existing blockers (invalidation owned by PD-CH2-055).
- PD-CH5-009: Exact equality of declared key digests; uncertain dependency-index completeness defaults to MISSING.
- PD-CH5-010: Timeout, flaky disagreement, or pending adapter outcome never green.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.artifacts import canonical_c1, freeze_to_c1_compatible
from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "sclass.product.gate_cache"
"""Enforces caller authority. The real boundary is caller wiring in S-Class execution."""


def compute_gate_cache_key(
    phase: str,
    canonical_state_binding: Mapping[str, Any],
    task_ref: str,
    spec_anchor_digest: str,
    input_digests: Sequence[str],
    pinned_guidance_digest: str,
    policy_version: str,
    evaluator_version: str,
    evaluation_instant: str,
) -> str:
    """Computes deterministic cache key from canonical input tuple.

    Per R2-2 and Master §5.1 L660:
    Tuple includes:
      - phase
      - canonical_state_binding (the 6-field canonical StateBinding tuple/dict)
      - task_ref
      - spec_anchor_digest
      - input_digests
      - pinned_guidance_digest (including skills)
      - policy_version
      - evaluator_version
      - evaluation_instant
    """
    if not phase or not canonical_state_binding or not task_ref or not spec_anchor_digest:
        raise ValueError("Missing required cache key fields")
    if not pinned_guidance_digest or not policy_version or not evaluator_version or not evaluation_instant:
        raise ValueError("Missing required cache key fields")

    # policy_version in evaluation tuple must match StateBinding.policy_version if present
    if "policy_version" in canonical_state_binding:
        if canonical_state_binding["policy_version"] != policy_version:
            raise ValueError("Policy version mismatch between StateBinding and evaluation tuple")

    cache_tuple = (
        phase,
        freeze_to_c1_compatible(canonical_state_binding),
        task_ref,
        spec_anchor_digest,
        tuple(input_digests),
        pinned_guidance_digest,
        policy_version,
        evaluator_version,
        evaluation_instant,
    )
    c1_bytes = canonical_c1(cache_tuple)
    return hashlib.sha256(c1_bytes).hexdigest()


class GateCache:
    """Deterministic cache and replay store for product gate evaluations."""

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}

    def put(
        self,
        cache_key: str,
        gate_output: GateOutput,
        replay_record: Mapping[str, Any],
        caller_authority: Optional[str] = None,
    ) -> None:
        """Stores evaluation result with associated replay record."""
        if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
            raise PermissionError("Unauthorized caller authority")
        self._store[cache_key] = {
            "output": gate_output,
            "replay": dict(replay_record),
        }

    def evaluate_cache_lookup(
        self,
        cache_key: Optional[str],
        evaluation_tuple: Mapping[str, Any],
        cached_guidance_digest: Optional[str] = None,
        current_guidance_digest: Optional[str] = None,
        caller_authority: Optional[str] = None,
    ) -> GateOutput:
        """Evaluates cache lookup and guidance binding per PD-CH5-003 & PD-CH5-007."""
        if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-007",
                failures=["MISSING[PD-CH5-007]"],
                explain={"error": "unauthorized caller authority"},
            )

        # PD-CH5-007: Complete explicit gate input tuple must be present in every cache key / replay record
        # Tuple: phase, canonical_state_binding, pinned_guidance, policy_version, evaluator_version, evaluation_instant
        required_elements = (
            "phase",
            "canonical_state_binding",
            "pinned_guidance",
            "policy_version",
            "evaluator_version",
            "evaluation_instant",
        )
        for elem in required_elements:
            if elem not in evaluation_tuple or evaluation_tuple[elem] is None or evaluation_tuple[elem] == "":
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH5-007",
                    failures=["MISSING[PD-CH5-007]"],
                    explain={"missing_element": elem, "error": f"cache key omits {elem}"},
                )

        # PD-CH5-003: Guidance digest check
        if cached_guidance_digest is not None and current_guidance_digest is not None:
            if cached_guidance_digest != current_guidance_digest:
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH5-003",
                    failures=["MISSING[PD-CH5-003]"],
                    explain={
                        "error": "guidance mismatch",
                        "cached": cached_guidance_digest,
                        "current": current_guidance_digest,
                    },
                )

        # If cache key is missing or not in store
        if not cache_key or cache_key not in self._store:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-003",
                failures=["MISSING[PD-CH5-003]"],
                explain={"error": "cache miss"},
            )

        entry = self._store[cache_key]
        return entry["output"]

    def evaluate_blocker_invalidation(
        self,
        binding_digest: str,
        blocker_ids: Sequence[str],
        additive_evidence_digest: Optional[str] = None,
        authoritative_invalidation: bool = False,
        caller_authority: Optional[str] = None,
    ) -> GateOutput:
        """Evaluates blocker invalidation per MUST PD-CH5-008.

        Additive evidence alone cannot bypass existing blockers.
        Invalidation is owned by PD-CH2-055.
        """
        if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-008",
                failures=["MISSING[PD-CH5-008]"],
                explain={"error": "unauthorized caller authority"},
            )

        # If blockers are open, additive evidence cannot bypass them
        if blocker_ids:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-008",
                failures=["MISSING[PD-CH5-008]"],
                explain={
                    "binding_digest": binding_digest,
                    "blocker_ids": list(blocker_ids),
                    "additive_evidence_digest": additive_evidence_digest,
                    "error": "additive evidence cannot bypass existing blockers",
                },
            )

        if not authoritative_invalidation:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-008",
                failures=["MISSING[PD-CH5-008]"],
                explain={"error": "binding changed but projection not invalidated"},
            )

        return GateOutput(state=GateState.SATISFIED)

    def evaluate_key_digests_and_dependency(
        self,
        declared_key_digests: Sequence[str],
        lookup_digests: Sequence[str],
        dependency_index_completeness: str,
        cached_result_digest: Optional[str] = None,
        evaluator_record_ref: Optional[str] = None,
        caller_authority: Optional[str] = None,
    ) -> GateOutput:
        """Evaluates cache reuse exact equality and dependency completeness per MUST PD-CH5-009."""
        if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-009",
                failures=["MISSING[PD-CH5-009]"],
                explain={"error": "unauthorized caller authority"},
            )

        # CH5-T11 variant A1: one declared cache_key_digest missing from the lookup
        if set(declared_key_digests) != set(lookup_digests):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-009",
                failures=["MISSING[PD-CH5-009]"],
                explain={"error": "one declared cache_key_digest missing from lookup"},
            )

        # CH5-T11 variant A2: dependency_index_completeness=unknown but reuse allowed
        if dependency_index_completeness.lower() in ("unknown", "uncertain", "incomplete"):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-009",
                failures=["MISSING[PD-CH5-009]"],
                explain={"error": "dependency_index_completeness is uncertain or unknown"},
            )

        # CH5-T11 variant A3: worker supplies cached_result_digest without evaluator re-derivation
        if not cached_result_digest or not evaluator_record_ref:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-009",
                failures=["MISSING[PD-CH5-009]"],
                explain={"error": "missing cached_result_digest or evaluator_record_ref"},
            )

        return GateOutput(state=GateState.SATISFIED)

    def evaluate_adapter_outcome(
        self,
        test_run_status: str,
        retry_count: int = 1,
        adapter_result_digest: Optional[str] = None,
        flaky_disagreement: bool = False,
        elapsed_ms: Optional[int] = None,
        caller_authority: Optional[str] = None,
    ) -> GateOutput:
        """Evaluates adapter verification outcome per MUST PD-CH5-010.

        Pending, TIMEOUT, or flaky disagreement adapter outcome is never green.
        elapsed_ms must come from an injected observation source.
        """
        if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-010",
                failures=["MISSING[PD-CH5-010]"],
                explain={"error": "unauthorized caller authority"},
            )

        # CH5-T13 variant A1: test_run_status=TIMEOUT
        if test_run_status.upper() == "TIMEOUT":
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-010",
                failures=["MISSING[PD-CH5-010]"],
                explain={"error": "test_run_status=TIMEOUT counted as pass bypass", "elapsed_ms": elapsed_ms},
            )

        # CH5-T13 variant A2: flaky disagreement
        if flaky_disagreement or test_run_status.upper() == "FLAKY_DISAGREEMENT":
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-010",
                failures=["MISSING[PD-CH5-010]"],
                explain={"error": "two runs disagree (flaky) and green run kept", "retry_count": retry_count},
            )

        # CH5-T13 variant A3: adapter result pending
        if test_run_status.upper() == "PENDING" or not adapter_result_digest:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-010",
                failures=["MISSING[PD-CH5-010]"],
                explain={"error": "adapter result pending but reported green by agent"},
            )

        if test_run_status.upper() not in ("PASSED", "GREEN"):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-010",
                failures=["MISSING[PD-CH5-010]"],
                explain={"error": f"unsuccessful test run status: {test_run_status}"},
            )

        return GateOutput(state=GateState.SATISFIED)
