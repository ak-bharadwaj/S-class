from target_module import TimeseriesRollupEngine

def test_rollup_avg():
    e = TimeseriesRollupEngine()
    e.record('cpu', 10.0, 100.0)
    e.record('cpu', 20.0, 110.0)
    e.record('cpu', 30.0, 120.0)
    assert e.query_rollup('cpu', 30, 'avg') == 20.0
    assert e.query_rollup('cpu', 30, 'max') == 30.0
