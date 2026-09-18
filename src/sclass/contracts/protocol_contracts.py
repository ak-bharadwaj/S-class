"""Protocol contracts for ACP and MCP communication."""
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass(frozen=True)
class RPCRequest:
    jsonrpc: str
    id: int
    method: str
    params: Dict[str, Any]

@dataclass(frozen=True)
class RPCResponse:
    jsonrpc: str
    id: int
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
