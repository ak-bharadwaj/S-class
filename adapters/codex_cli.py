"""
S-Class V13: OpenAI Codex CLI Hook Adapter (adapters/codex_cli.py)

Generates .codex/hooks.json (or config.toml fallback) with:
- PreToolUse: Intercepts apply_patch, Edit, Write
- PermissionRequest: Intercepts permission elevation
Supports commandWindows key for Windows cmd wrappers if needed.
"""

from __future__ import annotations
import os
import json
from typing import Dict, Any, Optional


class CodexCliAdapter:
    """Installs and configures OpenAI Codex CLI hooks."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self.codex_dir = os.path.join(self.workspace_dir, ".codex")
        self.hooks_file = os.path.join(self.codex_dir, "hooks.json")

    def install_hooks(self, runner_path: Optional[str] = None, strict: bool = False) -> str:
        """Writes .codex/hooks.json with hook bindings."""
        from adapters import resolve_runner_path
        os.makedirs(self.codex_dir, exist_ok=True)
        r_path = resolve_runner_path(self.workspace_dir, runner_path)
        norm_runner = r_path.replace("\\", "/")

        existing_cfg: Dict[str, Any] = {}
        if os.path.exists(self.hooks_file):
            try:
                with open(self.hooks_file, "r", encoding="utf-8") as f:
                    existing_cfg = json.load(f)
            except Exception:
                existing_cfg = {}

        cmd_str = f'python "{norm_runner}" --platform codex --event-type pre_tool_use'
        cmd_win = f'python "{norm_runner}" --platform codex --event-type pre_tool_use'

        hooks = existing_cfg.get("hooks", {})
        hooks["PreToolUse"] = [
            {
                "matcher": ".*",
                "hooks": [
                    {
                        "type": "command",
                        "command": cmd_str,
                        "commandWindows": cmd_win,
                        "timeout": 60,
                    }
                ],
            }
        ]
        hooks["PermissionRequest"] = [
            {
                "matcher": ".*",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'python "{norm_runner}" --platform codex --event-type permission',
                        "commandWindows": f'python "{norm_runner}" --platform codex --event-type permission',
                        "timeout": 30,
                    }
                ],
            }
        ]

        existing_cfg["hooks"] = hooks
        with open(self.hooks_file, "w", encoding="utf-8") as f:
            json.dump(existing_cfg, f, indent=2)

        return self.hooks_file
