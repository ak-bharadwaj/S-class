"""
S-Class Policy: Capability Registry and Resolver.
Authoritatively resolves granted capabilities for ActionRequests.
Enforces invariant: NO AUTHORITATIVE CAPABILITY -> NO EXECUTION.
"""

from __future__ import annotations
import os
from typing import List, Optional, Dict, Any

from sclass.domain.action import ActionRequest
from sclass.domain.capability import (
    Capability,
    CAP_TERMINAL_EXECUTE,
    CAP_FILESYSTEM_READ,
    CAP_FILESYSTEM_WRITE,
    CAP_GIT_READ,
    CAP_GIT_WRITE,
    CAP_PROCESS_SPAWN,
    CAP_NETWORK_REQUEST,
    CAP_SECRET_READ,
)


class CapabilityRegistry:
    """
    Authoritative registry of capabilities governing workspaces and actors.
    Provides strict lookup and resolution of granted capabilities.
    """

    def __init__(self, load_defaults: bool = True):
        self._capabilities: List[Capability] = []
        self._generation: int = 0
        if load_defaults:
            self._load_baseline_defaults()

    @property
    def generation(self) -> int:
        """Returns the current mutation generation counter of the registry."""
        return self._generation

    def _load_baseline_defaults(self) -> None:
        """Loads baseline default capabilities permitted for standard workspace operations."""
        self._capabilities.extend([
            Capability(
                id="cap:terminal.execute:baseline",
                version="1.0.0",
                actor="*",
                operation=CAP_TERMINAL_EXECUTE,
                resource="**",
                scope="workspace",
                risk="medium",
                duration=300.0,
                filesystem="read_write",
                network=False,
            ),
            Capability(
                id="cap:filesystem.read:baseline",
                version="1.0.0",
                actor="*",
                operation=CAP_FILESYSTEM_READ,
                resource="**",
                scope="workspace",
                risk="low",
                duration=60.0,
                filesystem="read",
                network=False,
            ),
            Capability(
                id="cap:filesystem.write:baseline",
                version="1.0.0",
                actor="*",
                operation=CAP_FILESYSTEM_WRITE,
                resource="**",
                scope="workspace",
                risk="medium",
                duration=300.0,
                filesystem="read_write",
                network=False,
            ),
            Capability(
                id="cap:git.read:baseline",
                version="1.0.0",
                actor="*",
                operation=CAP_GIT_READ,
                resource="**",
                scope="workspace",
                risk="low",
                duration=60.0,
                filesystem="read",
                network=False,
            ),
            Capability(
                id="cap:process.spawn:baseline",
                version="1.0.0",
                actor="*",
                operation=CAP_PROCESS_SPAWN,
                resource="**",
                scope="workspace",
                risk="medium",
                duration=120.0,
                filesystem="read_write",
                network=False,
            ),
        ])
        self._generation += 1

    def reload_defaults(self) -> None:
        """Clears registry and reloads baseline defaults, incrementing generation."""
        self.clear()
        self._load_baseline_defaults()

    def register(self, capability: Capability) -> None:
        """Registers an authoritative capability."""
        if not isinstance(capability, Capability):
            raise TypeError("capability must be an instance of Capability")
        self._capabilities.insert(0, capability)  # Prepend so custom capabilities take priority
        self._generation += 1

    def unregister(self, capability_id: str) -> bool:
        """Unregisters a capability by ID. Returns True if removed."""
        initial_len = len(self._capabilities)
        self._capabilities = [c for c in self._capabilities if c.id != capability_id]
        if len(self._capabilities) < initial_len:
            self._generation += 1
            return True
        return False

    def replace(self, old_capability_id: str, new_capability: Capability) -> bool:
        """Replaces a capability matching old_capability_id with new_capability."""
        if not isinstance(new_capability, Capability):
            raise TypeError("new_capability must be an instance of Capability")
        for i, cap in enumerate(self._capabilities):
            if cap.id == old_capability_id:
                self._capabilities[i] = new_capability
                self._generation += 1
                return True
        return False

    def get(self, capability_id: str) -> Optional[Capability]:
        """Gets a capability by ID."""
        for cap in self._capabilities:
            if cap.id == capability_id:
                return cap
        return None

    def clear(self) -> None:
        """Clears all capabilities from the registry."""
        self._capabilities.clear()
        self._generation += 1

    def get_capabilities(self) -> List[Capability]:
        """Returns a copy of all registered capabilities."""
        return list(self._capabilities)

    def resolve(
        self,
        request: ActionRequest,
        workspace_dir: str = "",
    ) -> Optional[Capability]:
        """
        Resolves the most specific authoritative capability matching the ActionRequest.
        Matches actor, operation, and resource constraints.
        Returns None if no capability grants this request.
        """
        if request is None:
            return None

        req_actor = getattr(request, "actor", None) or getattr(request, "agent", "unknown_actor")
        req_op = getattr(request, "capability", None) or getattr(request, "action", "")
        req_target = getattr(request, "target", "") or ""
        ws = os.path.abspath(workspace_dir or getattr(request, "workspace", "") or os.getcwd())

        exact_actor_matches: List[Capability] = []
        wildcard_actor_matches: List[Capability] = []

        for cap in self._capabilities:
            # 1. Check Operation match
            if not cap.allows_operation(req_op):
                continue

            # 2. Check Resource match
            if req_target and not cap.allows_resource(req_target, ws):
                continue

            # 3. Check Actor match
            if cap.actor == req_actor:
                exact_actor_matches.append(cap)
            elif cap.actor in ("*", "any"):
                wildcard_actor_matches.append(cap)

        if exact_actor_matches:
            return exact_actor_matches[0]
        if wildcard_actor_matches:
            return wildcard_actor_matches[0]

        return None


# Global default capability registry singleton
_GLOBAL_REGISTRY = CapabilityRegistry(load_defaults=True)


class CapabilityResolver:
    """Convenience helper resolving capabilities from global or custom registry."""

    @classmethod
    def get_global_registry(cls) -> CapabilityRegistry:
        return _GLOBAL_REGISTRY

    @classmethod
    def resolve(
        cls,
        request: ActionRequest,
        workspace_dir: str = "",
        registry: Optional[CapabilityRegistry] = None,
    ) -> Optional[Capability]:
        reg = registry or _GLOBAL_REGISTRY
        return reg.resolve(request, workspace_dir=workspace_dir)
