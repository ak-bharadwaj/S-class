"""Agent Client Protocol (ACP) Interop Bridge.

Provides JSON-RPC messaging format for agent-editor communications.
Per 02-OSS map: ACP messages are strictly transport inputs/observations;
they do not hold canonical authority or bypass ExecutionGate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ACPMessage:
    jsonrpc: str
    id: str | int | None
    method: str | None
    params: dict[str, Any] | None
    result: Any | None = None
    error: dict[str, Any] | None = None


class ACPBridge:
    """Encodes and decodes Agent Client Protocol messages."""

    @staticmethod
    def create_request(request_id: str | int, method: str, params: dict[str, Any]) -> str:
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        return json.dumps(payload)

    @staticmethod
    def create_response(request_id: str | int, result: Any) -> str:
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }
        return json.dumps(payload)

    @staticmethod
    def parse_message(raw_json: str) -> ACPMessage:
        data = json.loads(raw_json)
        return ACPMessage(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error"),
        )
