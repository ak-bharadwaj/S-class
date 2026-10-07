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


def _strip_comments(text: str) -> str:
    pattern = re.compile(
        r'("(?:\\.|[^"\\])*")|//.*?$|/\*.*?\*/',
        re.MULTILINE | re.DOTALL
    )
    def replacer(match):
        if match.group(1):
            return match.group(1)
        return ""
    cleaned = pattern.sub(replacer, text)
    cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
    return cleaned


def _merge_hook_list(existing_list: list, new_entry: dict, identity_marker: str) -> list:
    """Merges new hook into existing hook list without deleting user's own hooks."""
    result = list(existing_list)
    for idx, item in enumerate(result):
        if isinstance(item, dict):
            sub_hooks = item.get("hooks", [])
            if any(identity_marker in str(h.get("command", "")) for h in sub_hooks):
                result[idx] = new_entry
                return result
    result.insert(0, new_entry)
    return result


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

        existing_cfg: Dict[str, Any] = {}
        if os.path.exists(self.hooks_file):
            # Backup first (Item 36)
            try:
                shutil.copy2(self.hooks_file, self.hooks_file + ".bak")
            except Exception:
                pass

            try:
                with open(self.hooks_file, "r", encoding="utf-8") as f:
                    raw = f.read()
                cleaned = _strip_comments(raw).strip()
                existing_cfg = json.loads(cleaned) if cleaned else {}
            except Exception as e:
                # Refuse to overwrite unparseable configuration file (Item 36)
                logger.warning(f"Refusing to overwrite unparseable hooks file '{self.hooks_file}': {e}")
                return self.hooks_file

        py_bin = (sys.executable or "python").replace("\\", "/")
        cmd_str = f'"{py_bin}" "{norm_runner}" --platform codex --event-type pre_tool_use'
        cmd_win = f'"{py_bin}" "{norm_runner}" --platform codex --event-type pre_tool_use'

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
                    "command": f'"{py_bin}" "{norm_runner}" --platform codex --event-type permission',
                    "commandWindows": f'"{py_bin}" "{norm_runner}" --platform codex --event-type permission',
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
