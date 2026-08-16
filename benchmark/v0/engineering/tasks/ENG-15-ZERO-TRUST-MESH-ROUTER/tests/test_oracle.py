import pytest
import target_module

def test_zero_trust_ingress():
    headers = {"X-Forwarded-Client-Cert-SAN": "spiffe://cluster.local/ns/prod/sa/payment-service"}
    res = target_module.route_request(headers, "/api/v1/charge")
    assert res["status"] == 200
    
    # Path denied
    with pytest.raises(PermissionError):
        target_module.route_request(headers, "/api/v1/unauthorized")
        
    # Unauthenticated identity
    with pytest.raises(PermissionError):
        target_module.route_request({}, "/api/v1/charge")
