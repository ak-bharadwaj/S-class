"""
S-Class V13: Cursor (1.7+) Hook Adapter (adapters/cursor.py)

Generates .cursor/hooks.json with version: 1 format.
Binds discrete events:
- beforeReadFile: file inspection gate (stdout JSON response)
- beforeShellExecution: terminal command gate
- beforeMCPExecution: MCP tool invocation gate
- preToolUse: general agent action gate
- beforeSubmitPrompt: user prompt filter (warn-only)
- afterFileEdit: post-edit audit hook

Ensures Cursor discrete JSON response shapes are accurately routed.
"""

from __future__ import annotations
import os
import json
from typing import Dict, Any, Optional


class CursorAdapter:
    """Installs and configures Cursor 1.7+ hooks."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self.cursor_dir = os.path.join(self.workspace_dir, ".cursor")
        self.hooks_file = os.path.join(self.cursor_dir, "hooks.json")

    def install_hooks(self, runner_path: Optional[str] = None, strict: bool = False) -> str:
        """Writes .cursor/hooks.json with event-specific hook definitions."""
        os.makedirs(self.cursor_dir, exist_ok=True)
        r_path = runner_path or os.path.join(self.workspace_dir, "hook_runner.py")
        norm_runner = r_path.replace("\\", "/")

        cfg: Dict[str, Any] = {
            "version": 1,
            "hooks": {
                "beforeReadFile": [
                    {
                        "command": f'python "{norm_runner}" --platform cursor --event-type beforeReadFile',
                        "timeout": 10,
                    }
                ],
                "beforeShellExecution": [
                    {
                        "command": f'python "{norm_runner}" --platform cursor --event-type beforeShellExecution',
                        "timeout": 15,
                    }
                ],
                "beforeMCPExecution": [
                    {
                        "command": f'python "{norm_runner}" --platform cursor --event-type beforeMCPExecution',
                        "timeout": 15,
                    }
                ],
                "preToolUse": [
                    {
                        "command": f'python "{norm_runner}" --platform cursor --event-type preToolUse',
                        "timeout": 15,
                    }
                ],
                "afterFileEdit": [
                    {
                        "command": f'python "{norm_runner}" --platform cursor --event-type afterFileEdit',
                        "timeout": 10,
                    }
                ],
                "beforeSubmitPrompt": [
                    {
                        "command": f'python "{norm_runner}" --platform cursor --event-type beforeSubmitPrompt',
                        "timeout": 5,
                    }
                ],
            },
        }

        with open(self.hooks_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

        return self.hooks_file
