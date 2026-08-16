from target_module import EngineModule28

def test_engine_28():
    e = EngineModule28()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
