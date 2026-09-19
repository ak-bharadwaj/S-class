"""Test benchmark contracts."""
import pytest
from sclass.contracts.benchmark_contracts import BenchmarkRunResult

def test_benchmark_run_result():
    res = BenchmarkRunResult(tier="T1", scenario_id="scen-01", wall_clock_ms=45.2, token_usage=120, verifications_passed=1, verifications_failed=0, net_benefit_score=0.98)
    assert res.tier == "T1"
    assert res.net_benefit_score > 0.9
