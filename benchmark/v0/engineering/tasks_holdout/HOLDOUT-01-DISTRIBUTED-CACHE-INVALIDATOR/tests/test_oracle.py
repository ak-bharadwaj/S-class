from target_module import DistributedCacheInvalidator

def test_cache_set_get():
    c = DistributedCacheInvalidator('node-1')
    c.set('k1', 'v1', 1, 60)
    assert c.get('k1') == 'v1'

def test_invalidation_version():
    c1 = DistributedCacheInvalidator('node-1')
    c1.set('k1', 'v1', 1, 60)
    assert c1.invalidate('k1', 2) is True
    assert c1.get('k1') is None

def test_stale_invalidation_ignored():
    c1 = DistributedCacheInvalidator('node-1')
    c1.set('k1', 'v1', 5, 60)
    assert c1.invalidate('k1', 2) is False
    assert c1.get('k1') == 'v1'
