from target_module import EngineModule40

def test_engine_40():
    e = EngineModule40()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
