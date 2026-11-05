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
    AuthorityClass,
    Metric,
    MetricState,
    ObservationWindow,
    Stratum,
    evaluate_f9_metric,
    project_metrics_from_events,
)

SCHEMA_PATH = REPO_ROOT / "src" / "sclass" / "product" / "schemas" / "metric_report.json"
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    SCHEMA = json.load(f)


def probe_1_no_authority() -> bool:
    res = evaluate_f9_metric({"events": ["E1"]}, caller_authority=None)
    return res.state == GateState.MISSING and res.must_id == "PD-F9-001"


def probe_2_agent_authority() -> bool:
    res = evaluate_f9_metric({"events": ["E1"]}, caller_authority="AGENT")
    return res.state == GateState.MISSING and res.must_id == "PD-F9-001"


def probe_3_missing_denominator() -> bool:
    res = evaluate_f9_metric({"metric": "false_completion_rate", "denominator": None})
    return res.state == GateState.MISSING and res.must_id == "PD-F9-002"


def probe_4_zero_denominator_not_applicable() -> bool:
    res = evaluate_f9_metric({"numerator": 0, "denominator": 0})
    return res.state == GateState.SATISFIED and res.explain.get("expected_metric") == "NOT_APPLICABLE"


def probe_5_unpaired_evaluation() -> bool:
    res = evaluate_f9_metric({
        "false_completion_rate_old": 0.10,
        "false_completion_rate_new": 0.05,
        "false_block_rate_old": 0.08,
        "false_block_rate_new": 0.20,
        "paired_evaluation": False,
    })
    return res.state == GateState.MISSING and res.must_id == "PD-F9-003"


def probe_6_self_report_ignored() -> bool:
    res = evaluate_f9_metric({
        "agent_reported_cost": 1,
        "agent_reported_time_seconds": 2,
        "canonical_cost": 10,
        "canonical_time_seconds": 20,
        "expected_metric_cost": 10,
        "expected_metric_time_seconds": 20,
    })
    return res.state == GateState.SATISFIED and res.explain.get("canonical_cost") == 10


def probe_7_telemetry_estimate_rejected() -> bool:
    res = evaluate_f9_metric({
        "must_id": "PD-CH5-012",
        "denominator": "100",
        "observation_window": {"start_event_ref": "E1", "end_event_ref": "E2"},
        "telemetry_status": "forged",
    })
    return res.state == GateState.MISSING and res.must_id == "PD-CH5-012"


def probe_8_shortened_observation_window_rejected() -> bool:
    res = evaluate_f9_metric({
        "must_id": "PD-CH5-012",
        "denominator": "100",
        "observation_window": "shortened",
        "telemetry_status": "AVAILABLE",
    })
    return res.state == GateState.MISSING and res.must_id == "PD-CH5-012"


def probe_9_unhashable_and_nan_inputs() -> bool:
    res1 = evaluate_f9_metric({"false_completion_rate_old": [1, 2], "paired_evaluation": True})
    res2 = evaluate_f9_metric({"false_completion_rate_old": float("nan"), "paired_evaluation": True})
    return res1.state == GateState.MISSING and res2.state == GateState.MISSING


def probe_10_tracked_serialization_blocker() -> bool:
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
    d = m.to_metric_report_dict()
    # Conforms without event_basis
    jsonschema.validate(instance=d, schema=SCHEMA)
    # Adding event_basis fails closed under closed schema
    d_with_eb = dict(d)
    d_with_eb["event_basis"] = "canonical_stream"
    try:
        jsonschema.validate(instance=d_with_eb, schema=SCHEMA)
        return False
    except jsonschema.ValidationError:
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
    ("Probe 10: Tracked blocker: event_basis cannot serialize to closed schema", probe_10_tracked_serialization_blocker),
]


def main() -> int:
    print("=== Security & Fail-Closed Probes: Lane B2-METRICS-A ===")
    passed = 0
    for i, (name, probe_fn) in enumerate(PROBES, 1):
        try:
            ok = probe_fn()
        except Exception as exc:
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
