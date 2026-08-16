from target_module import EngineModule18

def test_engine_18():
    e = EngineModule18()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
