"""
S-Class EOS V11.2 - D6 Execution Provider Interface & Registry.
"""

from __future__ import annotations
from typing import Mapping, Optional, Sequence, Protocol, runtime_checkable, Dict
from controller.token import ActionBinding, ExecutionContext
from execution.workspace import IsolatedWorkspace


@runtime_checkable
class D6ExecutionProvider(Protocol):
    """Protocol for D6 execution providers that build bounded process commands."""

    @property
    def provider_id(self) -> str:
        ...

    @property
    def supported_action_types(self) -> Sequence[str]:
        ...

    @property
    def required_capabilities(self) -> Sequence[str]:
        ...

    def build_command(
        self,
        action_binding: ActionBinding,
        workspace: IsolatedWorkspace,
        context: ExecutionContext,
    ) -> Sequence[str]:
        """Builds the argv command sequence to execute."""
        ...


class D6ProviderRegistry:
    """Registry and resolver for D6 execution providers."""

    def __init__(self):
        self._providers: Dict[str, D6ExecutionProvider] = {}

    def register(self, provider: D6ExecutionProvider) -> None:
        if not isinstance(provider, D6ExecutionProvider):
            raise TypeError("provider must implement D6ExecutionProvider protocol.")
        self._providers[provider.provider_id] = provider

    def resolve(self, provider_id: str) -> Optional[D6ExecutionProvider]:
        return self._providers.get(provider_id)

    def list_providers(self) -> Sequence[str]:
        return tuple(self._providers.keys())
