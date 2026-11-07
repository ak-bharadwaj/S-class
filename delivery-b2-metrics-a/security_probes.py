#!/usr/bin/env python3
"""Standalone security and fail-closed probes for Lane B2-METRICS-A."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sclass.product.gate import GateOutput, GateState
from sclass.product.metrics import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    AuthorityClass,
    Metric,
    MetricState,
    ObservationWindow,
    PairedMetric,
    ProductMetricEnvelope,
    Stratum,
    evaluate_f9_metric,
    project_metrics_from_events,
)

SCHEMA_PATH = REPO_ROOT / "src" / "sclass" / "product" / "schemas" / "metric_report.json"
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    SCHEMA = json.load(f)


def probe_1_no_authority() -> bool:
    # Omitted caller_authority defaults to None and fails closed
    res = evaluate_f9_metric({"events": ["E1"]})
    return res.state == GateState.MISSING and res.must_id == "PD-F9-001"


def probe_2_agent_authority() -> bool:
    # Closed set check rejects caller_authority="AGENT"
    res = evaluate_f9_metric({"events": ["E1"]}, caller_authority="AGENT")
    return res.state == GateState.MISSING and res.must_id == "PD-F9-001"


def probe_3_missing_denominator() -> bool:
    res = evaluate_f9_metric(
        {"metric": "false_completion_rate", "denominator": None},
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    return res.state == GateState.MISSING and res.must_id == "PD-F9-002"


def probe_4_zero_denominator_not_applicable() -> bool:
    res = evaluate_f9_metric(
        {"numerator": 0, "denominator": 0},
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    return res.state == GateState.SATISFIED and res.explain.get("expected_metric") == "NOT_APPLICABLE"


def probe_5_unpaired_evaluation() -> bool:
    res = evaluate_f9_metric(
        {
            "false_completion_rate_old": 0.10,
            "false_completion_rate_new": 0.05,
            "false_block_rate_old": 0.08,
            "false_block_rate_new": 0.20,
            "paired_evaluation": False,
        },
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    return res.state == GateState.MISSING and res.must_id == "PD-F9-003"


def probe_6_self_report_ignored() -> bool:
    res = evaluate_f9_metric(
        {
            "agent_reported_cost": 1,
            "agent_reported_time_seconds": 2,
            "canonical_cost": 10,
            "canonical_time_seconds": 20,
            "expected_metric_cost": 10,
            "expected_metric_time_seconds": 20,
        },
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    return res.state == GateState.SATISFIED and res.explain.get("canonical_cost") == 10


def probe_7_telemetry_estimate_rejected() -> bool:
    res = evaluate_f9_metric(
        {
            "must_id": "PD-CH5-012",
            "denominator": "100",
            "observation_window": "valid_window",
            "telemetry_status": "forged",
        },
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    return res.state == GateState.MISSING and res.must_id == "PD-CH5-012"


def probe_8_shortened_observation_window_rejected() -> bool:
    res = evaluate_f9_metric(
        {
            "must_id": "PD-CH5-012",
            "denominator": "100",
            "observation_window": "shortened",
            "telemetry_status": "AVAILABLE",
        },
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    return res.state == GateState.MISSING and res.must_id == "PD-CH5-012"


def probe_9_unhashable_and_nan_inputs() -> bool:
    res1 = evaluate_f9_metric(
        {"false_completion_rate_old": [1, 2], "paired_evaluation": True},
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    res2 = evaluate_f9_metric(
        {"false_completion_rate_old": float("nan"), "paired_evaluation": True},
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    return res1.state == GateState.MISSING and res2.state == GateState.MISSING


def probe_10_product_metric_envelope_conformance() -> bool:
    m = Metric(
        metric_id="false_completion_rate",
        numerator="2",
        denominator="100",
        unit="count/count",
        observation_window=ObservationWindow(start_event_ref="E1", end_event_ref="E2"),
        stratum=Stratum(work_type="FEATURE", lane="LANE-A"),
        exclusions=(),
        uncertainty=None,
        state=MetricState.AVAILABLE,
        source_refs=("REF-1",),
        authority_class=AuthorityClass.PROJECTION,
        event_basis="canonical_event_stream",
    )
    env = m.to_envelope()
    # Inner report validates against closed schema without event_basis
    jsonschema.validate(instance=env.report, schema=SCHEMA)
    # Reconstructing envelope preserves event_basis
    assert env.event_basis == "canonical_event_stream"
    assert len(env.compute_digest()) == 64
    # Evaluating envelope under qualified evaluator satisfies gate
    res = evaluate_f9_metric(env, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    return res.state == GateState.SATISFIED


def probe_11_paired_metric_container_enforcement() -> bool:
    m_fc = Metric(
        metric_id="false_completion_rate",
        numerator="1",
        denominator="100",
        unit="ratio",
        observation_window=ObservationWindow(start_event_ref="E1", end_event_ref="E2"),
        stratum=Stratum(work_type="FEATURE", lane="LANE-A"),
    )
    m_fb = Metric(
        metric_id="false_block_rate",
        numerator="3",
        denominator="100",
        unit="ratio",
        observation_window=ObservationWindow(start_event_ref="E1", end_event_ref="E2"),
        stratum=Stratum(work_type="FEATURE", lane="LANE-A"),
    )
    env_fc = m_fc.to_envelope(pair_id="PAIR-01", event_basis="s1")
    env_fb = m_fb.to_envelope(pair_id="PAIR-01", event_basis="s2")

    paired = PairedMetric(pair_id="PAIR-01", false_completion=env_fc, false_block=env_fb)
    res = evaluate_f9_metric(paired, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    if res.state != GateState.SATISFIED or not res.explain.get("paired_evaluation"):
        return False

    # Incomplete pair rejected
    try:
        PairedMetric(pair_id="PAIR-02", false_completion=env_fc, false_block=None)  # type: ignore
        return False
    except ValueError:
        return True


PROBES = [
    ("Probe 1: No authority fails closed", probe_1_no_authority),
    ("Probe 2: Agent authority fails closed", probe_2_agent_authority),
    ("Probe 3: Missing denominator declaration returns MISSING[PD-F9-002]", probe_3_missing_denominator),
    ("Probe 4: Zero denominator marks NOT_APPLICABLE (PD-CH5-005)", probe_4_zero_denominator_not_applicable),
    ("Probe 5: Unpaired evaluation returns MISSING[PD-F9-003]", probe_5_unpaired_evaluation),
    ("Probe 6: Agent self-report cannot override canonical measurements (PD-F9-004)", probe_6_self_report_ignored),
    ("Probe 7: Forged telemetry estimate returns MISSING[PD-CH5-012]", probe_7_telemetry_estimate_rejected),
    ("Probe 8: Shortened observation window returns MISSING[PD-CH5-012]", probe_8_shortened_observation_window_rejected),
    ("Probe 9: Unhashable and NaN inputs handled safely fail-closed", probe_9_unhashable_and_nan_inputs),
    ("Probe 10: ProductMetricEnvelope C1 digest & closed schema conformance", probe_10_product_metric_envelope_conformance),
    ("Probe 11: PairedMetric container fail-closed enforcement (PD-F9-003)", probe_11_paired_metric_container_enforcement),
]


def main() -> int:
    print("=== Security & Fail-Closed Probes: Lane B2-METRICS-A ===")
    passed = 0
    for i, (name, probe_fn) in enumerate(PROBES, 1):
        try:
            ok = probe_fn()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            print(f"[{i:02d}/{len(PROBES)}] FAILED (exception): {name}: {exc}")
            ok = False

        if ok:
            print(f"[{i:02d}/{len(PROBES)}] PASSED: {name}")
            passed += 1
        else:
            print(f"[{i:02d}/{len(PROBES)}] FAILED: {name}")

    print(f"\nProbes summary: {passed}/{len(PROBES)} passed")
    return 0 if passed == len(PROBES) else 1


if __name__ == "__main__":
    sys.exit(main())
