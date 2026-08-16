# target_module.py
def route_request(headers: dict, path: str) -> dict:
    return {"status": 200, "routed_path": path} # Flawed: bypasses mTLS SAN check and RBAC
