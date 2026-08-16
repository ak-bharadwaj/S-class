from target_module import RateLimitedWebhookDispatcher

def test_dispatch_queue():
    d = RateLimitedWebhookDispatcher(max_rps=10)
    wid = d.dispatch('https://api.example.com/hook', {'event': 'ping'})
    assert wid is not None
    assert d.get_status(wid) in ['queued', 'pending', 'delivered']

def test_process_queue():
    d = RateLimitedWebhookDispatcher(max_rps=10)
    wid = d.dispatch('https://api.example.com/hook', {'event': 'test'})
    delivered = d.process_queue()
    assert delivered >= 0
