from target_module import MultiTenantRowGuard

def test_row_guard_tenant_isolation():
    g = MultiTenantRowGuard()
    g.set_context('tenant_A')
    assert g.validate_row({'tenant_id': 'tenant_A', 'data': 'ok'}) is True
    assert g.validate_row({'tenant_id': 'tenant_B', 'data': 'leak'}) is False
