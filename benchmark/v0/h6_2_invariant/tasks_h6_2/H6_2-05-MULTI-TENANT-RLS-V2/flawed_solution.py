class TenantViolation(Exception): pass
class MultiTenantRLSV2:
    def apply_rls(self, query: str, tenant_id: str) -> str:
        return f"{query} WHERE tenant_id = '{tenant_id}'" # Flawed: SQL injection leak
