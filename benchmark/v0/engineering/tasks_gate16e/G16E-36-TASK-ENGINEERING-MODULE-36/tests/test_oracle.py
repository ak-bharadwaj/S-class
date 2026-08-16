from target_module import EngineModule36

def test_engine_36():
    e = EngineModule36()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
