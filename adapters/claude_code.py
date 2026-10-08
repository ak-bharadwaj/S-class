"""
S-Class v6: Claude Code Hook Adapter (adapters/claude_code.py)

Generates .claude/settings.local.json configuration with:
- PreToolUse: Matches all tool executions, invokes hook_runner.py
- UserPromptSubmit: Intercepts prompt submissions
- SessionStart: Session initialization hook
Timeout is set to generous 120s to prevent silent bypass.
"""

from __future__ import annotations
import os
import json
import shutil
import re
import logging
import sys
from typing import Dict, Any, Optional

logger = logging.getLogger("sclass_claude_adapter")

from adapters.common import strip_comments as _strip_comments, merge_hook_list as _merge_hook_list


class ClaudeCodeAdapter:
    """Installs and configures Claude Code hooks non-destructively."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self.claude_dir = os.path.join(self.workspace_dir, ".claude")
        self.settings_file = os.path.join(self.claude_dir, "settings.local.json")

    def install_hooks(self, runner_path: Optional[str] = None, strict: bool = False) -> str:
        """Writes or updates .claude/settings.local.json with hook bindings non-destructively."""
        from adapters import resolve_runner_path
        os.makedirs(self.claude_dir, exist_ok=True)
        r_path = resolve_runner_path(self.workspace_dir, runner_path)
        norm_runner = r_path.replace("\\", "/")

        existing_cfg: Dict[str, Any] = {}
        if os.path.exists(self.settings_file):
            # Backup first (Item 36)
            try:
                shutil.copy2(self.settings_file, self.settings_file + ".bak")
            except Exception as e:
                logger.debug(f"[ClaudeCodeAdapter] Failed to backup settings file: {e}")

            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    raw = f.read()
                cleaned = _strip_comments(raw).strip()
                existing_cfg = json.loads(cleaned) if cleaned else {}
            except Exception as e:
                # Refuse to overwrite unparseable configuration file (Item 36)
                logger.warning(f"Refusing to overwrite unparseable settings file '{self.settings_file}': {e}")
                return self.settings_file

        python_bin = (sys.executable or "python").replace("\\", "/")
        hooks = existing_cfg.setdefault("hooks", {})

        sclass_pre_tool = {
            "matcher": ".*",
            "hooks": [
                {
                    "type": "command",
                    "command": f'"{python_bin}" "{norm_runner}" --platform claude_code --event-type pre_tool_use',
                    "timeout": 120,
                    "statusMessage": "S-Class Governance Gate",
                }
            ],
        }
        sclass_prompt = {
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": f'"{python_bin}" "{norm_runner}" --platform claude_code --event-type user_prompt',
                    "timeout": 15,
                }
            ],
        }
        sclass_session = {
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": f'"{python_bin}" "{norm_runner}" --platform claude_code --event-type session_start',
                    "timeout": 15,
                }
            ],
        }

        # Non-destructively merge hooks preserving existing user hooks (Item 36)
        hooks["PreToolUse"] = _merge_hook_list(hooks.get("PreToolUse", []), sclass_pre_tool, "hook_runner")
        hooks["UserPromptSubmit"] = _merge_hook_list(hooks.get("UserPromptSubmit", []), sclass_prompt, "hook_runner")
        hooks["SessionStart"] = _merge_hook_list(hooks.get("SessionStart", []), sclass_session, "hook_runner")

        existing_cfg["hooks"] = hooks
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(existing_cfg, f, indent=2)

        return self.settings_file
