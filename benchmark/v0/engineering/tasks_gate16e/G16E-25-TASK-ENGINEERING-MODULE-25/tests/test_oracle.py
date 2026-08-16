from target_module import EngineModule25

def test_engine_25():
    e = EngineModule25()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
