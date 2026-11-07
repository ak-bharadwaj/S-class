"""Tests for F9 outcome metrics and Chapter 5 metric requirements.

Validates:
- PD-F9-001: Deterministic metric projection from canonical events / replayed state.
- PD-F9-002: Mandatory declaration of numerator, denominator, and canonical event basis.
- PD-F9-003: Paired evaluation of trade-off metrics (e.g. false-completion vs false-block).
- PD-F9-004: Strict exclusion of agent/operator self-reported metrics.
- PD-CH5-005: Zero denominator classification as NOT_APPLICABLE, rejection of invented counters.
- PD-CH5-012: Disclosure of denominators, observation window, and unknown telemetry as UNAVAILABLE.
- R2-8 / WAVE1-FIX: ProductMetricEnvelope, PairedMetric container, closed-set caller authority.
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
    ProductMetricEnvelope,
    QUALIFIED_EVALUATOR_BOUNDARY,
    Stratum,
    Uncertainty,
    compute_metrics_vector_digest,
    create_product_metric_envelope,
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
    res = evaluate_f9_metric(fixture, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
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
    res = evaluate_f9_metric(fixture, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
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
    res = evaluate_f9_metric(fixture, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
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
    res = evaluate_f9_metric(fixture, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
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
    res = evaluate_f9_metric(fixture, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
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
        "expected_gate_output": "MISSING[PD-CH5-012]",
        "attack_variants": [
            {"variant": "omit_denominator", "denominator": None},
            {"variant": "shorten_window", "observation_window": "shortened"},
            {"variant": "forge_telemetry", "telemetry_status": "forged"},
        ],
    }
    res = evaluate_f9_metric(fixture, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH5-012"
    assert str(res) == "MISSING[PD-CH5-012]"


def test_ch5_t18_happy_fixture_pd_ch5_012() -> None:
    """CH5-T18: Conforming baseline metric report evaluates to SATISFIED."""
    fixture = {
        "must_id": "PD-CH5-012",
        "fixture_role": "happy",
        "baseline": {
            "metric_id": "false_completion_rate",
            "denominator": "100",
            "observation_window": {"start_event_ref": "E-01", "end_event_ref": "E-99"},
            "telemetry_status": "AVAILABLE",
        },
        "expected_gate_output": "SATISFIED",
    }
    res = evaluate_f9_metric(fixture, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


# ==============================================================================
# Non-Normative Security, Authority, and Hardening Tests
# ==============================================================================


def test_caller_authority_omitted_returns_missing() -> None:
    """METRICS-A omitted-argument test: omitted caller_authority fails closed to MISSING[PD-F9-001]."""
    fixture = {
        "events": ["E1", "E2"],
        "expected_gate_output": "SATISFIED",
    }
    # Omitted caller_authority argument
    res_omitted = evaluate_f9_metric(fixture)
    assert res_omitted.state == GateState.MISSING
    assert res_omitted.must_id == "PD-F9-001"

    # None caller_authority argument
    res_none = evaluate_f9_metric(fixture, caller_authority=None)
    assert res_none.state == GateState.MISSING
    assert res_none.must_id == "PD-F9-001"

    # Agent caller_authority argument
    res_agent = evaluate_f9_metric(fixture, caller_authority="AGENT")
    assert res_agent.state == GateState.MISSING
    assert res_agent.must_id == "PD-F9-001"

    # Unrecognized authority string
    res_other = evaluate_f9_metric(fixture, caller_authority="SUPERUSER")
    assert res_other.state == GateState.MISSING
    assert res_other.must_id == "PD-F9-001"

    # Projection with omitted authority returns empty tuple
    assert project_metrics_from_events(["E1"]) == ()
    assert project_metrics_from_events(["E1"], caller_authority=None) == ()
    assert project_metrics_from_events(["E1"], caller_authority="AGENT") == ()


def test_replay_vector_mismatch_fails_closed() -> None:
    """If replayed digests in fixture do not match, evaluator fails closed."""
    fixture = {
        "events": ["E1", "E2"],
        "replay_1_metrics_digest": "DIGEST-ALPHA",
        "replay_2_metrics_digest": "DIGEST-BETA",
        "expected_gate_output": "MISSING[PD-F9-001]",
    }
    res = evaluate_f9_metric(fixture, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F9-001"


def test_missing_denominator_declarations() -> None:
    """Both explicit None and absent denominator fail closed under PD-F9-002."""
    # Variant A: denominator explicit None
    res_a = evaluate_f9_metric({"numerator": 5, "denominator": None}, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res_a.state == GateState.MISSING
    assert res_a.must_id == "PD-F9-002"

    # Variant B: metric key present, denominator missing
    res_b = evaluate_f9_metric({"metric": "false_completion_rate"}, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res_b.state == GateState.MISSING
    assert res_b.must_id == "PD-F9-002"


def test_gaming_role_rejection() -> None:
    """Fixture marked with gaming role fails closed even with validly shaped fields (PD-CH5-012)."""
    gaming_fixture = {
        "must_id": "PD-CH5-012",
        "fixture_role": "gaming",
        "observation_window": {"start_event_ref": "E1", "end_event_ref": "E2"},
        "denominator": "100",
        "telemetry_status": "AVAILABLE",
    }
    res = evaluate_f9_metric(gaming_fixture, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH5-012"


def test_malformed_unhashable_and_empty_inputs() -> None:
    """Unhashable, empty, None, and malformed inputs fail closed without uncaught exceptions."""
    for malformed in [None, [], 123, "string", {}, {"events": []}, {"events": None}]:
        res = evaluate_f9_metric(malformed, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
        assert res.state == GateState.MISSING

    # Invalid types in paired evaluation
    bad_paired = {
        "false_completion_rate_old": [1, 2],  # unhashable list
        "false_completion_rate_new": {"a": 1},  # dict
        "false_block_rate_old": float("nan"),  # NaN
        "false_block_rate_new": 0.20,
        "paired_evaluation": True,
    }
    res_bad = evaluate_f9_metric(bad_paired, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res_bad.state == GateState.MISSING


def test_projection_determinism_and_unknown_telemetry() -> None:
    """Deterministic projection and UNAVAILABLE telemetry disclosure (PD-F9-001, PD-CH5-012)."""
    events = ["EVENT-1", "EVENT-2", "EVENT-3"]
    proj1 = project_metrics_from_events(
        events,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        telemetry_status="UNAVAILABLE",
        canonical_cost=42,
        canonical_time_seconds=12,
    )
    proj2 = project_metrics_from_events(
        events,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        telemetry_status="UNAVAILABLE",
        canonical_cost=42,
        canonical_time_seconds=12,
    )

    assert len(proj1) == 4
    assert compute_metrics_vector_digest(proj1) == compute_metrics_vector_digest(proj2)

    # Verify telemetry metric is UNAVAILABLE and not zero
    telem_m = [m for m in proj1 if m.metric_id == "outcome_telemetry"][0]
    assert telem_m.state == MetricState.UNAVAILABLE
    assert telem_m.numerator is None
    assert telem_m.denominator is None


# ==============================================================================
# R2-8 / WAVE1-FIX ProductMetricEnvelope & PairedMetric Tests
# ==============================================================================


def test_product_metric_envelope_c1_digest_and_closed_report(metric_report_schema: Dict[str, Any]) -> None:
    """ProductMetricEnvelope contains versioned envelope fields and closed Appendix A report."""
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
    )
    env = m.to_envelope(
        envelope_version="1.0.0",
        event_basis="canonical_event_stream",
        pair_id="PAIR-001",
    )

    assert env.envelope_version == "1.0.0"
    assert env.event_basis == "canonical_event_stream"
    assert env.pair_id == "PAIR-001"
    assert isinstance(env.compute_digest(), str)
    assert len(env.compute_digest()) == 64

    # Report inside envelope strictly conforms to closed Appendix A schema
    jsonschema.validate(instance=env.report, schema=metric_report_schema)
    assert "event_basis" not in env.report
    assert "pair_id" not in env.report


def test_product_metric_envelope_evaluation_satisfaction() -> None:
    """Valid ProductMetricEnvelope evaluates to SATISFIED."""
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
    env = m.to_envelope(envelope_version="1.0.0", event_basis="canonical_stream")
    res = evaluate_f9_metric(env, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert "envelope_digest" in res.explain


def test_product_metric_envelope_missing_event_basis_or_denominator() -> None:
    """Missing event_basis or denominator fails closed under PD-F9-002."""
    valid_report = {
        "metric_id": "m1",
        "numerator": "1",
        "denominator": "10",
        "unit": "ratio",
        "observation_window": {"start_event_ref": "E1", "end_event_ref": "E2"},
        "stratum": {"work_type": "FEATURE", "lane": "LANE-A"},
        "exclusions": [],
        "uncertainty": None,
        "state": "AVAILABLE",
        "source_refs": [],
        "authority_class": "PROJECTION",
    }

    # Empty event_basis raises ValueError at creation
    with pytest.raises(ValueError):
        ProductMetricEnvelope(envelope_version="1.0.0", report=valid_report, event_basis="")

    # Missing denominator in report
    missing_denom_rep = dict(valid_report)
    missing_denom_rep["denominator"] = None
    env_bad_denom = ProductMetricEnvelope(
        envelope_version="1.0.0",
        report=missing_denom_rep,
        event_basis="canonical_stream",
    )
    res = evaluate_f9_metric(env_bad_denom, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F9-002"


def test_product_metric_envelope_zero_denominator_not_applicable() -> None:
    """Zero denominator evaluates to NOT_APPLICABLE (PD-CH5-005)."""
    zero_denom_rep = {
        "metric_id": "m_zero",
        "numerator": "0",
        "denominator": "0",
        "unit": "ratio",
        "observation_window": {"start_event_ref": "E1", "end_event_ref": "E2"},
        "stratum": {"work_type": "FEATURE", "lane": "LANE-A"},
        "exclusions": [],
        "uncertainty": None,
        "state": "NOT_APPLICABLE",
        "source_refs": [],
        "authority_class": "PROJECTION",
    }
    env = ProductMetricEnvelope(envelope_version="1.0.0", report=zero_denom_rep, event_basis="canonical_stream")
    res = evaluate_f9_metric(env, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert res.explain.get("state") == MetricState.NOT_APPLICABLE.value


def test_product_metric_envelope_unknown_telemetry_unavailable() -> None:
    """Unknown telemetry evaluates to UNAVAILABLE (PD-CH5-012)."""
    unavail_rep = {
        "metric_id": "m_telemetry",
        "numerator": None,
        "denominator": "100",
        "unit": "unitless",
        "observation_window": {"start_event_ref": "E1", "end_event_ref": "E2"},
        "stratum": {"work_type": "FEATURE", "lane": "LANE-A"},
        "exclusions": [],
        "uncertainty": None,
        "state": "UNAVAILABLE",
        "source_refs": [],
        "authority_class": "PROJECTION",
    }
    env = ProductMetricEnvelope(envelope_version="1.0.0", report=unavail_rep, event_basis="telemetry_stream")
    res = evaluate_f9_metric(env, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert res.explain.get("state") == MetricState.UNAVAILABLE.value


def test_paired_metrics_evaluated_together() -> None:
    """False-completion and false-block must be evaluated together as one PairedMetric (PD-F9-003)."""
    m_fc = Metric(
        metric_id="false_completion_rate",
        numerator="1",
        denominator="100",
        unit="ratio",
        observation_window=ObservationWindow(start_event_ref="E1", end_event_ref="E100"),
        stratum=Stratum(work_type="FEATURE", lane="LANE-A"),
    )
    m_fb = Metric(
        metric_id="false_block_rate",
        numerator="3",
        denominator="100",
        unit="ratio",
        observation_window=ObservationWindow(start_event_ref="E1", end_event_ref="E100"),
        stratum=Stratum(work_type="FEATURE", lane="LANE-A"),
    )

    env_fc = m_fc.to_envelope(pair_id="PAIR-01", event_basis="stream_1")
    env_fb = m_fb.to_envelope(pair_id="PAIR-01", event_basis="stream_2")

    paired = PairedMetric(pair_id="PAIR-01", false_completion=env_fc, false_block=env_fb)
    res = evaluate_f9_metric(paired, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert res.explain.get("paired_evaluation") is True
    assert res.explain.get("pair_id") == "PAIR-01"

    # Incomplete paired metric raises ValueError at instantiation
    with pytest.raises(ValueError):
        PairedMetric(pair_id="PAIR-02", false_completion=env_fc, false_block=None)


def test_unpaired_evaluation_missing_pair() -> None:
    """Unpaired evaluation returns MISSING[PD-F9-003]."""
    res = evaluate_f9_metric(
        {
            "paired_evaluation": False,
            "false_completion_rate_old": 0.05,
            "false_completion_rate_new": 0.02,
            "false_block_rate_old": 0.01,
            "false_block_rate_new": 0.04,
        },
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F9-003"


def test_observation_window_manipulation_rejected() -> None:
    """Shortened or invalid observation window returns MISSING[PD-CH5-012]."""
    for bad_win in ["shortened", "invalid", None]:
        res = evaluate_f9_metric(
            {
                "must_id": "PD-CH5-012",
                "observation_window": bad_win,
                "denominator": "100",
                "telemetry_status": "AVAILABLE",
            },
            caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH5-012"


def test_forged_telemetry_estimate_rejected() -> None:
    """Forged telemetry or estimate returns MISSING[PD-CH5-012]."""
    for bad_telem in ["forged", "estimate", "ESTIMATE"]:
        res = evaluate_f9_metric(
            {
                "must_id": "PD-CH5-012",
                "observation_window": "valid_window",
                "telemetry_status": bad_telem,
                "denominator": "100",
            },
            caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH5-012"


def test_envelope_requires_event_basis() -> None:
    """ProductMetricEnvelope must have a non-empty event_basis."""
    rep = {
        "metric_id": "test",
        "numerator": "1",
        "denominator": "10",
        "unit": "ratio",
        "observation_window": {"start_event_ref": "E1", "end_event_ref": "E2"},
        "stratum": {"work_type": "FEATURE", "lane": "LANE-A"},
        "exclusions": [],
        "state": "AVAILABLE",
        "source_refs": [],
        "authority_class": "PROJECTION",
    }
    with pytest.raises(ValueError, match="event_basis must be a non-empty string"):
        ProductMetricEnvelope(envelope_version="1.0.0", report=rep, event_basis="")

    env = ProductMetricEnvelope(envelope_version="1.0.0", report=rep, event_basis="valid_stream")
    object.__setattr__(env, "event_basis", "")
    res = evaluate_f9_metric(env, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F9-002"

