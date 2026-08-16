from target_module import DistributedCacheInvalidator

def test_cache_operations():
    c = DistributedCacheInvalidator()
    assert c.set('k1', 'v1', 1, 60) is True
    assert c.get('k1') == 'v1'
    assert c.invalidate('k1', 2) is True
    assert c.get('k1') is None
