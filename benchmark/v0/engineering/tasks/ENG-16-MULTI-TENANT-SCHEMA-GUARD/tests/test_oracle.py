import pytest
from target_module import MultiTenantGuard

def test_multi_tenant_isolation_guard():
    guard = MultiTenantGuard()
    
    # Missing tenant context error
    with pytest.raises(PermissionError):
        guard.sanitize_and_bind_query("SELECT * FROM orders")
        
    guard.set_tenant("tenant_abc")
    sql = guard.sanitize_and_bind_query("SELECT * FROM orders")
    assert "WHERE tenant_id = 'tenant_abc'" in sql
    
    # SQL injection attempt rejected
    with pytest.raises(ValueError):
        guard.sanitize_and_bind_query("SELECT * FROM orders; DROP TABLE users;")
