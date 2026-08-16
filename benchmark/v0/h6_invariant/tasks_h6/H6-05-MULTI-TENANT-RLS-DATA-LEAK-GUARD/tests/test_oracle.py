from target_module import MultiTenantRLSGuard, TenantIsolationViolation
import pytest

def test_tenant_rls():
    g = MultiTenantRLSGuard()
    sql = g.enforce_rls('SELECT * FROM orders', 'tenant_123')
    assert 'tenant_123' in sql
    with pytest.raises(TenantIsolationViolation):
        g.enforce_rls('SELECT * FROM orders', '')
