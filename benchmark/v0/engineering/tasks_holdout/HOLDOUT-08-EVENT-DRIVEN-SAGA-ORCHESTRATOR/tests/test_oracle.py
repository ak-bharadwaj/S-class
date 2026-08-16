from target_module import SagaOrchestrator

def test_saga_success():
    s = SagaOrchestrator()
    s.add_step('step1', lambda d: d.update({'s1': True}), lambda d: d.update({'s1_comp': True}))
    res = s.execute({})
    assert res.get('status') == 'SUCCESS'
