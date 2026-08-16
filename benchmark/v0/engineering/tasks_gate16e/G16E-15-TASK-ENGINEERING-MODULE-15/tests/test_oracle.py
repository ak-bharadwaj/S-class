from target_module import EngineModule15

def test_engine_15():
    e = EngineModule15()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
