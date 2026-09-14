"""
S-Class Execution: Execution Provider Registry.
Authoritative registry for execution providers with fail-closed resolution.
Decouples policy evaluation from execution isolation mechanisms.
"""

from __future__ import annotations
import os
from typing import Dict, Any, List, Optional, Union

from sclass.domain.action import ActionRequest
from sclass.execution.base import ExecutionProvider, ProviderCapabilities, ProviderHealth
from sclass.execution.native import NativeProcessProvider
from sclass.execution.isolated import (
    BubblewrapProvider,
    OCIProvider,
    GVisorProvider,
    DaggerProvider,
    IsolatedSandboxProvider,
)
from sclass.core.errors import SecurityViolationError


class ExecutionProviderRegistry:
    """
    Authoritative registry mapping provider names to ExecutionProvider instances.
    Enforces fail-closed resolution: unknown providers are rejected immediately.
    """

    def __init__(self):
        self._providers: Dict[str, ExecutionProvider] = {}
        self._aliases: Dict[str, str] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Registers canonical built-in execution providers."""
        native = NativeProcessProvider()
        self.register("native", native, aliases=["host", "direct"])

        bubblewrap = BubblewrapProvider()
        self.register("bubblewrap", bubblewrap, aliases=["bwrap"])

        oci = OCIProvider()
        self.register("oci", oci, aliases=["container", "docker", "podman"])

        gvisor = GVisorProvider()
        self.register("gvisor", gvisor, aliases=["runsc"])

        dagger = DaggerProvider()
        self.register("dagger", dagger, aliases=[])

        sandbox = IsolatedSandboxProvider()
        self.register("sandbox", sandbox, aliases=["isolated", "auto"])

    def register(
        self,
        name: str,
        provider: ExecutionProvider,
        aliases: Optional[List[str]] = None,
    ) -> None:
        """Registers an execution provider under canonical name and optional aliases."""
        clean_name = name.lower().strip()
        self._providers[clean_name] = provider
        if aliases:
            for alias in aliases:
                self._aliases[alias.lower().strip()] = clean_name

    def has(self, name: str) -> bool:
        """Returns True if provider or alias is registered."""
        clean = name.lower().strip()
        return clean in self._providers or clean in self._aliases

    def get(self, name: str) -> ExecutionProvider:
        """
        Retrieves requested provider by name or alias.
        Fails closed with SecurityViolationError if provider is unknown.
        """
        clean = name.lower().strip()
        target_name = self._aliases.get(clean, clean)
        if target_name in self._providers:
            return self._providers[target_name]

        raise SecurityViolationError(
            f"UNKNOWN PROVIDER -> NO EXECUTION: Execution provider '{name}' is not registered. "
            "Fail-closed policy strictly prohibits execution under unrecognized providers."
        )

    def list_providers(self) -> List[str]:
        """Returns list of all registered primary provider names."""
        return sorted(list(self._providers.keys()))

    def list_available_providers(self) -> List[str]:
        """Returns list of registered providers whose required runtimes are available on this host."""
        return sorted([name for name, p in self._providers.items() if p.is_available()])

    def inspect_all(self) -> Dict[str, Dict[str, Any]]:
        """Introspects capabilities across all registered providers."""
        return {name: p.inspect_capabilities().to_dict() for name, p in self._providers.items()}

    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Runs health checks across all registered providers."""
        return {name: p.health_check().to_dict() for name, p in self._providers.items()}

    def resolve(
        self,
        name: Optional[str] = None,
        require_isolation: bool = False,
        request: Optional[ActionRequest] = None,
    ) -> ExecutionProvider:
        """
        Resolves the appropriate execution provider enforcing isolation requirements.
        If require_isolation is True, rejects uncontained host providers.
        """
        chosen_name = name
        if not chosen_name:
            if request and hasattr(request, "context") and isinstance(request.context, dict):
                chosen_name = request.context.get("execution_provider")

        if not chosen_name:
            chosen_name = "sandbox" if require_isolation else "native"

        provider = self.get(chosen_name)

        if require_isolation:
            if provider.provider_type == "host":
                raise SecurityViolationError(
                    f"INSUFFICIENT ISOLATION: Requested provider '{provider.name}' is uncontained host execution, "
                    "but task security requirements mandate sandbox or container isolation."
                )
            if not provider.is_available():
                raise SecurityViolationError(
                    f"NO SANDBOX -> NO SANDBOXED EXECUTION: Requested isolation provider '{provider.name}' "
                    "is not available on this host. Fail-closed policy denies degrading to host execution."
                )

        return provider


_GLOBAL_REGISTRY: Optional[ExecutionProviderRegistry] = None


def get_provider_registry() -> ExecutionProviderRegistry:
    """Returns singleton ExecutionProviderRegistry."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = ExecutionProviderRegistry()
    return _GLOBAL_REGISTRY


def reset_provider_registry() -> ExecutionProviderRegistry:
    """Resets global registry to default state."""
    global _GLOBAL_REGISTRY
    _GLOBAL_REGISTRY = ExecutionProviderRegistry()
    return _GLOBAL_REGISTRY


def get_execution_provider(name: str = "native") -> ExecutionProvider:
    """Convenience getter for resolving an ExecutionProvider by name."""
    return get_provider_registry().get(name)
