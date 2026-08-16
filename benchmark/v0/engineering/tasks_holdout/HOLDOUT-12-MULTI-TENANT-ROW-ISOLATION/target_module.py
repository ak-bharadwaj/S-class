class MultiTenantRowGuard:
    def __init__(self):
        pass

    def set_context(self, tenant_id: str):
        pass

    def sanitize_query(self, sql_str: str) -> str:
        pass

    def validate_row(self, row_dict: dict) -> bool:
        pass
