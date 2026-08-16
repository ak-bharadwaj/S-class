from target_module import MultiTenantRLSV2
def test_rls_l1():
    m = MultiTenantRLSV2()
    assert 'tenant_1' in m.apply_rls('SELECT 1', 'tenant_1')
