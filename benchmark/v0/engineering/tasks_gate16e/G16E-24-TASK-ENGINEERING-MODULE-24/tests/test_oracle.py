from target_module import EngineModule24

def test_engine_24():
    e = EngineModule24()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
