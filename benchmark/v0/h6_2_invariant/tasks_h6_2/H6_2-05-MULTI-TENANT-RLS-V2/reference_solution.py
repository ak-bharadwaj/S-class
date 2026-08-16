class TenantViolation(Exception): pass
class MultiTenantRLSV2:
    def apply_rls(self, query: str, tenant_id: str) -> str:
        if not tenant_id or "'" in tenant_id or "--" in tenant_id:
            raise TenantViolation('Invalid tenant')
        return f"{query} WHERE tenant_id = '{tenant_id}'"
