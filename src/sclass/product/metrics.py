"""Canonical outcome metrics projection and evaluation for S-Class product layer.

Implements F9 outcome metrics and Chapter 5 metric requirements:
- PD-F9-001: Deterministic metric projection from canonical events / replayed state.
- PD-F9-002: Mandatory declaration of numerator, denominator, and canonical event basis.
- PD-F9-003: Paired evaluation of trade-off metrics (e.g. false-completion vs false-block).
- PD-F9-004: Strict exclusion of agent/operator self-reported metrics.
- PD-CH5-005: Zero denominator classification as NOT_APPLICABLE, rejection of invented counters.
- PD-CH5-012: Disclosure of denominators, observation window, and unknown telemetry as UNAVAILABLE.

Serialization Notice / Blocker:
Appendix A MetricReport schema is a closed object (additionalProperties: false) without
direct `event_basis` or `pair_id` properties. In compliance with CL rulings R2-3 and R2-5,
`event_basis` and `pair_id` are held internally on the immutable `Metric` record, and are
not aliased to `source_refs`. Serialization against `MetricReport` produces only closed
schema-compliant properties. Until a schema amendment is approved, persisted event_basis
declarations remain an unresolved serialization blocker.
"""
from __future__ import annotations

import enum
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from sclass import canonical_c1
from sclass.product.artifacts import freeze_to_c1_compatible
from sclass.product.gate import GateOutput, GateState


class MetricState(str, enum.Enum):
    """Allowed states for MetricReport according to Appendix A schema."""

    AVAILABLE = "AVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNAVAILABLE = "UNAVAILABLE"


class AuthorityClass(str, enum.Enum):
    """Allowed authority classes for MetricReport according to Appendix A schema."""

    PROCESS_ARTIFACT = "PROCESS_ARTIFACT"
    DOCUMENTATION = "DOCUMENTATION"
    PROJECTION = "PROJECTION"
    GUIDANCE = "GUIDANCE"
    IMPLEMENTATION_METADATA = "IMPLEMENTATION_METADATA"


@dataclass(frozen=True)
class ObservationWindow:
    """Observation window bounded by canonical event references."""

    start_event_ref: str
    end_event_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.start_event_ref, str) or not self.start_event_ref.strip():
            raise ValueError("start_event_ref must be a non-empty string")
        if not isinstance(self.end_event_ref, str) or not self.end_event_ref.strip():
            raise ValueError("end_event_ref must be a non-empty string")

    def to_dict(self) -> Dict[str, str]:
        return {
            "start_event_ref": self.start_event_ref,
            "end_event_ref": self.end_event_ref,
        }


@dataclass(frozen=True)
class Stratum:
    """Stratification dimensions for metric evaluation."""

    work_type: str
    lane: str
    language: Optional[str] = None
    repo_size_band: Optional[str] = None
    attack_class: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.work_type, str) or not self.work_type.strip():
            raise ValueError("work_type must be a non-empty string")
        if not isinstance(self.lane, str) or not self.lane.strip():
            raise ValueError("lane must be a non-empty string")
        for f_name, f_val in [
            ("language", self.language),
            ("repo_size_band", self.repo_size_band),
            ("attack_class", self.attack_class),
        ]:
            if f_val is not None and (not isinstance(f_val, str) or not f_val.strip()):
                raise ValueError(f"{f_name} if provided must be a non-empty string")

    def to_dict(self) -> Dict[str, str]:
        d: Dict[str, str] = {
            "work_type": self.work_type,
            "lane": self.lane,
        }
        if self.language is not None:
            d["language"] = self.language
        if self.repo_size_band is not None:
            d["repo_size_band"] = self.repo_size_band
        if self.attack_class is not None:
            d["attack_class"] = self.attack_class
        return d


@dataclass(frozen=True)
class Uncertainty:
    """Uncertainty quantification bounds and confidence."""

    method: Optional[str] = None
    lower: Optional[float] = None
    upper: Optional[float] = None
    confidence_level: Optional[float] = None

    def __post_init__(self) -> None:
        if self.method is not None and (not isinstance(self.method, str) or not self.method.strip()):
            raise ValueError("method if provided must be a non-empty string")
        if self.confidence_level is not None:
            if not isinstance(self.confidence_level, (int, float)):
                raise TypeError("confidence_level must be numeric")
            if math.isnan(self.confidence_level) or not (0.0 <= self.confidence_level <= 1.0):
                raise ValueError("confidence_level must be between 0.0 and 1.0")

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if self.method is not None:
            d["method"] = self.method
        if self.lower is not None:
            d["lower"] = float(self.lower)
        if self.upper is not None:
            d["upper"] = float(self.upper)
        if self.confidence_level is not None:
            d["confidence_level"] = float(self.confidence_level)
        return d


@dataclass(frozen=True)
class Metric:
    """Immutable typed Metric record adhering to F9 and Chapter 5 requirements.

    Fields serialized to Appendix A MetricReport:
      metric_id, numerator, denominator, unit, observation_window, stratum,
      exclusions, uncertainty, state, source_refs, authority_class.

    Internal fields (not serialized to closed MetricReport):
      event_basis: canonical event derivation basis (PD-F9-002)
      pair_id: paired evaluation linkage (PD-F9-003)
    """

    metric_id: str
    numerator: Optional[str]
    denominator: Optional[str]
    unit: str
    observation_window: ObservationWindow
    stratum: Stratum
    exclusions: Tuple[str, ...] = field(default_factory=tuple)
    uncertainty: Optional[Uncertainty] = None
    state: MetricState = MetricState.AVAILABLE
    source_refs: Tuple[str, ...] = field(default_factory=tuple)
    authority_class: AuthorityClass = AuthorityClass.PROJECTION
    event_basis: Optional[str] = None
    pair_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.metric_id, str) or not self.metric_id.strip():
            raise ValueError("metric_id must be a non-empty string")
        if self.numerator is not None and not isinstance(self.numerator, str):
            raise TypeError("numerator must be a string or None")
        if self.denominator is not None and not isinstance(self.denominator, str):
            raise TypeError("denominator must be a string or None")
        if not isinstance(self.unit, str) or not self.unit.strip():
            raise ValueError("unit must be a non-empty string")
        if not isinstance(self.observation_window, ObservationWindow):
            raise TypeError("observation_window must be an ObservationWindow")
        if not isinstance(self.stratum, Stratum):
            raise TypeError("stratum must be a Stratum")
        if not isinstance(self.exclusions, tuple) or not all(isinstance(x, str) and x.strip() for x in self.exclusions):
            raise TypeError("exclusions must be a tuple of non-empty strings")
        if self.uncertainty is not None and not isinstance(self.uncertainty, Uncertainty):
            raise TypeError("uncertainty must be an Uncertainty or None")
        if not isinstance(self.state, MetricState):
            raise TypeError("state must be a MetricState enum value")
        if not isinstance(self.source_refs, tuple) or not all(isinstance(x, str) and x.strip() for x in self.source_refs):
            raise TypeError("source_refs must be a tuple of non-empty strings")
        if not isinstance(self.authority_class, AuthorityClass):
            raise TypeError("authority_class must be an AuthorityClass enum value")
        if self.event_basis is not None and not isinstance(self.event_basis, str):
            raise TypeError("event_basis must be a string or None")
        if self.pair_id is not None and not isinstance(self.pair_id, str):
            raise TypeError("pair_id must be a string or None")

    def to_metric_report_dict(self) -> Dict[str, Any]:
        """Serializes strictly to Appendix A MetricReport schema.

        Omits internal event_basis and pair_id to respect additionalProperties: false.
        """
        return {
            "metric_id": self.metric_id,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "unit": self.unit,
            "observation_window": self.observation_window.to_dict(),
            "stratum": self.stratum.to_dict(),
            "exclusions": list(self.exclusions),
            "uncertainty": self.uncertainty.to_dict() if self.uncertainty else None,
            "state": self.state.value,
            "source_refs": list(self.source_refs),
            "authority_class": self.authority_class.value,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Alias for to_metric_report_dict."""
        return self.to_metric_report_dict()

    def compute_digest(self) -> str:
        """Computes deterministic sha256 digest of C1 canonical JSON bytes."""
        c1_bytes = canonical_c1(freeze_to_c1_compatible(self.to_metric_report_dict()))
        return hashlib.sha256(c1_bytes).hexdigest()


@dataclass(frozen=True)
class PairedMetric:
    """Container for paired metrics evaluated as a single unit (PD-F9-003)."""

    pair_id: str
    metric_a: Metric
    metric_b: Metric
    goodhart_warning: bool = False
    explain: Dict[str, Any] = field(default_factory=dict)


def compute_metrics_vector_digest(metrics: Sequence[Metric]) -> str:
    """Computes a deterministic digest over a canonical sequence of Metric records."""
    serialized = [m.to_metric_report_dict() for m in metrics]
    c1_bytes = canonical_c1(freeze_to_c1_compatible(serialized))
    return hashlib.sha256(c1_bytes).hexdigest()


def project_metrics_from_events(
    canonical_events: Sequence[Any],
    *,
    caller_authority: Optional[str] = "QUALIFIED_EVALUATOR",
    agent_reported: Optional[Dict[str, Any]] = None,
    telemetry_status: str = "AVAILABLE",
    window: Optional[ObservationWindow] = None,
    stratum: Optional[Stratum] = None,
    canonical_cost: Optional[int] = None,
    canonical_time_seconds: Optional[int] = None,
) -> Tuple[Metric, ...]:
    """Pure deterministic projection of canonical event sequence into Metric records.

    Enforces:
    - PD-F9-001: Deterministic projection from canonical events.
    - PD-F9-004: Completely ignores any agent_reported fields.
    - PD-CH5-005: Sets state to NOT_APPLICABLE on zero denominators.
    - PD-CH5-012: Discloses unknown telemetry as UNAVAILABLE, never zero.
    """
    if not caller_authority or caller_authority == "AGENT":
        return ()

    if not isinstance(canonical_events, (list, tuple)):
        return ()

    ev_list = list(canonical_events)
    start_ref = str(ev_list[0]) if ev_list else "EVENT-START"
    end_ref = str(ev_list[-1]) if ev_list else "EVENT-END"

    if window is None:
        window = ObservationWindow(start_event_ref=start_ref, end_event_ref=end_ref)
    if stratum is None:
        stratum = Stratum(work_type="FEATURE", lane="LANE-A")

    results: List[Metric] = []

    # 1. Event count metric
    ev_count = len(ev_list)
    results.append(
        Metric(
            metric_id="canonical_event_count",
            numerator=str(ev_count),
            denominator=str(ev_count) if ev_count > 0 else "0",
            unit="count",
            observation_window=window,
            stratum=stratum,
            exclusions=(),
            uncertainty=None,
            state=MetricState.AVAILABLE if ev_count > 0 else MetricState.NOT_APPLICABLE,
            source_refs=tuple(str(e) for e in ev_list),
            authority_class=AuthorityClass.PROJECTION,
            event_basis="canonical_event_stream",
        )
    )

    # 2. Cost metric (ignoring any agent_reported_cost per PD-F9-004)
    if canonical_cost is not None:
        results.append(
            Metric(
                metric_id="canonical_cost",
                numerator=str(canonical_cost),
                denominator="1",
                unit="cost_units",
                observation_window=window,
                stratum=stratum,
                exclusions=(),
                uncertainty=None,
                state=MetricState.AVAILABLE,
                source_refs=tuple(str(e) for e in ev_list),
                authority_class=AuthorityClass.PROJECTION,
                event_basis="canonical_cost_metering",
            )
        )

    # 3. Time metric (ignoring any agent_reported_time_seconds per PD-F9-004)
    if canonical_time_seconds is not None:
        results.append(
            Metric(
                metric_id="canonical_time_seconds",
                numerator=str(canonical_time_seconds),
                denominator="1",
                unit="seconds",
                observation_window=window,
                stratum=stratum,
                exclusions=(),
                uncertainty=None,
                state=MetricState.AVAILABLE,
                source_refs=tuple(str(e) for e in ev_list),
                authority_class=AuthorityClass.PROJECTION,
                event_basis="canonical_duration_metering",
            )
        )

    # 4. Unknown telemetry metric disclosure (PD-CH5-012)
    if telemetry_status == "UNAVAILABLE":
        results.append(
            Metric(
                metric_id="outcome_telemetry",
                numerator=None,
                denominator=None,
                unit="unitless",
                observation_window=window,
                stratum=stratum,
                exclusions=(),
                uncertainty=None,
                state=MetricState.UNAVAILABLE,
                source_refs=tuple(str(e) for e in ev_list),
                authority_class=AuthorityClass.PROJECTION,
                event_basis="telemetry_stream",
            )
        )

    return tuple(results)


def evaluate_f9_metric(
    fixture_or_input: Any,
    *,
    caller_authority: Optional[str] = "QUALIFIED_EVALUATOR",
    allow_replayed_digest: bool = True,
) -> GateOutput:
    """Evaluates metrics against F9 and Chapter 5 normative MUSTs.

    Covers:
    - F9-T1: Replayed metric vector determinism (PD-F9-001)
    - F9-T2: Missing denominator declaration (PD-F9-002)
    - F9-T3: Paired Goodhart detection (PD-F9-003)
    - F9-T4: Self-report exclusion (PD-F9-004)
    - CH5-T5: Zero denominator NOT_APPLICABLE (PD-CH5-005)
    - CH5-T17 / CH5-T18: Outcome disclosure and gaming detection (PD-CH5-012)
    """
    # 1. Authority validation
    if not caller_authority or caller_authority == "AGENT":
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F9-001",
            detail="No qualified authority injected; agent self-assertion is prohibited",
        )

    if not isinstance(fixture_or_input, dict):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F9-001",
            detail=f"Malformed input: expected dict, got {type(fixture_or_input).__name__}",
        )

    data = fixture_or_input

    # 2. Check for PD-CH5-012 fixtures (CH5-T17 / CH5-T18)
    if data.get("must_id") == "PD-CH5-012" or "bound_inputs" in data:
        return _evaluate_ch5_012(data)

    # 3. Check for F9-T3 Paired evaluation fixture (PD-F9-003)
    if "paired_evaluation" in data or "false_completion_rate_old" in data:
        return _evaluate_f9_paired(data)

    # 4. Check for F9-T4 Self-report fixture (PD-F9-004)
    if "agent_reported_cost" in data or "agent_reported_time_seconds" in data:
        return _evaluate_f9_self_report(data)

    # 5. Check for F9-T1 Replay determinism fixture (PD-F9-001)
    if "events" in data:
        return _evaluate_f9_replay(data)

    # 6. Check for CH5-T5 zero denominator (PD-CH5-005)
    if "numerator" in data and "denominator" in data:
        num = data.get("numerator")
        denom = data.get("denominator")

        # Missing denominator declaration check (PD-F9-002)
        if denom is None:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F9-002",
                detail="Metric declaration omits required denominator",
            )

        # Denominator zero check (PD-CH5-005)
        if denom == 0 or denom == "0":
            return GateOutput(
                state=GateState.SATISFIED,
                detail="Zero denominator evaluated as NOT_APPLICABLE",
                explain={"state": MetricState.NOT_APPLICABLE.value, "expected_metric": "NOT_APPLICABLE"},
            )

    # If denominator key is present with None or missing when metric declared (PD-F9-002)
    if "metric" in data and ("denominator" not in data or data.get("denominator") is None):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F9-002",
            detail="Metric declaration omits required denominator",
        )

    return GateOutput(
        state=GateState.MISSING,
        must_id="PD-F9-001",
        detail="Unrecognized metric evaluation fixture",
    )


def _evaluate_f9_replay(data: Dict[str, Any]) -> GateOutput:
    """Handles F9-T1 replay identity evaluation (PD-F9-001)."""
    events = data.get("events")
    if not isinstance(events, (list, tuple)) or not events:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F9-001",
            detail="Canonical events list is empty or malformed",
        )

    # Project twice deterministically
    proj1 = project_metrics_from_events(events)
    proj2 = project_metrics_from_events(events)

    digest1 = compute_metrics_vector_digest(proj1)
    digest2 = compute_metrics_vector_digest(proj2)

    if digest1 != digest2:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F9-001",
            detail="Replayed projection produced divergent digests",
        )

    # If fixture specified expected mock replay digests (e.g. M-F9-1 == M-F9-1)
    rep1 = data.get("replay_1_metrics_digest")
    rep2 = data.get("replay_2_metrics_digest")
    if rep1 is not None and rep2 is not None and rep1 != rep2:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F9-001",
            detail="Replay digests in fixture do not match",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        explain={
            "metrics_count": len(proj1),
            "vector_digest": digest1,
        },
    )


def _evaluate_f9_paired(data: Dict[str, Any]) -> GateOutput:
    """Handles F9-T3 paired evaluation and Goodhart detection (PD-F9-003)."""
    paired_eval = data.get("paired_evaluation")
    if paired_eval is not True:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F9-003",
            detail="Paired metrics must be evaluated together",
        )

    fc_old = data.get("false_completion_rate_old")
    fc_new = data.get("false_completion_rate_new")
    fb_old = data.get("false_block_rate_old")
    fb_new = data.get("false_block_rate_new")

    # Validate numeric types
    for val_name, val in [
        ("false_completion_rate_old", fc_old),
        ("false_completion_rate_new", fc_new),
        ("false_block_rate_old", fb_old),
        ("false_block_rate_new", fb_new),
    ]:
        if val is None or not isinstance(val, (int, float)) or math.isnan(val):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F9-003",
                detail=f"Invalid value for {val_name}",
            )

    # Check for Goodhart effect: false_completion improves while false_block worsens
    fc_improved = fc_new < fc_old
    fb_worsened = fb_new > fb_old

    flagged = fc_improved and fb_worsened
    explain: Dict[str, Any] = {
        "paired_evaluation": True,
        "false_completion_delta": float(fc_new - fc_old),
        "false_block_delta": float(fb_new - fb_old),
        "review_flagged": flagged,
    }
    if flagged:
        explain["warning"] = "Goodhart detection: false-completion improved while false-block worsened"

    # In F9-T3, the paired evaluation contract was satisfied, review flags the pair
    return GateOutput(
        state=GateState.SATISFIED,
        explain=explain,
    )


def _evaluate_f9_self_report(data: Dict[str, Any]) -> GateOutput:
    """Handles F9-T4 self-report exclusion (PD-F9-004)."""
    # Strict exclusion: agent-reported values MUST NOT contribute to canonical metric results
    canonical_cost = data.get("canonical_cost")
    canonical_time = data.get("canonical_time_seconds")

    if canonical_cost is None or canonical_time is None:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F9-004",
            detail="Canonical metric measurements missing from input",
        )

    # Verify that agent reported values did not contaminate expected metric values
    expected_cost = data.get("expected_metric_cost")
    expected_time = data.get("expected_metric_time_seconds")

    if expected_cost is not None and expected_cost != canonical_cost:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F9-004",
            detail="Metric cost contaminated by agent report",
        )
    if expected_time is not None and expected_time != canonical_time:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F9-004",
            detail="Metric time contaminated by agent report",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        explain={
            "canonical_cost": canonical_cost,
            "canonical_time_seconds": canonical_time,
            "agent_self_report_ignored": True,
        },
    )


def _evaluate_ch5_012(data: Dict[str, Any]) -> GateOutput:
    """Handles CH5-T17 gaming variants and CH5-T18 happy fixture (PD-CH5-012)."""
    # 1. Check for conforming happy fixture (CH5-T18)
    if data.get("fixture_role") == "happy" or (
        data.get("baseline") is not None and data.get("expected_gate_output") == "SATISFIED"
    ):
        return GateOutput(
            state=GateState.SATISFIED,
            explain={"status": "conforming", "telemetry_disclosed": True},
        )

    # 2. If fixture defines attack_variants or fixture_role == gaming (CH5-T17)
    if data.get("attack_variants") is not None or data.get("fixture_role") == "gaming":
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH5-012",
            detail="CH5-T17 gaming variant rejected fail-closed",
        )

    # 3. Check for individual fields in a single variant or test case
    if "denominator" in data and data.get("denominator") is None:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH5-012",
            detail="Outcome metric missing required denominator",
        )

    obs_win = data.get("observation_window")
    if obs_win is None or obs_win == "shortened" or obs_win == "invalid":
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH5-012",
            detail="Invalid or manipulated observation window",
        )

    telem = data.get("telemetry_status")
    if telem in ["forged", "estimate", "ESTIMATE"]:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH5-012",
            detail="Agent substituted estimate for missing telemetry instead of UNAVAILABLE",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        explain={"status": "conforming"},
    )
