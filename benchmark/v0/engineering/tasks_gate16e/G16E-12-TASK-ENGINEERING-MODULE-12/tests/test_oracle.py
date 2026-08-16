from target_module import EngineModule12

def test_engine_12():
    e = EngineModule12()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
