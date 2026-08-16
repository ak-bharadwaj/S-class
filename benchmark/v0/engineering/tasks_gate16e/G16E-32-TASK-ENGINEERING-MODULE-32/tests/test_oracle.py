from target_module import EngineModule32

def test_engine_32():
    e = EngineModule32()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
