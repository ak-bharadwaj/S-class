"""
S-Class v6: Cursor (1.7+) Hook Adapter (adapters/cursor.py)

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
import logging
from typing import Dict, Any, Optional
from adapters.common import backup_config_file, safe_read_json_config, get_python_executable, merge_hook_list

logger = logging.getLogger("sclass_cursor_adapter")


class CursorAdapter:
    """Installs and configures Cursor 1.7+ hooks non-destructively."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self.cursor_dir = os.path.join(self.workspace_dir, ".cursor")
        self.hooks_file = os.path.join(self.cursor_dir, "hooks.json")

    def install_hooks(self, runner_path: Optional[str] = None, strict: bool = False) -> str:
        """Writes or updates .cursor/hooks.json non-destructively with event-specific hook definitions."""
        from adapters import resolve_runner_path
        os.makedirs(self.cursor_dir, exist_ok=True)
        r_path = resolve_runner_path(self.workspace_dir, runner_path)
        norm_runner = r_path.replace("\\", "/")
        py_bin = get_python_executable()

        strict_flag = " --strict" if strict else ""

        backup_config_file(self.hooks_file)

        existing_cfg = safe_read_json_config(self.hooks_file)
        if existing_cfg is None:
            logger.warning(f"Refusing to overwrite unparseable hooks file '{self.hooks_file}'")
            return self.hooks_file

        if "version" not in existing_cfg:
            existing_cfg["version"] = 1

        hooks = existing_cfg.setdefault("hooks", {})

        sclass_hooks_spec = {
            "beforeReadFile": {
                "command": f'"{py_bin}" "{norm_runner}" --platform cursor --event-type beforeReadFile{strict_flag}',
                "timeout": 10,
            },
            "beforeShellExecution": {
                "command": f'"{py_bin}" "{norm_runner}" --platform cursor --event-type beforeShellExecution{strict_flag}',
                "timeout": 15,
            },
            "beforeMCPExecution": {
                "command": f'"{py_bin}" "{norm_runner}" --platform cursor --event-type beforeMCPExecution{strict_flag}',
                "timeout": 15,
            },
            "preToolUse": {
                "command": f'"{py_bin}" "{norm_runner}" --platform cursor --event-type preToolUse{strict_flag}',
                "timeout": 15,
            },
            "afterFileEdit": {
                "command": f'"{py_bin}" "{norm_runner}" --platform cursor --event-type afterFileEdit{strict_flag}',
                "timeout": 10,
            },
            "beforeSubmitPrompt": {
                "command": f'"{py_bin}" "{norm_runner}" --platform cursor --event-type beforeSubmitPrompt{strict_flag}',
                "timeout": 5,
            },
        }

        # Idempotently merge each hook entry, preserving user's own custom hooks
        for event_name, hook_entry in sclass_hooks_spec.items():
            curr_list = hooks.get(event_name, [])
            if not isinstance(curr_list, list):
                curr_list = [curr_list] if isinstance(curr_list, dict) else []
            hooks[event_name] = merge_hook_list(curr_list, hook_entry, identity_marker="--platform cursor")

        with open(self.hooks_file, "w", encoding="utf-8") as f:
            json.dump(existing_cfg, f, indent=2)

        return self.hooks_file

    def check_desync(self, local_phase: str, local_task_id: Optional[str] = None) -> tuple[bool, str]:
        """Detects if Cursor state has drifted from authoritative kernel state."""
        from adapters.state_sync import StateSyncManager
        return StateSyncManager.check_desync(local_phase, self.workspace_dir, local_task_id)

    def sync_state(self, local_phase: Optional[str] = None) -> Dict[str, Any]:
        """Synchronizes Cursor plugin state with authoritative kernel state."""
        from adapters.state_sync import StateSyncManager
        if local_phase:
            is_desynced, msg = StateSyncManager.check_desync(local_phase, self.workspace_dir)
            if is_desynced:
                logger.warning(f"[CursorAdapter] State desync detected: {msg}")
        return StateSyncManager.reconcile(self.workspace_dir)

