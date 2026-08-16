import pytest
from target_module import BlackboxBuffer

def test_parity_and_ring_capacity():
    bb = BlackboxBuffer(capacity=2)
    # Odd parity words: 0b1 (1 bit), 0b111 (3 bits)
    assert bb.record(0b1) is True
    assert bb.record(0b111) is True
    assert len(bb.get_records()) == 2
    # Overwrite test
    assert bb.record(0b1011) is True # 3 bits
    records = bb.get_records()
    assert len(records) == 2
    assert records == [0b111, 0b1011]

    # Even parity (invalid: 0b11 = 2 bits)
    with pytest.raises(ValueError):
        bb.record(0b11)
