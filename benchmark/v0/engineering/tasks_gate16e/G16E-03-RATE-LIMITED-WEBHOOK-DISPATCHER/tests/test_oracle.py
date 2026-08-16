from target_module import RateLimitedWebhookDispatcher

def test_dispatcher():
    d = RateLimitedWebhookDispatcher(max_rps=10)
    wid = d.dispatch('https://example.com/webhook', {'event': 'ping'})
    assert wid is not None
    assert d.get_status(wid) in ['queued', 'delivered', 'pending']
