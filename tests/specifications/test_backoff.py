from sclass.fleet.backoff import compute_backoff
def test_backoff(): assert compute_backoff(3) == 8.0
