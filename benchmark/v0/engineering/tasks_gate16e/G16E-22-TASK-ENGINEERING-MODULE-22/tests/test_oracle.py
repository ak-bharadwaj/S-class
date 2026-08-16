from target_module import EngineModule22

def test_engine_22():
    e = EngineModule22()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
