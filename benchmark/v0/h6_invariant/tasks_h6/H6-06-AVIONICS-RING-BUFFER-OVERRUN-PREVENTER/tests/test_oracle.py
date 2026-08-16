from target_module import AvionicsRingBufferGuard

def test_avionics_buffer():
    b = AvionicsRingBufferGuard(capacity=2)
    b.push({'f': 1})
    b.push({'f': 2})
    b.push({'f': 3})
    assert b.overrun_count == 1
    assert b.pop()['f'] == 2
