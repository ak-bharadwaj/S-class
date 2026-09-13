"""
S-Class ACP Integration: Protocol Version Compatibility & Negotiation.
Handles wire-compatibility negotiation separate from schema artifact versions.
ACP identifies protocol version 'v1' (and aliases '2026-07-28', '2025-01-01', '2024-11-05').
"""

from __future__ import annotations
from typing import Tuple, Optional, Dict, Any

from sclass.integrations.acp.schema import (
    SUPPORTED_PROTOCOL_VERSIONS,
    DEFAULT_PROTOCOL_VERSION,
)


class ACPCompatibility:
    """Protocol version negotiator and compatibility validator for ACP connections."""

    SUPPORTED = SUPPORTED_PROTOCOL_VERSIONS
    DEFAULT = DEFAULT_PROTOCOL_VERSION

    @classmethod
    def negotiate_version(cls, client_requested_version: Optional[str]) -> Tuple[bool, str, Optional[str]]:
        """
        Negotiates protocol version between client and S-Class server.
        Returns:
            (is_compatible, selected_version, error_message)
        """
        if not client_requested_version:
            return True, cls.DEFAULT, None

        req = client_requested_version.strip().lower()

        # Handle 'v1' canonical identifier or date-based specifications
        if req in ("v1", "1", "1.0"):
            return True, cls.DEFAULT, None

        for supported in cls.SUPPORTED:
            if req == supported.lower():
                return True, supported, None

        # If requesting an unsupported newer or unrecognized version, fail closed
        return (
            False,
            cls.DEFAULT,
            f"Unsupported ACP protocol version '{client_requested_version}'. Supported versions: {list(cls.SUPPORTED)}",
        )

    @classmethod
    def get_server_capabilities(cls) -> Dict[str, Any]:
        """Returns authoritative S-Class ACP server capabilities."""
        return {
            "protocol_version": cls.DEFAULT,
            "supported_versions": list(cls.SUPPORTED),
            "streaming": True,
            "cancellation": True,
            "authorization": True,
            "session_forking": True,
            "session_resumption": True,
            "filesystem_gateway": True,
            "terminal_gateway": True,
            "verification_adjudication": True,
        }
