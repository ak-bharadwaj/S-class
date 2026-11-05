"""Tests for F9 outcome metrics and Chapter 5 metric requirements.

Validates:
- PD-F9-001: Deterministic metric projection from canonical events / replayed state.
- PD-F9-002: Mandatory declaration of numerator, denominator, and canonical event basis.
- PD-F9-003: Paired evaluation of trade-off metrics (e.g. false-completion vs false-block).
- PD-F9-004: Strict exclusion of agent/operator self-reported metrics.
- PD-CH5-005: Zero denominator classification as NOT_APPLICABLE, rejection of invented counters.
- PD-CH5-012: Disclosure of denominators, observation window, and unknown telemetry as UNAVAILABLE.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import jsonschema
import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.metrics import (
    AuthorityClass,
    Metric,
    MetricState,
    ObservationWindow,
    PairedMetric,
    Stratum,
    Uncertainty,
    compute_metrics_vector_digest,
    evaluate_f9_metric,
    project_metrics_from_events,
)

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "src" / "sclass" / "product" / "schemas" / "metric_report.json"


@pytest.fixture
def metric_report_schema() -> Dict[str, Any]:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ==============================================================================
# Normative Appendix F Fixture Tests
# ==============================================================================


def test_f9_t1_replayed_metric_identity() -> None:
    """F9-T1: Replayed history twice yields identical metric vector and SATISFIED."""
    fixture = {
        "events": [
            "WORK_ASSIGNED",
            "VERIFICATION_COMPLETED",
            "EVIDENCE_ACCEPTED",
            "OBLIGATION_SATISFIED",
        ],
        "replay_1_metrics_digest": "M-F9-1",
        "replay_2_metrics_digest": "M-F9-1",
        "expected_gate_output": "SATISFIED",
    }
    res = evaluate_f9_metric(fixture)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"
    assert "vector_digest" in res.explain


def test_f9_t2_denominator_required() -> None:
    """F9-T2: Metric declaration omitting denominator returns MISSING[PD-F9-002]."""
    fixture = {
        "metric": "false_completion_rate",
        "numerator": "invalidated_after_satisfaction",
        "denominator": None,
        "expected_gate_output": "MISSING[PD-F9-002]",
    }
    res = evaluate_f9_metric(fixture)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F9-002"
    assert str(res) == "MISSING[PD-F9-002]"


def test_f9_t3_paired_goodhart_detection() -> None:
    """F9-T3: Paired Goodhart detection flags warning when one metric improves and paired worsens."""
    fixture = {
        "false_completion_rate_old": 0.10,
        "false_completion_rate_new": 0.05,
        "false_block_rate_old": 0.08,
        "false_block_rate_new": 0.20,
        "paired_evaluation": True,
        "expected_gate_output": "SATISFIED",
    }
    res = evaluate_f9_metric(fixture)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"
    assert res.explain.get("review_flagged") is True
    assert "warning" in res.explain


def test_f9_t4_self_report_ignored() -> None:
    """F9-T4: Agent-reported cost/time ignored, canonical metrics preserved."""
    fixture = {
        "agent_reported_cost": 1,
        "agent_reported_time_seconds": 2,
        "canonical_cost": 10,
        "canonical_time_seconds": 20,
        "expected_metric_cost": 10,
        "expected_metric_time_seconds": 20,
        "expected_gate_output": "SATISFIED",
    }
    res = evaluate_f9_metric(fixture)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"
    assert res.explain.get("canonical_cost") == 10
    assert res.explain.get("canonical_time_seconds") == 20
    assert res.explain.get("agent_self_report_ignored") is True


def test_ch5_t5_metric_zero_denominator() -> None:
    """CH5-T5: Zero denominator classifies metric as NOT_APPLICABLE (PD-CH5-005)."""
    fixture = {
        "numerator": 0,
        "denominator": 0,
        "expected_metric": "NOT_APPLICABLE",
    }
    res = evaluate_f9_metric(fixture)
    assert res.state == GateState.SATISFIED
    assert res.explain.get("expected_metric") == "NOT_APPLICABLE"
    assert res.explain.get("state") == MetricState.NOT_APPLICABLE.value


def test_ch5_t17_gaming_fixture_pd_ch5_012() -> None:
    """CH5-T17: Gaming fixture testing denominator omission, window shortening, and forged telemetry."""
    fixture = {
        "must_id": "PD-CH5-012",
        "fixture_role": "gaming",
        "input_binding": "typed mismatch of one named digest-bound input per variant",
        "bound_inputs": ["metric_definition_digest", "denominator", "observation_window", "telemetry_status"],
        "attack_or_case": "Outcome metrics MUST derive from canonical records and disclose denominators, observation window and unknown telemetry as UNAVAILABLE.",
        "expected_gate_output": "MISSING[PD-CH5-012]",
        "execution_evidence": "UNVERIFIED",
        "attack_variants": [
            {
                "id": "A1",
                "mutates": ["denominator"],
                "op": "omit",
                "bypass": "denominator omitted.",
                "expected_gate_output": "MISSING[PD-CH5-012]",
            },
            {
                "id": "A2",
                "mutates": ["observation_window"],
                "op": "replace",
                "bypass": "observation_window shortened to hide a failure period.",
                "expected_gate_output": "MISSING[PD-CH5-012]",
            },
            {
                "id": "A3",
                "mutates": ["telemetry_status"],
                "op": "forge",
                "bypass": "agent substitutes an estimate for missing telemetry instead of UNAVAILABLE.",
                "expected_gate_output": "MISSING[PD-CH5-012]",
            },
        ],
    }
    res = evaluate_f9_metric(fixture)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH5-012"
    assert str(res) == "MISSING[PD-CH5-012]"

    # Test individual gaming variants
    v1 = {"must_id": "PD-CH5-012", "denominator": None, "observation_window": {"start_event_ref": "E1", "end_event_ref": "E2"}}
    assert evaluate_f9_metric(v1).state == GateState.MISSING

    v2 = {"must_id": "PD-CH5-012", "denominator": "10", "observation_window": "shortened"}
    assert evaluate_f9_metric(v2).state == GateState.MISSING

    v3 = {"must_id": "PD-CH5-012", "denominator": "10", "observation_window": {"start_event_ref": "E1", "end_event_ref": "E2"}, "telemetry_status": "forged"}
    assert evaluate_f9_metric(v3).state == GateState.MISSING


def test_ch5_t18_happy_fixture_pd_ch5_012() -> None:
    """CH5-T18: Happy fixture with all named inputs present and valid."""
    fixture = {
        "must_id": "PD-CH5-012",
        "fixture_role": "happy",
        "input_binding": "every named input present and digest-equal to the authorized baseline",
        "bound_inputs": ["metric_definition_digest", "denominator", "observation_window", "telemetry_status"],
        "baseline": "authorized baseline digests pinned by the F5 gate tuple; no variant mutates any bound input",
        "attack_or_case": "Conforming case, no violation present.",
        "expected_gate_output": "SATISFIED",
        "execution_evidence": "UNVERIFIED",
    }
    res = evaluate_f9_metric(fixture)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


# ==============================================================================
# Security, Negative, and Boundary Tests
# ==============================================================================


def test_no_injected_authority_fails_closed() -> None:
    """Evaluator without injected authority must never return SATISFIED."""
    fixture = {
        "events": ["E1", "E2"],
        "expected_gate_output": "SATISFIED",
    }
    # No authority
    res_none = evaluate_f9_metric(fixture, caller_authority=None)
    assert res_none.state == GateState.MISSING

    # Agent authority
    res_agent = evaluate_f9_metric(fixture, caller_authority="AGENT")
    assert res_agent.state == GateState.MISSING

    # Projection with no authority returns empty
    assert project_metrics_from_events(["E1"], caller_authority=None) == ()
    assert project_metrics_from_events(["E1"], caller_authority="AGENT") == ()


def test_unpaired_optimization_rejected() -> None:
    """Isolated evaluation of paired metrics fails closed (PD-F9-003)."""
    fixture = {
        "false_completion_rate_old": 0.10,
        "false_completion_rate_new": 0.05,
        "paired_evaluation": False,
    }
    res = evaluate_f9_metric(fixture)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F9-003"


def test_malformed_unhashable_and_empty_inputs() -> None:
    """Unhashable, empty, None, and malformed inputs fail closed without uncaught exceptions."""
    for malformed in [None, [], 123, "string", {}, {"events": []}, {"events": None}]:
        res = evaluate_f9_metric(malformed)
        assert res.state == GateState.MISSING

    # Invalid types in paired evaluation
    bad_paired = {
        "false_completion_rate_old": [1, 2],  # unhashable list
        "false_completion_rate_new": {"a": 1},  # dict
        "false_block_rate_old": float("nan"),  # NaN
        "false_block_rate_new": 0.20,
        "paired_evaluation": True,
    }
    res_bad = evaluate_f9_metric(bad_paired)
    assert res_bad.state == GateState.MISSING


def test_projection_determinism_and_unknown_telemetry() -> None:
    """Deterministic projection and UNAVAILABLE telemetry disclosure (PD-F9-001, PD-CH5-012)."""
    events = ["EVENT-1", "EVENT-2", "EVENT-3"]
    proj1 = project_metrics_from_events(events, telemetry_status="UNAVAILABLE", canonical_cost=42, canonical_time_seconds=12)
    proj2 = project_metrics_from_events(events, telemetry_status="UNAVAILABLE", canonical_cost=42, canonical_time_seconds=12)

    assert len(proj1) == 4
    assert compute_metrics_vector_digest(proj1) == compute_metrics_vector_digest(proj2)

    # Verify telemetry metric is UNAVAILABLE and not zero
    telem_m = [m for m in proj1 if m.metric_id == "outcome_telemetry"][0]
    assert telem_m.state == MetricState.UNAVAILABLE
    assert telem_m.numerator is None
    assert telem_m.denominator is None


# ==============================================================================
# Appendix A Schema Serialization and Blocker Verification
# ==============================================================================


def test_metric_report_schema_conformance(metric_report_schema: Dict[str, Any]) -> None:
    """Metric.to_metric_report_dict() strictly conforms to Appendix A MetricReport schema."""
    m = Metric(
        metric_id="false_completion_rate",
        numerator="2",
        denominator="100",
        unit="count/count",
        observation_window=ObservationWindow(start_event_ref="EV-001", end_event_ref="EV-100"),
        stratum=Stratum(work_type="FEATURE", lane="LANE-A"),
        exclusions=("ex1",),
        uncertainty=Uncertainty(method="bootstrap", lower=0.01, upper=0.03, confidence_level=0.95),
        state=MetricState.AVAILABLE,
        source_refs=("REF-001",),
        authority_class=AuthorityClass.PROJECTION,
        event_basis="canonical_event_stream",
        pair_id="PAIR-001",
    )
    d = m.to_metric_report_dict()

    # Validates cleanly against closed schema
    jsonschema.validate(instance=d, schema=metric_report_schema)

    # Verify internal fields are NOT leaked into closed schema
    assert "event_basis" not in d
    assert "pair_id" not in d


def test_tracked_serialization_blocker(metric_report_schema: Dict[str, Any]) -> None:
    """Documents the tracked schema blocker: serializing event_basis fails schema validation.

    Because Appendix A metric_report.json has additionalProperties: false and does not define
    event_basis or pair_id, attempting to serialize event_basis directly fails validation.
    This confirms the brief's analysis and proves the tracked blocker is real.
    """
    m = Metric(
        metric_id="false_completion_rate",
        numerator="2",
        denominator="100",
        unit="count/count",
        observation_window=ObservationWindow(start_event_ref="EV-001", end_event_ref="EV-100"),
        stratum=Stratum(work_type="FEATURE", lane="LANE-A"),
        exclusions=(),
        uncertainty=None,
        state=MetricState.AVAILABLE,
        source_refs=("REF-001",),
        authority_class=AuthorityClass.PROJECTION,
    )
    d = m.to_metric_report_dict()

    # Adding event_basis violates closed schema
    d_with_event_basis = dict(d)
    d_with_event_basis["event_basis"] = "canonical_stream"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=d_with_event_basis, schema=metric_report_schema)
