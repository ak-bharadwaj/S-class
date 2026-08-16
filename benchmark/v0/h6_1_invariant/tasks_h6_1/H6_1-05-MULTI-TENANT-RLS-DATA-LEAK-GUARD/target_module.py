class TenantIsolationViolation(Exception): pass

class MultiTenantRLSGuard:
    def enforce_rls(self, sql_query: str, tenant_id: str) -> str:
        pass
