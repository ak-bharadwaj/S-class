"""
S-Class ACP Integration: Official Protocol Transport Layer.
Implements JSON-RPC 2.0 message framing, parsing, serialization, and error generation
for Agent Client Protocol (ACP) v1 connections.
"""

from __future__ import annotations
import json
import uuid
from typing import Dict, Any, Optional, Union, Tuple

from sclass.integrations.acp.schema import (
    ACPMessage,
    ACPRequest,
    ACPResponse,
    ACPNotification,
    ACPErrorData,
)


class ACPTransport:
    """Authoritative protocol transport parser and message builder for ACP v1."""

    @classmethod
    def parse_message(cls, raw: Union[str, bytes, Dict[str, Any]]) -> ACPMessage:
        """
        Parses raw payload into ACPRequest, ACPNotification, or ACPResponse.
        """
        if isinstance(raw, (str, bytes)):
            try:
                data = json.loads(raw)
            except Exception as e:
                raise ValueError(f"Invalid JSON payload: {e}")
        elif isinstance(raw, dict):
            data = raw
        else:
            raise ValueError(f"Unsupported payload type: {type(raw)}")

        if not isinstance(data, dict):
            raise ValueError("Payload must be a JSON object.")

        if data.get("jsonrpc") != "2.0":
            raise ValueError("Invalid JSON-RPC protocol version. Expected '2.0'.")

        # Check if response
        if "result" in data or "error" in data:
            return ACPResponse.model_validate(data)

        # Check if request or notification
        if "id" in data:
            return ACPRequest.model_validate(data)
        elif "method" in data:
            return ACPNotification.model_validate(data)

        raise ValueError("Malformed JSON-RPC message: missing 'id' or 'method'.")

    @classmethod
    def build_response(
        cls,
        request_id: Optional[Union[str, int]],
        result: Any = None,
    ) -> Dict[str, Any]:
        """Builds a successful ACP JSON-RPC 2.0 response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    @classmethod
    def build_error_response(
        cls,
        request_id: Optional[Union[str, int]],
        code: int,
        message: str,
        data: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Builds a standardized ACP JSON-RPC 2.0 error response."""
        err_payload: Dict[str, Any] = {
            "code": code,
            "message": message,
        }
        if data is not None:
            err_payload["data"] = data

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": err_payload,
        }

    @classmethod
    def serialize_message(cls, message: Union[Dict[str, Any], ACPMessage]) -> str:
        """Serializes message to JSON string."""
        if isinstance(message, ACPMessage):
            return message.model_dump_json()
        return json.dumps(message, ensure_ascii=False)
