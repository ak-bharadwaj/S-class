from target_module import EngineModule13

def test_engine_13():
    e = EngineModule13()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
