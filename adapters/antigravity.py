"""
S-Class V13: Google Antigravity / Gemini Hook Adapter (adapters/antigravity.py)

Generates .agents/hooks.json with native Gemini dialect:
- BeforeTool: intercepts tool executions (crucial: NOT PreToolUse)
- AfterTool: post-tool inspection / retry trigger
- SessionStart: agent initialization hook
- AGENTS.md / GEMINI.md projection parity
"""

from __future__ import annotations
import os
import json
from typing import Dict, Any, Optional


class AntigravityAdapter:
    """Installs and configures Google Antigravity hooks in native Gemini dialect."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self.agents_dir = os.path.join(self.workspace_dir, ".agents")
        self.hooks_file = os.path.join(self.agents_dir, "hooks.json")

    def install_hooks(self, runner_path: Optional[str] = None, strict: bool = False) -> str:
        """Writes .agents/hooks.json using native BeforeTool/AfterTool event dialect."""
        from adapters import resolve_runner_path
        os.makedirs(self.agents_dir, exist_ok=True)
        r_path = resolve_runner_path(self.workspace_dir, runner_path)
        norm_runner = r_path.replace("\\", "/")

        cfg: Dict[str, Any] = {
            "version": 1,
            "dialect": "gemini_native",
            "hooks": [
                {
                    "event": "BeforeTool",
                    "matcher": ".*",
                    "command": f'python "{norm_runner}" --platform antigravity --event-type BeforeTool',
                    "blocking": strict,
                    "timeoutSec": 60,
                },
                {
                    "event": "AfterTool",
                    "matcher": ".*",
                    "command": f'python "{norm_runner}" --platform antigravity --event-type AfterTool',
                    "blocking": False,
                    "timeoutSec": 15,
                },
                {
                    "event": "SessionStart",
                    "command": f'python "{norm_runner}" --platform antigravity --event-type SessionStart',
                    "blocking": False,
                    "timeoutSec": 10,
                },
            ],
        }

        with open(self.hooks_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

        return self.hooks_file
