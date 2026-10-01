"""
ACP Request Router and Method Dispatcher.
"""
from typing import Callable, Dict, Any

class ACPRouter:
    def __init__(self):
        self.handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}

    def register_method(self, method_name: str, handler: Callable):
        self.handlers[method_name] = handler

    def dispatch(self, request: Dict[str, Any]) -> Dict[str, Any]:
        if request.get("jsonrpc") != "2.0":
            return {"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": -32600, "message": "Invalid JSON-RPC"}}
        
        method = request.get("method")
        if method not in self.handlers:
            return {"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": -32601, "message": f"Method {method} not found"}}
        
        result = self.handlers[method](request.get("params", {}))
        return {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
