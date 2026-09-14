"""
S-Class Integrations: Base Adapter Capabilities, Universal Adapter Interface & Lifecycle Status.
Defines:
- AdapterStatus (SUPPORTED, INSTALLED, CONNECTED, VERIFIED)
- AdapterCapabilities
- PlatformAdapter (Protocol)
- BasePlatformAdapter (Concrete universal normalization base class)
"""

from __future__ import annotations
import os
import shutil
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Protocol, runtime_checkable

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.domain.capability import (
    CAP_TERMINAL_EXECUTE,
    CAP_FILESYSTEM_READ,
    CAP_FILESYSTEM_WRITE,
    CAP_NETWORK_REQUEST,
)
from sclass.domain.claim import Claim
from sclass.domain.verification import VerificationResult
from sclass.control.authorization import authorize
from sclass.verification.engine import verify_claim


class AdapterStatus(str, Enum):
    """Honest verification tiers for agent platform integrations."""
    SUPPORTED = "SUPPORTED"      # Adapter implementation exists
    INSTALLED = "INSTALLED"      # Client/agent binary detected on system
    CONNECTED = "CONNECTED"      # Protocol transport handshake succeeded
    VERIFIED = "VERIFIED"        # End-to-end integration tests have executed and passed


@dataclass(frozen=True)
class AdapterCapabilities:
    """Explicit declaration of capabilities provided by a platform adapter."""
    pre_action_enforcement: bool = True
    post_action_observation: bool = True
    approval: bool = True
    verification: bool = True
    session_events: bool = True
    native_protocol: str = "generic"  # "acp", "mcp", "cli", "native_hook", "generic"

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
            pre_action_enforcement=data.get("pre_action_enforcement", True),
            post_action_observation=data.get("post_action_observation", True),
            approval=data.get("approval", True),
            verification=data.get("verification", True),
            session_events=data.get("session_events", True),
            native_protocol=data.get("native_protocol", "generic"),
        )


@runtime_checkable
class PlatformAdapter(Protocol):
    """Universal protocol for host coding agent platform adapters."""

    @property
    def platform_id(self) -> str:
        """Unique identifier of the platform (e.g. codex, claude_code, cursor, antigravity)."""
        ...

    @property
    def status(self) -> AdapterStatus:
        """Current operational and installation status."""
        ...

    @property
    def capabilities(self) -> AdapterCapabilities:
        """Capabilities exposed by this adapter."""
        ...

    def normalize_action(
        self,
        action: str,
        target: str,
        parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
    ) -> ActionRequest:
        """Normalizes vendor-specific action requests into canonical S-Class ActionRequest."""
        ...

    def normalize_event(self, event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes vendor-specific lifecycle events into structured S-Class events."""
        ...

    def before_action(self, request: ActionRequest) -> AuthorizationDecision:
        """Pre-action enforcement hook."""
        ...

    def after_action(self, request: ActionRequest, result: Any) -> None:
        """Post-action observation and telemetry hook."""
        ...

    def evaluate_claim(self, claim: Claim, evidence: Any) -> VerificationResult:
        """Evaluates platform claims against independent verification engine."""
        ...


class BasePlatformAdapter(PlatformAdapter):
    """
    Universal base class for platform adapters.
    Provides canonical normalization and enforcement hooks.
    """

    def __init__(
        self,
        workspace_dir: str,
        platform_id: str = "generic",
        mode: str = "enforce",
        capabilities: Optional[AdapterCapabilities] = None,
    ):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self._platform_id = platform_id.strip().lower()
        self.mode = mode
        self._capabilities = capabilities or AdapterCapabilities()

    @property
    def platform_id(self) -> str:
        return self._platform_id

    @property
    def capabilities(self) -> AdapterCapabilities:
        return self._capabilities

    def inspect_status(self) -> AdapterStatus:
        """Probes local environment for platform presence."""
        bin_name = self._platform_id
        if shutil.which(bin_name):
            return AdapterStatus.INSTALLED
        home_path = os.path.expanduser(f"~/.{bin_name}")
        if os.path.exists(home_path):
            return AdapterStatus.INSTALLED
        return AdapterStatus.SUPPORTED

    @property
    def status(self) -> AdapterStatus:
        return self.inspect_status()

    def normalize_action(
        self,
        action: str,
        target: str,
        parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
    ) -> ActionRequest:
        """Maps diverse tool/action names to canonical S-Class capabilities."""
        act_lower = str(action).strip().lower()
        params = dict(parameters or {})
        ctx = dict(context or {})

        # Determine capability mapping
        if any(k in act_lower for k in ("command", "bash", "terminal", "exec", "sh", "shell", "run")):
            cap = CAP_TERMINAL_EXECUTE
        elif any(k in act_lower for k in ("read", "cat", "view", "get_file", "search", "list")):
            cap = CAP_FILESYSTEM_READ
        elif any(k in act_lower for k in ("write", "edit", "modify", "save", "delete", "rm", "patch")):
            cap = CAP_FILESYSTEM_WRITE
        elif any(k in act_lower for k in ("net", "http", "curl", "fetch", "download")):
            cap = CAP_NETWORK_REQUEST
        else:
            cap = CAP_TERMINAL_EXECUTE

        return ActionRequest(
            actor=self._platform_id,
            session=task_id or "",
            capability=cap,
            action=action,
            target=target,
            parameters=params,
            workspace=self.workspace_dir,
            context=ctx,
            provenance={"platform": self._platform_id, "adapter": self.__class__.__name__},
            agent=self._platform_id,
            platform=self._platform_id,
            tool=act_lower,
            task_id=task_id,
        )

    def normalize_event(self, event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Canonical event normalization."""
        return {
            "platform": self._platform_id,
            "event": f"{self._platform_id}.{event_name}",
            "payload": dict(payload),
            "status": "observed",
        }

    def before_action(self, request: ActionRequest) -> AuthorizationDecision:
        """Standard pre-action authorization enforcement."""
        return authorize(request, mode=self.mode, workspace_dir=self.workspace_dir)

    def after_action(self, request: ActionRequest, result: Any) -> None:
        """Standard post-action observation hook."""
        # Baseline observation recording without polluting verified state
        pass

    def evaluate_claim(self, claim: Claim, evidence: Any) -> VerificationResult:
        """Independent claim verification."""
        return verify_claim(claim, evidence, workspace_dir=self.workspace_dir)
