#!/usr/bin/env python3
"""Standalone security and fail-closed probes for Lane B2-METRICS-B."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sclass.product.gate import GateOutput, GateState
from sclass.product.performance_claims import (
    PerformanceClaim,
    PerformancePolicy,
    evaluate_performance_claim,
)


def probe_1_no_authority() -> bool:
    res = evaluate_performance_claim({"claim": "test"}, caller_authority=None)
    return res.state == GateState.MISSING and res.must_id == "PD-CH5-004"


def probe_2_agent_authority() -> bool:
    res = evaluate_performance_claim({"claim": "test"}, caller_authority="AGENT")
    return res.state == GateState.MISSING and res.must_id == "PD-CH5-004"


def probe_3_unsupported_latency_promise() -> bool:
    res = evaluate_performance_claim({
        "claim": "p95 under 100 ms",
        "benchmark_corpus": "absent",
        "measurement_window": "absent",
    })
    return res.state == GateState.MISSING and res.must_id == "PD-CH5-004"


def probe_4_missing_corpus() -> bool:
    res = evaluate_performance_claim({
        "must_id": "PD-CH5-011",
        "corpus_digest": None,
        "sample_count": 500,
        "unit": "ms",
        "percentile": "p99",
    })
    return res.state == GateState.MISSING and res.must_id == "PD-CH5-011"


def probe_5_missing_unit() -> bool:
    res = evaluate_performance_claim({
        "must_id": "PD-CH5-011",
        "corpus_digest": "CORP-001",
        "sample_count": 500,
        "unit": None,
        "percentile": "p99",
    })
    return res.state == GateState.MISSING and res.must_id == "PD-CH5-011"


def probe_6_missing_percentile() -> bool:
    res = evaluate_performance_claim({
        "must_id": "PD-CH5-011",
        "corpus_digest": "CORP-001",
        "sample_count": 500,
        "unit": "ms",
        "percentile": None,
    })
    return res.state == GateState.MISSING and res.must_id == "PD-CH5-011"


def probe_7_insufficient_samples_p99() -> bool:
    res = evaluate_performance_claim({
        "must_id": "PD-CH5-011",
        "corpus_digest": "CORP-001",
        "sample_count": 99,
        "unit": "ms",
        "percentile": "p99",
        "measured_evidence_ref": "EVID-001",
        "objective_status": "MEASURED",
    })
    return res.state == GateState.MISSING and res.must_id == "PD-CH5-011"


def probe_8_samples_overflow_cap() -> bool:
    res = evaluate_performance_claim({
        "must_id": "PD-CH5-011",
        "corpus_digest": "CORP-001",
        "sample_count": 100_001,
        "unit": "ms",
        "percentile": "p99",
        "measured_evidence_ref": "EVID-001",
        "objective_status": "MEASURED",
    })
    return res.state == GateState.MISSING and res.must_id == "PD-CH5-011"


def probe_9_unmeasured_open_objective() -> bool:
    res = evaluate_performance_claim({
        "must_id": "PD-CH5-011",
        "corpus_digest": "CORP-001",
        "sample_count": 200,
        "unit": "ms",
        "percentile": "p99",
        "objective_status": "OPEN",
    })
    return res.state == GateState.MISSING and res.must_id == "PD-CH5-011"


def probe_10_conforming_claim() -> bool:
    res = evaluate_performance_claim({
        "must_id": "PD-CH5-011",
        "corpus_digest": "CORP-001",
        "sample_count": 100,
        "unit": "ms",
        "percentile": "p99",
        "measured_evidence_ref": "EVID-001",
        "objective_status": "MEASURED",
    })
    return res.state == GateState.SATISFIED


PROBES = [
    ("Probe 1: No authority fails closed", probe_1_no_authority),
    ("Probe 2: Agent authority fails closed", probe_2_agent_authority),
    ("Probe 3: Unsupported latency promise returns MISSING[PD-CH5-004]", probe_3_unsupported_latency_promise),
    ("Probe 4: Missing measured corpus returns MISSING[PD-CH5-011]", probe_4_missing_corpus),
    ("Probe 5: Missing measured unit returns MISSING[PD-CH5-011]", probe_5_missing_unit),
    ("Probe 6: Missing percentile returns MISSING[PD-CH5-011]", probe_6_missing_percentile),
    ("Probe 7: Insufficient samples for p99 (<100) returns MISSING[PD-CH5-011]", probe_7_insufficient_samples_p99),
    ("Probe 8: Samples exceeding 100,000 cap returns MISSING[PD-CH5-011]", probe_8_samples_overflow_cap),
    ("Probe 9: Unmeasured OPEN objective returns MISSING[PD-CH5-011]", probe_9_unmeasured_open_objective),
    ("Probe 10: Conforming claim returns SATISFIED", probe_10_conforming_claim),
]


def main() -> int:
    print("=== Security & Fail-Closed Probes: Lane B2-METRICS-B ===")
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
