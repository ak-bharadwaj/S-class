"""Test protocol contracts."""
import pytest
from sclass.contracts.protocol_contracts import RPCRequest, RPCResponse

def test_rpc_request_structure():
    req = RPCRequest(jsonrpc="2.0", id=1, method="tools/list", params={})
    assert req.jsonrpc == "2.0"
    assert req.method == "tools/list"

def test_rpc_response_success():
    resp = RPCResponse(jsonrpc="2.0", id=1, result={"tools": []})
    assert resp.result == {"tools": []}
    assert resp.error is None
