"""
S-Class: Google Antigravity / Gemini Hook Adapter (adapters/antigravity.py)

Generates .agents/hooks.json with true Antigravity schema:
- Top-level named hook "sclass-enforcement-guard"
- PreToolUse for interception
- Stop for completion gating
"""

from __future__ import annotations
import os
import json
import logging
from typing import Dict, Any, Optional
from adapters.common import backup_config_file, safe_read_json_config, get_python_executable

logger = logging.getLogger("sclass_antigravity_adapter")


class AntigravityAdapter:
    """Installs and configures Google Antigravity hooks in native schema."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self.agents_dir = os.path.join(self.workspace_dir, ".agents")
        self.hooks_file = os.path.join(self.agents_dir, "hooks.json")

    def install_hooks(self, runner_path: Optional[str] = None, strict: bool = False) -> str:
        """Writes or updates .agents/hooks.json non-destructively using true Antigravity schema."""
        from adapters import resolve_runner_path
        os.makedirs(self.agents_dir, exist_ok=True)
        r_path = resolve_runner_path(self.workspace_dir, runner_path)
        norm_runner = r_path.replace("\\", "/")
        py_bin = get_python_executable()
        
        strict_flag = " --strict" if strict else ""

        # Backup existing file before modifications (Item 36)
        backup_config_file(self.hooks_file)

        existing_cfg = safe_read_json_config(self.hooks_file)
        if existing_cfg is None:
            logger.warning(f"Refusing to overwrite unparseable hooks file '{self.hooks_file}'")
            return self.hooks_file

        sclass_guard = {
            "PreToolUse": [
                {
                    "matcher": "write_to_file|replace_file_content|run_command",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f'"{py_bin}" "{norm_runner}" --platform antigravity --event-type PreToolUse{strict_flag}',
                            "timeout": 15,
                        }
                    ],
                }
            ],
            "Stop": [
                {
                    "type": "command",
                    "command": f'"{py_bin}" "{norm_runner}" --platform antigravity --event-type Stop{strict_flag}',
                    "timeout": 15,
                }
            ],
        }

        # Idempotent merge: preserve all existing user hooks, update or insert S-Class guard
        existing_cfg["sclass-enforcement-guard"] = sclass_guard

        with open(self.hooks_file, "w", encoding="utf-8") as f:
            json.dump(existing_cfg, f, indent=2)

        return self.hooks_file

    def check_desync(self, local_phase: str, local_task_id: Optional[str] = None) -> tuple[bool, str]:
        """Detects if IDE state has drifted from authoritative kernel state."""
        from adapters.state_sync import StateSyncManager
        return StateSyncManager.check_desync(local_phase, self.workspace_dir, local_task_id)

    def sync_state(self, local_phase: Optional[str] = None) -> Dict[str, Any]:
        """Synchronizes IDE plugin state with authoritative kernel state."""
        from adapters.state_sync import StateSyncManager
        if local_phase:
            is_desynced, msg = StateSyncManager.check_desync(local_phase, self.workspace_dir)
            if is_desynced:
                logger.warning(f"[AntigravityAdapter] State desync detected: {msg}")
        return StateSyncManager.reconcile(self.workspace_dir)


