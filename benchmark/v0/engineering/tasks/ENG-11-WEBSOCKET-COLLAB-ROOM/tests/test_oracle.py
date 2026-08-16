import pytest
from target_module import CollabDocument

def test_vector_clock_causality():
    doc = CollabDocument()
    assert doc.apply_update('client_A', {'client_A': 1}, "Version 1") is True
    assert doc.get_content() == "Version 1"
    
    # Stale update from client_A (version 1 again)
    assert doc.apply_update('client_A', {'client_A': 1}, "Stale Version") is False
    assert doc.get_content() == "Version 1"
