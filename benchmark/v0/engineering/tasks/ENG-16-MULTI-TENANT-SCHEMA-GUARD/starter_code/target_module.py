# target_module.py
class MultiTenantGuard:
    def __init__(self):
        pass
    def set_tenant(self, tenant_id: str):
        pass
    def sanitize_and_bind_query(self, raw_sql: str) -> str:
        pass
