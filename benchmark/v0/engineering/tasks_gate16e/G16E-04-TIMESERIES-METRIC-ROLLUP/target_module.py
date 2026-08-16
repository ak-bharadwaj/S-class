class TimeseriesRollupEngine:
    def __init__(self):
        pass

    def record(self, metric: str, value: float, timestamp: float):
        pass

    def query_rollup(self, metric: str, window_sec: int, agg_func: str = 'avg') -> float:
        pass
