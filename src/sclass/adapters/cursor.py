"""S-Class Cursor Adapter (adapters/cursor.py).

Configures Cursor IDE (1.7+) workspace hooks to route agent file operations,
terminal commands, and prompt submissions through S-Class governance and MCP server.
Zero independent authority; all validations route through S-Class control plane.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CursorAdapter:
    """Configures Cursor IDE hooks to bind with S-Class control plane."""

    def __init__(self, workspace_root: Path | str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.cursor_dir = self.workspace_root / ".cursor"
        self.hooks_file = self.cursor_dir / "hooks.json"

    def install_hooks(self, mcp_server_command: str = "sclass-mcp", strict: bool = True) -> Path:
        """Write .cursor/hooks.json routing actions through S-Class.

        Parameters
        ----------
        mcp_server_command : str
            The executable command to invoke the S-Class MCP / CLI bridge.
        strict : bool
            Whether to fail-closed on verification errors.
        """
        self.cursor_dir.mkdir(parents=True, exist_ok=True)

        config: dict[str, Any] = {
            "version": 1,
            "governance": {
                "system": "sclass-v6.0.1",
                "strict": strict,
            },
            "hooks": {
                "beforeReadFile": [
                    {
                        "command": f"{mcp_server_command} hook beforeReadFile",
                        "timeout": 10,
                    }
                ],
                "beforeShellExecution": [
                    {
                        "command": f"{mcp_server_command} hook beforeShellExecution",
                        "timeout": 15,
                    }
                ],
                "beforeMCPExecution": [
                    {
                        "command": f"{mcp_server_command} hook beforeMCPExecution",
                        "timeout": 15,
                    }
                ],
                "preToolUse": [
                    {
                        "command": f"{mcp_server_command} hook preToolUse",
                        "timeout": 15,
                    }
                ],
                "afterFileEdit": [
                    {
                        "command": f"{mcp_server_command} hook afterFileEdit",
                        "timeout": 10,
                    }
                ],
                "beforeSubmitPrompt": [
                    {
                        "command": f"{mcp_server_command} hook beforeSubmitPrompt",
                        "timeout": 5,
                    }
                ],
            },
        }

        self.hooks_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return self.hooks_file
