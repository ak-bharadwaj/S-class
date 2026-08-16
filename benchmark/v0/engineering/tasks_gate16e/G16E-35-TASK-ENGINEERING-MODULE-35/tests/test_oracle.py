from target_module import EngineModule35

def test_engine_35():
    e = EngineModule35()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
