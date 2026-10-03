"""Plugin Manifest and Capability Registration (plugins/manifest.py).

Defines plugin manifests and registers declared capabilities without granting
autonomous execution authority.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PluginManifest:
    name: str
    version: str
    description: str
    capabilities: tuple[str, ...]
    required_effects: tuple[str, ...]
    entrypoint: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginManifest:
        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            capabilities=tuple(data.get("capabilities", [])),
            required_effects=tuple(data.get("required_effects", [])),
            entrypoint=data.get("entrypoint", ""),
            metadata=data.get("metadata", {}),
        )


class PluginRegistry:
    """Discovers and registers plugins from workspace and declared directories."""

    def __init__(self, workspace_root: Path | str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self._plugins: dict[str, PluginManifest] = {}

    def discover_plugins(self) -> dict[str, PluginManifest]:
        """Scans plugin.json files in workspace or plugins directory."""
        candidates = [
            self.workspace_root / "plugin.json",
            *list(self.workspace_root.glob("plugins/*/plugin.json")),
            *list(self.workspace_root.glob("capability_plugins/*/plugin.json")),
        ]

        for p_file in candidates:
            if p_file.exists():
                try:
                    data = json.loads(p_file.read_text(encoding="utf-8"))
                    manifest = PluginManifest.from_dict(data)
                    self._plugins[manifest.name] = manifest
                except (json.JSONDecodeError, KeyError, OSError, TypeError):
                    continue

        return dict(self._plugins)

    def get_plugin(self, name: str) -> PluginManifest | None:
        return self._plugins.get(name)
