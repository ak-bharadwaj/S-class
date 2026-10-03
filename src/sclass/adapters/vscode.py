"""S-Class VS Code Adapter (adapters/vscode.py).

Configures VS Code workspace settings (.vscode/settings.json) and MCP configuration
to bind the IDE with S-Class control plane and stdio MCP server.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class VSCodeAdapter:
    """Configures VS Code workspace settings and MCP server registrations."""

    def __init__(self, workspace_root: Path | str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.vscode_dir = self.workspace_root / ".vscode"
        self.settings_file = self.vscode_dir / "settings.json"
        self.mcp_file = self.workspace_root / ".mcp.json"

    def install_configuration(
        self,
        python_executable: str = "python",
        mcp_script: str | None = None,
    ) -> dict[str, Path]:
        """Writes .vscode/settings.json and workspace .mcp.json for S-Class integration."""
        self.vscode_dir.mkdir(parents=True, exist_ok=True)

        # 1. Workspace settings
        settings: dict[str, Any] = {}
        if self.settings_file.exists():
            try:
                settings = json.loads(self.settings_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                settings = {}

        settings["sclass.enabled"] = True
        settings["sclass.version"] = "6.0.1"
        settings["sclass.enforceGating"] = True
        settings["sclass.dbPath"] = "sclass.sqlite"

        self.settings_file.write_text(json.dumps(settings, indent=2), encoding="utf-8")

        # 2. MCP server registration
        script_path = mcp_script or str(
            (self.workspace_root / "tools" / "mcp" / "sclass_mcp_server.py").resolve()
        )
        mcp_cfg: dict[str, Any] = {
            "mcpServers": {
                "sclass": {
                    "command": python_executable,
                    "args": [script_path],
                    "env": {
                        "SCLASS_INTEGRITY": "development",
                        "PYTHONUNBUFFERED": "1",
                    },
                }
            }
        }
        self.mcp_file.write_text(json.dumps(mcp_cfg, indent=2), encoding="utf-8")

        return {
            "settings": self.settings_file,
            "mcp": self.mcp_file,
        }
