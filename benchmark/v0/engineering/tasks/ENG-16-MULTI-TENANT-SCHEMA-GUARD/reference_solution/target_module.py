# target_module.py
import re

class MultiTenantGuard:
    def __init__(self):
        self.active_tenant = None

    def set_tenant(self, tenant_id: str):
        if not tenant_id or not re.match(r"^[a-zA-Z0-9_-]+$", tenant_id):
            raise ValueError("Invalid tenant ID format")
        self.active_tenant = tenant_id

    def sanitize_and_bind_query(self, raw_sql: str) -> str:
        if not self.active_tenant:
            raise PermissionError("Missing active tenant context")
            
        # SQL injection guard
        if ";" in raw_sql or "--" in raw_sql or "/*" in raw_sql:
            raise ValueError("Potential SQL injection detected")
            
        clean_sql = raw_sql.strip()
        if "WHERE" in clean_sql.upper():
            bound_sql = re.sub(r"(?i)WHERE\s+", f"WHERE tenant_id = '{self.active_tenant}' AND (", clean_sql) + ")"
        else:
            bound_sql = f"{clean_sql} WHERE tenant_id = '{self.active_tenant}'"
            
        return bound_sql
