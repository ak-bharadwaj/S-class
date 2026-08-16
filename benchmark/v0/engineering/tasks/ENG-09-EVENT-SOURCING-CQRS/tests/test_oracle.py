import pytest
from target_module import EventStore

def test_cqrs_event_sourcing():
    es = EventStore()
    es.append('acc_1', 'CREATED', {}, 0)
    es.append('acc_1', 'DEPOSITED', {'amount': 500}, 1)
    
    proj = es.get_projection('acc_1')
    assert proj['status'] == 'ACTIVE'
    assert proj['balance'] == 500
    
    with pytest.raises(ValueError):
        es.append('acc_1', 'DEPOSITED', {'amount': 100}, 1) # Wrong version
