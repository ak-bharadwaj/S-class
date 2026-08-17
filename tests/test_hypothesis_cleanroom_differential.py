"""
S-Class EOS V11.2 - Gate 2 Phase 6: Comprehensive Differential Conformance Test Suite.
Directly executes the standard, boundary, and property-based meta-spec differential campaigns
comparing ReferenceHypothesisAdapter vs CleanRoomPropertyEngine under the IndependentDifferentialOracle.
Supported Python Versions: 3.10-3.13.
"""

import pytest
from benchmark.hypothesis_parity.differential_campaign_runner import (
    run_differential_campaign,
    get_standard_differential_corpus,
    get_boundary_differential_corpus,
    run_generated_meta_fuzz_differential_campaign
)
from benchmark.hypothesis_parity.reference_adapter import ReferenceHypothesisAdapter
from benchmark.hypothesis_parity.cleanroom_engine import CleanRoomPropertyEngine
from benchmark.hypothesis_parity.differential_oracle import IndependentDifferentialOracle
from benchmark.hypothesis_parity.observation import StrategySpec


def test_full_differential_campaign_canonical_and_boundary_zero_discrepancies():
    """Runs the 21-case canonical and boundary differential corpus and verifies 0 discrepancies."""
    report = run_differential_campaign(seed=12345, suppress_health_checks=True)
    assert report["all_passed"] is True, f"Differential discrepancies detected: {report['discrepancies']}"
    assert report["total_discrepancies"] == 0
    assert report["total_campaign_cases"] == 21


def test_differential_meta_fuzz_property_based_campaign():
    """Runs the property-based meta-spec differential campaign."""
    report = run_generated_meta_fuzz_differential_campaign(iterations_per_seed=25, seeds=[42, 1337])
    assert report["all_passed"] is True, f"Meta-fuzz differential discrepancies: {report['discrepancies']}"
    assert report["total_discrepancies"] == 0


@pytest.mark.parametrize("case", get_standard_differential_corpus() + get_boundary_differential_corpus(), ids=lambda c: c["name"])
def test_individual_differential_case_conformance(case):
    """Verifies each canonical and boundary differential case individually."""
    specs = case["specs"]
    prop = case["property"]
    max_ex = case.get("max_examples", 30)

    ref_obs = ReferenceHypothesisAdapter.run_campaign(specs, prop, max_examples=max_ex, seed=42, suppress_health_checks=True)
    cand_obs = CleanRoomPropertyEngine.run_campaign(specs, prop, max_examples=max_ex, seed=42)

    verdict = IndependentDifferentialOracle.compare_observations(ref_obs, cand_obs, prop, specs)
    assert verdict.overall_status == "PASS", f"Differential failure on case '{case['name']}': {verdict.violations}"
    assert verdict.verdict_agreement is True
    assert verdict.reference_valid is True
    assert verdict.candidate_valid is True


def test_differential_health_check_duality():
    """
    Verifies behavior under both health check modes:
    A. Normal health check mode: impossible/extreme filter triggers structured error in both frameworks.
    B. Suppressed health check mode: feasible filter executes diagnostics cleanly.
    """
    # Mode A: Strict / Extreme filter exhaustion
    extreme_specs = {
        "x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 100000}, filter_fn=lambda x: x == 999999)
    }
    ref_obs_strict = ReferenceHypothesisAdapter.run_campaign(extreme_specs, lambda x: True, max_examples=10, seed=42, suppress_health_checks=False)
    cand_obs_strict = CleanRoomPropertyEngine.run_campaign(extreme_specs, lambda x: True, max_examples=10, seed=42)
    assert ref_obs_strict.verdict == "ERROR"
    assert cand_obs_strict.verdict == "ERROR"
    assert cand_obs_strict.exception_class == "FilterExhaustion"

    # Mode B: Suppressed / Diagnostic feasible filter
    feasible_specs = {
        "x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 1000}, filter_fn=lambda x: x % 10 == 0)
    }
    ref_obs_supp = ReferenceHypothesisAdapter.run_campaign(feasible_specs, lambda x: True, max_examples=15, seed=42, suppress_health_checks=True)
    cand_obs_supp = CleanRoomPropertyEngine.run_campaign(feasible_specs, lambda x: True, max_examples=15, seed=42)

    verdict = IndependentDifferentialOracle.compare_observations(ref_obs_supp, cand_obs_supp, lambda x: True, feasible_specs)
    assert verdict.overall_status == "PASS"
    assert verdict.verdict_agreement is True
