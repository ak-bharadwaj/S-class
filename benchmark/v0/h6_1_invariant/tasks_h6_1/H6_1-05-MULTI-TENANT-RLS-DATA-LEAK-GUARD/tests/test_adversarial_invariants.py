from target_module import MultiTenantRLSGuard, TenantIsolationViolation
import pytest

def test_rls_adversarial_probes():
    g = MultiTenantRLSGuard()
    # Probe 1: SQL Injection tenant payload
    with pytest.raises(TenantIsolationViolation):
        g.enforce_rls('SELECT * FROM orders', "' OR '1'='1")
    # Probe 2: Whitespace empty tenant ID
    with pytest.raises(TenantIsolationViolation):
        g.enforce_rls('SELECT * FROM orders', '   ')
