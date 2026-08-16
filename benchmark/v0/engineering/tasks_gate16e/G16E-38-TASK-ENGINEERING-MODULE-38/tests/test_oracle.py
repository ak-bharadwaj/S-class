from target_module import EngineModule38

def test_engine_38():
    e = EngineModule38()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
