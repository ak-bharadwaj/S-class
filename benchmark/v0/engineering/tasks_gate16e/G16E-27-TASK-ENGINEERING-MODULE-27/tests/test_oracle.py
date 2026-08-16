from target_module import EngineModule27

def test_engine_27():
    e = EngineModule27()
    assert e.get_status() == 'ready'
    res = e.process({'input': 123})
    assert res.get('status') == 'success'
