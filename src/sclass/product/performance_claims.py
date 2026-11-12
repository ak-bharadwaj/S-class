"""Evaluator for performance claims and objectives in S-Class product layer.

Implements Chapter 5 performance claim validation:
- PD-CH5-004: Performance statements MUST report measured units and corpus; unsupported latency promises return MISSING[PD-CH5-004].
- PD-CH5-011: Performance claims MUST include measured corpus, sample count meeting policy-bound minimum (default 100 for p99), unit and percentile; unmeasured objectives remain OPEN.

Pure deterministic evaluator without live benchmarking, wall-clock enforcement,
filesystem writes, or subprocess calls.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from sclass.product.gate import GateOutput, GateState


QUALIFIED_EVALUATOR_BOUNDARY: str = "QUALIFIED_EVALUATOR"
"""Module-level authority constant for Lane B2-METRICS-B.

The actual trust boundary is caller wiring, not the string label.
Accepted caller_authority values are strictly the closed set {QUALIFIED_EVALUATOR_BOUNDARY}.
"""


@dataclass(frozen=True)
class PerformancePolicy:
    """Policy bounds for performance measurement validation (PD-CH5-011)."""

    min_samples_p99: int = 100
    min_samples_p95: int = 20
    min_samples_default: int = 10
    max_samples_cap: int = 100_000
    allowed_units: Tuple[str, ...] = (
        "ms",
        "s",
        "seconds",
        "MB",
        "bytes",
        "files",
        "nodes",
        "edges",
        "%",
        "count",
    )

    def __post_init__(self) -> None:
        if self.min_samples_p99 < 1:
            raise ValueError("min_samples_p99 must be positive")
        if self.max_samples_cap < self.min_samples_p99:
            raise ValueError("max_samples_cap must exceed min_samples_p99")


@dataclass(frozen=True)
class PerformanceClaim:
    """Immutable record representing a performance claim or statement."""

    claim_id: Optional[str] = None
    claim_text: Optional[str] = None
    corpus_digest: Optional[str] = None
    sample_count: Optional[int] = None
    unit: Optional[str] = None
    percentile: Optional[Union[float, int, str]] = None
    threshold: Optional[Union[float, int]] = None
    measurement_window: Optional[str] = None
    objective_status: str = "OPEN"

    def __post_init__(self) -> None:
        if self.sample_count is not None:
            if not isinstance(self.sample_count, int) or isinstance(self.sample_count, bool):
                raise TypeError("sample_count must be an integer")
        if self.threshold is not None:
            if not isinstance(self.threshold, (int, float)) or isinstance(self.threshold, bool) or math.isnan(self.threshold):
                raise TypeError("threshold must be numeric")


def evaluate_performance_claim(
    claim_or_fixture: Any,
    *,
    caller_authority: Optional[str] = None,
    policy: Optional[PerformancePolicy] = None,
) -> GateOutput:
    """Pure deterministic evaluator for performance claims against PD-CH5-004 and PD-CH5-011.

    The actual trust boundary is caller wiring, not the string label.
    Accepted caller_authority values are strictly the closed set {QUALIFIED_EVALUATOR_BOUNDARY}.
    Omitted, None, 'AGENT', or unrecognized caller_authority fails closed to MISSING[PD-CH5-004].

    Enforces:
    - Authority requirement: missing authority or agent self-assertion returns MISSING[PD-CH5-004].
    - PD-CH5-004: Unsupported latency promises (missing corpus/window) return MISSING[PD-CH5-004].
    - PD-CH5-011: Validates measured corpus, sample count against policy minimum, unit, percentile.
    - Policy cap: sample count > 100,000 fails closed with MISSING[PD-CH5-011].
    """
    # 1. Authority validation
    if caller_authority is not QUALIFIED_EVALUATOR_BOUNDARY and caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH5-004",
            detail="Missing or unauthorized caller_authority; actual trust boundary is caller wiring",
        )

    if policy is None:
        policy = PerformancePolicy()

    # 2. Input type validation
    if isinstance(claim_or_fixture, PerformanceClaim):
        data: Dict[str, Any] = {
            "claim_id": claim_or_fixture.claim_id,
            "claim": claim_or_fixture.claim_text,
            "corpus_digest": claim_or_fixture.corpus_digest,
            "sample_count": claim_or_fixture.sample_count,
            "unit": claim_or_fixture.unit,
            "percentile": claim_or_fixture.percentile,
            "threshold": claim_or_fixture.threshold,
            "measurement_window": claim_or_fixture.measurement_window,
            "objective_status": claim_or_fixture.objective_status,
        }
    elif isinstance(claim_or_fixture, dict):
        data = claim_or_fixture
    else:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH5-004",
            detail=f"Malformed performance claim: expected dict or PerformanceClaim, got {type(claim_or_fixture).__name__}",
        )

    # 3. Check for CH5-T4 unsupported latency promise (PD-CH5-004)
    # Match if claim string is provided without benchmark corpus or measurement window
    if "claim" in data:
        claim_str = data.get("claim")
        if not isinstance(claim_str, str) or not claim_str.strip():
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-004",
                detail="Claim text must be a non-empty string",
            )
        corpus = data.get("benchmark_corpus")
        window = data.get("measurement_window")
        if corpus in ["absent", None, ""] or window in ["absent", None, ""]:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-004",
                detail="Unsupported latency promise: benchmark corpus or measurement window absent",
            )

    # 4. Check for CH5-T15 / CH5-T16 fixtures (PD-CH5-011)
    must_id = data.get("must_id")
    if must_id == "PD-CH5-011" or "corpus_digest" in data or "percentile" in data:
        # Validate corpus_digest
        corpus_digest = data.get("corpus_digest")
        if not corpus_digest or not isinstance(corpus_digest, str) or not corpus_digest.strip() or corpus_digest in ["absent", "null"]:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-011",
                detail="Performance claim omits measured corpus digest",
            )

        # Validate unit
        unit = data.get("unit")
        if not unit or not isinstance(unit, str) or not unit.strip() or unit in ["absent", "null"]:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-011",
                detail="Performance claim omits measured unit",
            )

        # Validate percentile
        percentile = data.get("percentile")
        if percentile is None or percentile in ["absent", "null"]:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-011",
                detail="Performance claim omits percentile declaration",
            )

        # Parse numeric percentile value for sample bound checking
        perc_num: float = 0.0
        if isinstance(percentile, (int, float)):
            perc_num = float(percentile)
        elif isinstance(percentile, str):
            clean_p = percentile.lower().replace("p", "").replace("%", "").strip()
            try:
                perc_num = float(clean_p)
            except ValueError:
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH5-011",
                    detail=f"Invalid percentile format: {percentile}",
                )
        else:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-011",
                detail="Percentile must be numeric or valid string format",
            )

        if math.isnan(perc_num) or not (0.0 <= perc_num <= 100.0):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-011",
                detail="Percentile value out of range (must be between 0 and 100)",
            )

        # Validate sample_count
        sample_count = data.get("sample_count")
        if sample_count is None or isinstance(sample_count, bool) or not isinstance(sample_count, int):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-011",
                detail="Performance claim omits or provides non-integer sample count",
            )

        # Check maximum policy cap (100,000 samples)
        if sample_count > policy.max_samples_cap:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-011",
                detail=f"Sample count {sample_count} exceeds policy maximum cap of {policy.max_samples_cap}",
            )

        # Determine minimum required samples by percentile
        min_required = policy.min_samples_default
        if perc_num >= 99.0:
            min_required = policy.min_samples_p99
        elif perc_num >= 95.0:
            min_required = policy.min_samples_p95

        if sample_count < min_required:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-011",
                detail=f"Sample count {sample_count} below policy minimum of {min_required} for p{perc_num:.0f}",
            )

        # Validate measured_result
        measured_result = data.get("measured_result")
        if measured_result is None and "measured_value" in data:
            measured_result = data.get("measured_value")
        if (
            measured_result is None
            or isinstance(measured_result, bool)
            or not isinstance(measured_result, (int, float))
            or math.isnan(measured_result)
            or math.isinf(measured_result)
            or measured_result <= 0
        ):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-011",
                detail="Performance claim omits or provides invalid measured result (must be positive number)",
            )

        # Check objective status: unmeasured objectives remain OPEN (baseline claims are not evidence)
        if data.get("objective_status") == "OPEN" and not data.get("measured_evidence_ref"):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH5-011",
                detail="Unmeasured performance objective remains OPEN without bound evidence",
            )

        return GateOutput(
            state=GateState.SATISFIED,
            explain={
                "corpus_digest": corpus_digest,
                "sample_count": sample_count,
                "unit": unit,
                "percentile": percentile,
                "measured_result": measured_result,
                "policy_min": min_required,
            },
        )

    return GateOutput(
        state=GateState.MISSING,
        must_id="PD-CH5-004",
        detail="Unrecognized performance claim fixture",
    )


def evaluate_pd_ch5_011_performance_measurement(
    payload: Mapping[str, Any] | Dict[str, Any],
    caller_authority: Optional[str] = None,
    policy: Optional[PerformancePolicy] = None,
) -> GateOutput:
    """Dedicated evaluator for PD-CH5-011: Validates performance measurement records."""
    if not isinstance(payload, (dict, Mapping)):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH5-011",
            detail=f"Malformed payload: expected Mapping, got {type(payload).__name__}",
        )
    p_dict = dict(payload)
    p_dict["must_id"] = "PD-CH5-011"
    return evaluate_performance_claim(p_dict, caller_authority=caller_authority, policy=policy)


def evaluate_performance_gate(
    payload: Mapping[str, Any] | Dict[str, Any],
    caller_authority: Optional[str] = None,
    policy: Optional[PerformancePolicy] = None,
) -> GateOutput:
    """Public gate path for Chapter 5 performance claims (PD-CH5-004, PD-CH5-011)."""
    return evaluate_performance_claim(payload, caller_authority=caller_authority, policy=policy)
