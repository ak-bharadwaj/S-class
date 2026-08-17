"""
S-Class EOS V11.2 - Gate 2 Phase 6: Differential Conformance Test Suite.
Directly executes the differential campaign corpus comparing ReferenceHypothesisAdapter vs CleanRoomPropertyEngine
under the IndependentDifferentialOracle.
Supported Python Versions: 3.10-3.13.
"""

import pytest
from benchmark.hypothesis_parity.differential_campaign_runner import run_differential_campaign, get_standard_differential_corpus
from benchmark.hypothesis_parity.reference_adapter import ReferenceHypothesisAdapter
from benchmark.hypothesis_parity.cleanroom_engine import CleanRoomPropertyEngine
from benchmark.hypothesis_parity.differential_oracle import IndependentDifferentialOracle
from benchmark.hypothesis_parity.observation import StrategySpec


def test_full_differential_campaign_passes_with_zero_discrepancies():
    """Runs the complete standard differential corpus and verifies 0 discrepancies."""
    report = run_differential_campaign(seed=12345)
    assert report["all_passed"] is True, f"Differential discrepancies detected: {report['discrepancies']}"
    assert report["total_discrepancies"] == 0
    assert report["total_campaign_cases"] >= 12


@pytest.mark.parametrize("case", get_standard_differential_corpus(), ids=lambda c: c["name"])
def test_individual_differential_case_conformance(case):
    """Verifies each differential case individually with independent oracle assertion."""
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


def test_differential_adversarial_nan_infinities_matrix():
    """Differential comparison on floating-point NaN and infinite boundary parameters."""
    specs = {
        "f": StrategySpec(strategy_type="floats", params={"min_value": -100.0, "max_value": 100.0, "allow_nan": False, "allow_infinity": False})
    }

    def finite_only_property(f: float) -> bool:
        import math
        assert not math.isnan(f) and not math.isinf(f), "Non-finite float generated"
        return True

    ref_obs = ReferenceHypothesisAdapter.run_campaign(specs, finite_only_property, max_examples=30, seed=42)
    cand_obs = CleanRoomPropertyEngine.run_campaign(specs, finite_only_property, max_examples=30, seed=42)

    verdict = IndependentDifferentialOracle.compare_observations(ref_obs, cand_obs, finite_only_property, specs)
    assert verdict.overall_status == "PASS"
    assert verdict.verdict_agreement is True
