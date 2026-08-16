from target_module import EngineModule17

def test_engine_17():
    e = EngineModule17()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
