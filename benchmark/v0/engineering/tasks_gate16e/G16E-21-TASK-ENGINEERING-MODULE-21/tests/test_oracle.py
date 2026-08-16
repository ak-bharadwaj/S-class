from target_module import EngineModule21

def test_engine_21():
    e = EngineModule21()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
