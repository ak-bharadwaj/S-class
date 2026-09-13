"""
S-Class V13: Claude Code Hook Adapter (adapters/claude_code.py)

Generates .claude/settings.local.json configuration with:
- PreToolUse: Matches all tool executions, invokes hook_runner.py
- UserPromptSubmit: Intercepts prompt submissions
- SessionStart: Session initialization hook
Timeout is set to generous 120s to prevent silent bypass.
"""

from __future__ import annotations
import os
import json
from typing import Dict, Any, Optional


class ClaudeCodeAdapter:
    """Installs and configures Claude Code hooks."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self.claude_dir = os.path.join(self.workspace_dir, ".claude")
        self.settings_file = os.path.join(self.claude_dir, "settings.local.json")

    def install_hooks(self, runner_path: Optional[str] = None, strict: bool = False) -> str:
        """Writes or updates .claude/settings.local.json with hook bindings."""
        from adapters import resolve_runner_path
        os.makedirs(self.claude_dir, exist_ok=True)
        r_path = resolve_runner_path(self.workspace_dir, runner_path)
        norm_runner = r_path.replace("\\", "/")

        existing_cfg: Dict[str, Any] = {}
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    existing_cfg = json.load(f)
            except Exception:
                existing_cfg = {}

        hooks = existing_cfg.get("hooks", {})
        hooks["PreToolUse"] = [
            {
                "matcher": ".*",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'python "{norm_runner}" --platform claude_code --event-type pre_tool_use',
                        "timeout": 120,
                        "statusMessage": "S-Class Governance Gate",
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
                        "command": f'python "{norm_runner}" --platform claude_code --event-type user_prompt',
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
                        "command": f'python "{norm_runner}" --platform claude_code --event-type session_start',
                        "timeout": 15,
                    }
                ],
            }
        ]

        existing_cfg["hooks"] = hooks
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(existing_cfg, f, indent=2)

        return self.settings_file
