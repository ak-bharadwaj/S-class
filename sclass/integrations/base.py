"""
S-Class Integrations: Base Adapter Capabilities and Honest Lifecycle Status.
Defines AdapterCapabilities and AdapterStatus (SUPPORTED, INSTALLED, CONNECTED, VERIFIED).
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


class AdapterStatus(str, Enum):
    """Honest verification tiers for agent platform integrations."""
    SUPPORTED = "SUPPORTED"      # Adapter implementation exists
    INSTALLED = "INSTALLED"      # Client/agent binary detected on system
    CONNECTED = "CONNECTED"      # Protocol transport handshake succeeded
    VERIFIED = "VERIFIED"        # End-to-end integration tests have executed and passed


@dataclass(frozen=True)
class AdapterCapabilities:
    """Explicit declaration of capabilities provided by a platform adapter."""
    pre_action_enforcement: bool
    post_action_observation: bool
    approval: bool
    verification: bool
    session_events: bool
    native_protocol: str  # "acp", "mcp", "cli", "native_hook"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pre_action_enforcement": self.pre_action_enforcement,
            "post_action_observation": self.post_action_observation,
            "approval": self.approval,
            "verification": self.verification,
            "session_events": self.session_events,
            "native_protocol": self.native_protocol,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AdapterCapabilities:
        return cls(
            pre_action_enforcement=data.get("pre_action_enforcement", False),
            post_action_observation=data.get("post_action_observation", False),
            approval=data.get("approval", False),
            verification=data.get("verification", False),
            session_events=data.get("session_events", False),
            native_protocol=data.get("native_protocol", "generic"),
        )
