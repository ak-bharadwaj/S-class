from target_module import EngineModule37

def test_engine_37():
    e = EngineModule37()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
