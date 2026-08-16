from target_module import EngineModule20

def test_engine_20():
    e = EngineModule20()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
