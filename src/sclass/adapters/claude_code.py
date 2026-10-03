"""S-Class Claude Code Adapter (adapters/claude_code.py).

Configures Claude Code CLI workspace settings (.claude/settings.local.json)
to intercept pre-tool actions, prompt submissions, and session starts,
routing them to S-Class control plane for admission and gating.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ClaudeCodeAdapter:
    """Configures Claude Code workspace settings to bind with S-Class control plane."""

    def __init__(self, workspace_root: Path | str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.claude_dir = self.workspace_root / ".claude"
        self.settings_file = self.claude_dir / "settings.local.json"

    def install_hooks(self, mcp_server_command: str = "sclass-mcp", strict: bool = True) -> Path:
        """Writes or updates .claude/settings.local.json with S-Class hooks."""
        self.claude_dir.mkdir(parents=True, exist_ok=True)

        existing_cfg: dict[str, Any] = {}
        if self.settings_file.exists():
            try:
                existing_cfg = json.loads(self.settings_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing_cfg = {}

        hooks = existing_cfg.get("hooks", {})
        hooks["PreToolUse"] = [
            {
                "matcher": ".*",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{mcp_server_command} hook pre_tool_use",
                        "timeout": 120,
                        "statusMessage": "S-Class ExecutionGate Governance",
                    }
                ],
            }
        ]
        hooks["UserPromptSubmit"] = [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{mcp_server_command} hook user_prompt",
                        "timeout": 15,
                    }
                ],
            }
        ]
        hooks["SessionStart"] = [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{mcp_server_command} hook session_start",
                        "timeout": 15,
                    }
                ],
            }
        ]

        existing_cfg["hooks"] = hooks
        existing_cfg["sclass_governance"] = {
            "version": "6.0.1",
            "strict": strict,
        }

        self.settings_file.write_text(json.dumps(existing_cfg, indent=2), encoding="utf-8")
        return self.settings_file
