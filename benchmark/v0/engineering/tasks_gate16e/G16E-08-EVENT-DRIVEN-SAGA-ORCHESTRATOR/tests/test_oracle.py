from target_module import SagaOrchestrator

def test_saga():
    s = SagaOrchestrator()
    s.add_step('step1', lambda d: d.update({'ok': True}), lambda d: None)
    res = s.execute({})
    assert res.get('status') == 'SUCCESS'
