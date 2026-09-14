"""
S-Class Product: Coding Agent Platform Auto-Discovery (RC.12).

Auto-detects installed coding agent platforms:
- OpenAI Codex
- Anthropic Claude Code
- Google Antigravity
- Anysphere Cursor
- GitHub Copilot CLI
- Codeium Windsurf
And configures appropriate normalized adapters automatically.
"""

from __future__ import annotations
import os
import shutil
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from sclass.integrations.base import (
    AdapterStatus,
    AdapterCapabilities,
    BasePlatformAdapter,
)


@dataclass(frozen=True)
class DiscoveredProvider:
    """Discovered coding agent platform with honest installation tier."""
    platform_id: str
    name: str
    status: AdapterStatus
    binary_path: Optional[str] = None
    config_path: Optional[str] = None
    detected_by: str = "probe"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform_id": self.platform_id,
            "name": self.name,
            "status": self.status.value,
            "binary_path": self.binary_path,
            "config_path": self.config_path,
            "detected_by": self.detected_by,
            "metadata": dict(self.metadata),
        }


class ProviderDiscovery:
    """
    Scans the host system and workspace to discover available coding agent platforms
    and configure their S-Class integration adapters.
    """

    PLATFORM_PROFILES = [
        {
            "id": "codex",
            "name": "OpenAI Codex",
            "binary": "codex",
            "home": "~/.codex",
            "env_vars": ["CODEX_HOME", "OPENAI_API_KEY"],
            "protocol": "acp",
        },
        {
            "id": "claude_code",
            "name": "Anthropic Claude Code",
            "binary": "claude",
            "home": "~/.claude",
            "env_vars": ["CLAUDE_HOME", "ANTHROPIC_API_KEY"],
            "protocol": "cli",
        },
        {
            "id": "antigravity",
            "name": "Google Antigravity",
            "binary": "antigravity",
            "home": "~/.antigravity",
            "env_vars": ["ANTIGRAVITY_AGENT_ID", "GEMINI_API_KEY"],
            "workspace_dir": ".agents",
            "protocol": "native_hook",
        },
        {
            "id": "cursor",
            "name": "Anysphere Cursor",
            "binary": "cursor",
            "home": "~/.cursor",
            "env_vars": ["CURSOR_HOME"],
            "protocol": "native_hook",
        },
        {
            "id": "copilot",
            "name": "GitHub Copilot",
            "binary": "gh",
            "home": "~/.config/github-copilot",
            "env_vars": ["GITHUB_TOKEN", "GH_COPILOT_TOKEN"],
            "protocol": "cli",
        },
        {
            "id": "windsurf",
            "name": "Codeium Windsurf",
            "binary": "windsurf",
            "home": "~/.windsurf",
            "env_vars": ["WINDSURF_HOME"],
            "protocol": "native_hook",
        },
    ]

    def __init__(self, default_mode: str = "enforce"):
        self.default_mode = default_mode

    def probe_platform(self, spec: Dict[str, Any], workspace_dir: Optional[str] = None) -> DiscoveredProvider:
        """Probes presence of a single platform."""
        platform_id = spec["id"]
        name = spec["name"]
        bin_target = spec.get("binary")
        home_target = os.path.expanduser(spec.get("home", ""))
        env_vars = spec.get("env_vars", [])
        ws_marker = spec.get("workspace_dir")

        # 1. Check Binary first (installed on system path)
        bin_path = shutil.which(bin_target) if bin_target else None
        if bin_path:
            return DiscoveredProvider(
                platform_id=platform_id,
                name=name,
                status=AdapterStatus.INSTALLED,
                binary_path=bin_path,
                config_path=home_target if os.path.exists(home_target) else None,
                detected_by="binary",
                metadata={"protocol": spec.get("protocol", "generic")},
            )

        # 2. Check Workspace Marker (config/context marker only -> CONFIGURED, not INSTALLED)
        if workspace_dir and ws_marker:
            marker_path = os.path.join(workspace_dir, ws_marker)
            if os.path.exists(marker_path):
                return DiscoveredProvider(
                    platform_id=platform_id,
                    name=name,
                    status=AdapterStatus.CONFIGURED,
                    config_path=marker_path,
                    detected_by="workspace_marker",
                    metadata={"protocol": spec.get("protocol", "generic")},
                )

        # 3. Check Environment Variables (API key / env only -> CONFIGURED, not INSTALLED)
        active_env = [ev for ev in env_vars if os.getenv(ev)]
        if active_env:
            return DiscoveredProvider(
                platform_id=platform_id,
                name=name,
                status=AdapterStatus.CONFIGURED,
                detected_by=f"env:{active_env[0]}",
                metadata={"active_env": active_env, "protocol": spec.get("protocol", "generic")},
            )

        # 4. Check Home / Config Path (~/.codex, ~/.claude, etc.) -> CONFIGURED
        if home_target and os.path.exists(home_target):
            return DiscoveredProvider(
                platform_id=platform_id,
                name=name,
                status=AdapterStatus.CONFIGURED,
                config_path=home_target,
                detected_by="config_dir",
                metadata={"protocol": spec.get("protocol", "generic")},
            )

        # Not detected
        return DiscoveredProvider(
            platform_id=platform_id,
            name=name,
            status=AdapterStatus.NOT_DETECTED,
            detected_by="not_detected",
            metadata={"protocol": spec.get("protocol", "generic")},
        )

    def discover_all(self, workspace_dir: Optional[str] = None) -> List[DiscoveredProvider]:
        """Probes and lists all registered platforms and their current status."""
        return [self.probe_platform(spec, workspace_dir=workspace_dir) for spec in self.PLATFORM_PROFILES]

    def discover_installed(self, workspace_dir: Optional[str] = None) -> List[DiscoveredProvider]:
        """Returns only platforms verified as installed or connected."""
        all_provs = self.discover_all(workspace_dir=workspace_dir)
        return [p for p in all_provs if p.status in (AdapterStatus.INSTALLED, AdapterStatus.CONNECTED, AdapterStatus.VERIFIED)]

    def get_primary_platform(self, workspace_dir: Optional[str] = None) -> str:
        """
        Determines the most likely active platform in the current environment.
        Defaults to 'antigravity' or 'generic' if none discovered.
        """
        installed = self.discover_installed(workspace_dir=workspace_dir)
        if installed:
            return installed[0].platform_id
        return "generic"

    def create_adapter(
        self,
        platform_id: str,
        workspace_dir: str,
        mode: Optional[str] = None,
    ) -> BasePlatformAdapter:
        """
        Creates a normalized S-Class adapter for the requested platform.
        Fails closed with ADAPTER_ERROR / UNAVAILABLE if adapter initialization fails.
        Never silently substitutes a generic adapter for a requested known platform.
        """
        pid = platform_id.strip().lower()
        active_mode = mode or self.default_mode

        if pid == "cursor":
            try:
                from sclass.integrations.cursor.adapter import CursorAdapter
                return CursorAdapter(workspace_dir=workspace_dir, mode=active_mode)
            except Exception as ex:
                raise RuntimeError(f"ADAPTER_ERROR: Failed to initialize Cursor adapter: {ex}")
        elif pid == "codex":
            try:
                from sclass.integrations.codex.adapter import CodexAdapter
                return CodexAdapter(workspace_dir=workspace_dir, mode=active_mode)
            except Exception as ex:
                raise RuntimeError(f"ADAPTER_ERROR: Failed to initialize Codex adapter: {ex}")
        elif pid in ("claude", "claude_code"):
            try:
                from sclass.integrations.claude.adapter import ClaudeCodeAdapter
                return ClaudeCodeAdapter(workspace_dir=workspace_dir, mode=active_mode)
            except Exception as ex:
                raise RuntimeError(f"ADAPTER_ERROR: Failed to initialize Claude Code adapter: {ex}")
        elif pid == "antigravity":
            return BasePlatformAdapter(
                workspace_dir=workspace_dir,
                platform_id="antigravity",
                mode=active_mode,
                capabilities=AdapterCapabilities(native_protocol="native_hook"),
            )
        elif pid in ("generic", "base", "default"):
            return BasePlatformAdapter(
                workspace_dir=workspace_dir,
                platform_id=pid,
                mode=active_mode,
                capabilities=AdapterCapabilities(native_protocol="generic"),
            )

        raise ValueError(f"UNAVAILABLE: Unknown or unsupported platform '{pid}'. Generic adapter not substituted.")
