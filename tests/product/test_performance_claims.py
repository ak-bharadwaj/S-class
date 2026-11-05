"""Tests for performance claims evaluation (PD-CH5-004, PD-CH5-011).

Validates:
- PD-CH5-004: Performance statements report measured units and corpus; unsupported latency promises return MISSING[PD-CH5-004].
- PD-CH5-011: Performance claims include measured corpus, sample count meeting policy-bound minimum (default 100 for p99), unit and percentile; unmeasured objectives remain OPEN.
"""
from __future__ import annotations

import math
from typing import Any, Dict

import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.performance_claims import (
    PerformanceClaim,
    PerformancePolicy,
    evaluate_performance_claim,
)


# ==============================================================================
# Normative Appendix F Fixture Tests
# ==============================================================================


def test_ch5_t4_unmeasured_performance_promise() -> None:
    """CH5-T4: Unmeasured latency promise returns MISSING[PD-CH5-004]."""
    fixture = {
        "claim": "p95 under 100 ms",
        "benchmark_corpus": "absent",
        "measurement_window": "absent",
        "expected_gate_output": "MISSING[PD-CH5-004]",
    }
    res = evaluate_performance_claim(fixture)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH5-004"
    assert str(res) == "MISSING[PD-CH5-004]"
    assert "Unsupported latency promise" in (res.detail or "")


def test_gaming_role_rejection() -> None:
    """Gaming role fixture fails closed even when measurements are valid (PD-CH5-011)."""
    gaming_fixture = {
        "must_id": "PD-CH5-011",
        "fixture_role": "gaming",
        "corpus_digest": "CORP-001",
        "sample_count": 500,
        "unit": "ms",
        "percentile": "p99",
        "measured_evidence_ref": "EVID-001",
    }
    res = evaluate_performance_claim(gaming_fixture)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH5-011"


def test_ch5_t15_gaming_fixture_pd_ch5_011() -> None:
    """CH5-T15: Gaming fixture testing missing unit, insufficient samples, and absent corpus."""
    fixture = {
        "must_id": "PD-CH5-011",
        "fixture_role": "gaming",
        "input_binding": "typed mismatch of one named digest-bound input per variant",
        "bound_inputs": ["corpus_digest", "sample_count", "unit", "percentile"],
        "attack_or_case": "Performance claims MUST include measured corpus, sample count meeting the policy-bound minimum, unit and percentile.",
        "expected_gate_output": "MISSING[PD-CH5-011]",
        "execution_evidence": "UNVERIFIED",
        "attack_variants": [
            {
                "id": "A1",
                "mutates": ["unit"],
                "op": "omit",
                "bypass": "unit omitted from a latency claim.",
                "expected_gate_output": "MISSING[PD-CH5-011]",
            },
            {
                "id": "A2",
                "mutates": ["sample_count"],
                "op": "forge",
                "bypass": "sample_count=3 for a p99 claim.",
                "expected_gate_output": "MISSING[PD-CH5-011]",
            },
            {
                "id": "A3",
                "mutates": ["corpus_digest"],
                "op": "omit",
                "bypass": "agent states a performance objective as met without measured corpus.",
                "expected_gate_output": "MISSING[PD-CH5-011]",
            },
        ],
    }
    res = evaluate_performance_claim(fixture)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH5-011"
    assert str(res) == "MISSING[PD-CH5-011]"

    # Test individual attack variants directly
    # Variant A1: unit omitted
    v1 = {
        "must_id": "PD-CH5-011",
        "corpus_digest": "CORP-001",
        "sample_count": 100,
        "percentile": "p99",
        "unit": None,
    }
    assert evaluate_performance_claim(v1).state == GateState.MISSING

    # Variant A2: sample_count=3 for p99 claim (<100 policy minimum)
    v2 = {
        "must_id": "PD-CH5-011",
        "corpus_digest": "CORP-001",
        "sample_count": 3,
        "percentile": "p99",
        "unit": "ms",
    }
    assert evaluate_performance_claim(v2).state == GateState.MISSING

    # Variant A3: corpus_digest omitted
    v3 = {
        "must_id": "PD-CH5-011",
        "corpus_digest": None,
        "sample_count": 100,
        "percentile": "p99",
        "unit": "ms",
    }
    assert evaluate_performance_claim(v3).state == GateState.MISSING


def test_ch5_t16_happy_fixture_pd_ch5_011() -> None:
    """CH5-T16: Happy fixture with all named inputs present and valid produces SATISFIED."""
    fixture = {
        "must_id": "PD-CH5-011",
        "fixture_role": "happy",
        "input_binding": "every named input present and digest-equal to the authorized baseline",
        "bound_inputs": ["corpus_digest", "sample_count", "unit", "percentile"],
        "baseline": "authorized baseline digests pinned by the F5 gate tuple; no variant mutates any bound input",
        "attack_or_case": "Conforming case, no violation present.",
        "expected_gate_output": "SATISFIED",
        "execution_evidence": "UNVERIFIED",
    }
    res = evaluate_performance_claim(fixture)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


# ==============================================================================
# Security, Boundary, and Policy Tests
# ==============================================================================


def test_no_injected_authority_fails_closed() -> None:
    """Evaluator without injected authority never returns SATISFIED."""
    valid_claim = {
        "must_id": "PD-CH5-011",
        "corpus_digest": "CORP-001",
        "sample_count": 500,
        "unit": "ms",
        "percentile": "p99",
        "measured_evidence_ref": "EVID-001",
        "objective_status": "MEASURED",
    }
    res_none = evaluate_performance_claim(valid_claim, caller_authority=None)
    assert res_none.state == GateState.MISSING

    res_agent = evaluate_performance_claim(valid_claim, caller_authority="AGENT")
    assert res_agent.state == GateState.MISSING


def test_sample_count_policy_bounds_and_overflow() -> None:
    """Validates sample count minimums and maximum 100,000 cap overflow behavior."""
    policy = PerformancePolicy()

    base_claim = {
        "must_id": "PD-CH5-011",
        "corpus_digest": "CORP-001",
        "unit": "ms",
        "percentile": "p99",
        "measured_evidence_ref": "EVID-001",
        "objective_status": "MEASURED",
    }

    # Under minimum (99 samples for p99)
    claim_under = dict(base_claim, sample_count=99)
    res_under = evaluate_performance_claim(claim_under, policy=policy)
    assert res_under.state == GateState.MISSING
    assert res_under.must_id == "PD-CH5-011"

    # Exactly minimum (100 samples for p99) -> SATISFIED
    claim_min = dict(base_claim, sample_count=100)
    res_min = evaluate_performance_claim(claim_min, policy=policy)
    assert res_min.state == GateState.SATISFIED

    # At policy cap (100,000 samples) -> SATISFIED
    claim_cap = dict(base_claim, sample_count=100_000)
    res_cap = evaluate_performance_claim(claim_cap, policy=policy)
    assert res_cap.state == GateState.SATISFIED

    # Overflow beyond cap (100,001 samples) -> MISSING
    claim_over = dict(base_claim, sample_count=100_001)
    res_over = evaluate_performance_claim(claim_over, policy=policy)
    assert res_over.state == GateState.MISSING
    assert res_over.must_id == "PD-CH5-011"


def test_unmeasured_objective_remains_open() -> None:
    """Unmeasured performance objective remains OPEN without bound evidence (PD-CH5-011)."""
    claim = {
        "must_id": "PD-CH5-011",
        "corpus_digest": "CORP-001",
        "sample_count": 200,
        "unit": "ms",
        "percentile": "p99",
        "objective_status": "OPEN",
    }
    res = evaluate_performance_claim(claim)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH5-011"


def test_malformed_empty_and_unhashable_inputs() -> None:
    """Malformed, wrong-type, unhashable, and NaN-like inputs fail closed."""
    for malformed in [None, [], 42, "string", {}, {"must_id": "PD-CH5-011"}]:
        res = evaluate_performance_claim(malformed)
        assert res.state == GateState.MISSING

    # Unhashable list in percentile
    bad_claim = {
        "must_id": "PD-CH5-011",
        "corpus_digest": "CORP-001",
        "sample_count": [1, 2],
        "unit": "ms",
        "percentile": {"p": 99},
    }
    assert evaluate_performance_claim(bad_claim).state == GateState.MISSING

    # Out of range percentile
    out_of_range = {
        "must_id": "PD-CH5-011",
        "corpus_digest": "CORP-001",
        "sample_count": 100,
        "unit": "ms",
        "percentile": 150.0,
    }
    assert evaluate_performance_claim(out_of_range).state == GateState.MISSING


def test_performance_claim_dataclass_evaluation() -> None:
    """Evaluation of immutable typed PerformanceClaim record."""
    pc = PerformanceClaim(
        claim_id="CLAIM-001",
        corpus_digest="CORP-HASH-123",
        sample_count=250,
        unit="ms",
        percentile=99.0,
        threshold=50.0,
        measurement_window="WINDOW-001",
        objective_status="MEASURED",
    )
    # Without measured evidence ref, OPEN objective remains OPEN
    res_open = evaluate_performance_claim(pc)
    assert res_open.state == GateState.MISSING

    # Conforming claim dict with baseline
    conforming = {
        "must_id": "PD-CH5-011",
        "corpus_digest": pc.corpus_digest,
        "sample_count": pc.sample_count,
        "unit": pc.unit,
        "percentile": pc.percentile,
        "baseline": "BASE-001",
        "expected_gate_output": "SATISFIED",
    }
    res_conf = evaluate_performance_claim(conforming)
    assert res_conf.state == GateState.SATISFIED
