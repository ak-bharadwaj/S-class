def compute_backoff(attempt): return min(2.0 ** attempt, 30.0)
