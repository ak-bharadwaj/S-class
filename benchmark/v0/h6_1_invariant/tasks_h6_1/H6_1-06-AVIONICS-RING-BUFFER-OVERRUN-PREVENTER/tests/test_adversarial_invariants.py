from target_module import AvionicsRingBufferGuard

def test_avionics_adversarial_probes():
    b = AvionicsRingBufferGuard(capacity=2)
    # Probe 1: Overrun by 5 frames
    for i in range(7):
        b.push({'f': i})
    assert b.overrun_count == 5
    assert len(b.buffer) <= 2
    # Probe 2: Pop remaining capacity
    f1 = b.pop()
    f2 = b.pop()
    assert f1['f'] == 5 and f2['f'] == 6
