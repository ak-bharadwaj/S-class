from target_module import ModuleV2_10, InvariantErr
import pytest
def test_m_l1():
    m = ModuleV2_10()
    assert m.check_invariant({'valid': True}) is True
    with pytest.raises(InvariantErr):
        m.check_invariant({'valid': False})
