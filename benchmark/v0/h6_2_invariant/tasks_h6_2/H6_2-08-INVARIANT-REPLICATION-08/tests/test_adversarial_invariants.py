from target_module import ModuleV2_08, InvariantErr
import pytest
def test_m_l2():
    m = ModuleV2_08()
    with pytest.raises(InvariantErr):
        m.check_invariant(None) # None payload attack
