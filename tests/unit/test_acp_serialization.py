"""
Unit tests validating Agent Client Protocol (ACP) JSON-RPC 2.0 serialization.
"""
import json
import pytest

def build_acp_request(req_id: int, method: str, params: dict) -> str:
    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params
    }
    return json.dumps(payload)

def parse_acp_response(response_str: str) -> dict:
    data = json.loads(response_str)
    assert data.get("jsonrpc") == "2.0"
    return data

def test_acp_request_roundtrip():
    req_json = build_acp_request(1, "acp.session.initialize", {"workspace": "/project"})
    parsed = parse_acp_response(req_json)
    assert parsed["id"] == 1
    assert parsed["method"] == "acp.session.initialize"
    assert parsed["params"]["workspace"] == "/project"
