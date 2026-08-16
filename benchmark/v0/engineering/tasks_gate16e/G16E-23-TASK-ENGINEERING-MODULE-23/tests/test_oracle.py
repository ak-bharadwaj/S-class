from target_module import EngineModule23

def test_engine_23():
    e = EngineModule23()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
