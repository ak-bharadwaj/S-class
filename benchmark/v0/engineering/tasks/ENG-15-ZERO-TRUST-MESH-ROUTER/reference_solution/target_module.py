# target_module.py
RBAC_POLICY = {
    "spiffe://cluster.local/ns/prod/sa/payment-service": ["/api/v1/charge", "/api/v1/refund"],
    "spiffe://cluster.local/ns/prod/sa/frontend": ["/api/v1/status"]
}

def route_request(headers: dict, path: str) -> dict:
    mtls_san = headers.get("X-Forwarded-Client-Cert-SAN")
    if not mtls_san or not mtls_san.startswith("spiffe://"):
        raise PermissionError("mTLS client SAN missing or invalid")
        
    allowed_paths = RBAC_POLICY.get(mtls_san, [])
    if path not in allowed_paths:
        raise PermissionError(f"Access denied to path {path} for identity {mtls_san}")
        
    return {"status": 200, "routed_path": path, "identity": mtls_san}
