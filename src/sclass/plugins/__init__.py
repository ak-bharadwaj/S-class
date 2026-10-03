"""S-Class Plugin and Extension Model.

Per §14.6: Plugins declare capabilities and required effect scopes.
Activation does NOT grant authority; all plugin executions remain subject
to D3 policy and D5/D6 ExecutionGate authorization.
"""

from sclass.plugins.manifest import PluginManifest, PluginRegistry

__all__ = [
    "PluginManifest",
    "PluginRegistry",
]
