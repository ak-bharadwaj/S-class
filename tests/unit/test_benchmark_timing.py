"""
Unit tests validating benchmark timing probe precision and observable metrics.
"""
import pytest
import time
from sclass.benchmarks.fixtures.t1_trivial import T1TrivialBenchmark

def test_t1_benchmark_timing_and_replacement():
    harness = T1TrivialBenchmark("def greeting(): return 'hello'")
    res = harness.apply_edit("'hello'", "'world'")
    assert res["tier"] == "T1"
    assert res["success"] is True
    assert res["elapsed_us"] >= 0.0

def test_t1_benchmark_no_change():
    harness = T1TrivialBenchmark("constant = 42")
    res = harness.apply_edit("nonexistent", "foo")
    assert res["success"] is False
