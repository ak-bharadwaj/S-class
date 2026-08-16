from target_module import MultiTenantRLSV2, TenantViolation
import pytest
def test_rls_l2():
    m = MultiTenantRLSV2()
    with pytest.raises(TenantViolation):
        m.apply_rls('SELECT 1', "' OR '1'='1")
