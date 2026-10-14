"""
S-Class v6: OpenAI Codex CLI Hook Adapter (adapters/codex_cli.py)

Generates .codex/hooks.json (or config.toml fallback) with:
- PreToolUse: Intercepts apply_patch, Edit, Write
- PermissionRequest: Intercepts permission elevation
Supports commandWindows key for Windows cmd wrappers if needed.
"""

from __future__ import annotations
import os
import json
import shutil
import re
import logging
import sys
from typing import Dict, Any, Optional

logger = logging.getLogger("sclass_codex_adapter")


from adapters.common import (
    strip_comments as _strip_comments,
    merge_hook_list as _merge_hook_list,
    backup_config_file,
    safe_read_json_config,
    get_python_executable,
)


class CodexCliAdapter:
    """Installs and configures OpenAI Codex CLI hooks non-destructively."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self.codex_dir = os.path.join(self.workspace_dir, ".codex")
        self.hooks_file = os.path.join(self.codex_dir, "hooks.json")

    def install_hooks(self, runner_path: Optional[str] = None, strict: bool = False) -> str:
        """Writes .codex/hooks.json with hook bindings non-destructively."""
        from adapters import resolve_runner_path
        os.makedirs(self.codex_dir, exist_ok=True)
        r_path = resolve_runner_path(self.workspace_dir, runner_path)
        norm_runner = r_path.replace("\\", "/")

        backup_config_file(self.hooks_file)

        existing_cfg = safe_read_json_config(self.hooks_file)
        if existing_cfg is None:
            # Refuse to overwrite unparseable configuration file (Item 36)
            logger.warning(f"Refusing to overwrite unparseable hooks file '{self.hooks_file}'")
            return self.hooks_file

        py_bin = get_python_executable()
        strict_flag = " --strict" if strict else ""
        cmd_str = f'"{py_bin}" "{norm_runner}" --platform codex --event-type pre_tool_use{strict_flag}'
        cmd_win = f'"{py_bin}" "{norm_runner}" --platform codex --event-type pre_tool_use{strict_flag}'
        perm_cmd = f'"{py_bin}" "{norm_runner}" --platform codex --event-type permission{strict_flag}'

        hooks = existing_cfg.setdefault("hooks", {})

        sclass_pre_tool = {
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
        sclass_perm = {
            "matcher": ".*",
            "hooks": [
                {
                    "type": "command",
                    "command": perm_cmd,
                    "commandWindows": perm_cmd,
                    "timeout": 30,
                }
            ],
        }

        # Non-destructively merge hooks preserving existing user hooks (Item 36)
        hooks["PreToolUse"] = _merge_hook_list(hooks.get("PreToolUse", []), sclass_pre_tool, "hook_runner")
        hooks["PermissionRequest"] = _merge_hook_list(hooks.get("PermissionRequest", []), sclass_perm, "hook_runner")

        existing_cfg["hooks"] = hooks
        with open(self.hooks_file, "w", encoding="utf-8") as f:
            json.dump(existing_cfg, f, indent=2)

        return self.hooks_file
