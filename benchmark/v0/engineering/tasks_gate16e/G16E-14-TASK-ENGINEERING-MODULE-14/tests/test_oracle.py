from target_module import EngineModule14

def test_engine_14():
    e = EngineModule14()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
