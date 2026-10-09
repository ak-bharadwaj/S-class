"""
S-Class v6: GitHub Copilot Hook Adapter (adapters/copilot.py)

Generates:
1. .github/hooks/sclass.json: Real executable preToolUse hook
2. .github/copilot-instructions.md: Advisory prompt context injection

Surface Scoping:
- Local Copilot CLI sessions execute .github/hooks/*.json immediately from workspace.
- Remote GitHub Copilot Cloud Agent requires committing .github/hooks/*.json to default branch.
"""

from __future__ import annotations
import os
import json
from typing import Dict, Any, Optional


class CopilotAdapter:
    """Installs and configures GitHub Copilot hooks and instructions."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self.github_dir = os.path.join(self.workspace_dir, ".github")
        self.hooks_dir = os.path.join(self.github_dir, "hooks")
        self.hooks_file = os.path.join(self.hooks_dir, "sclass.json")
        self.instructions_file = os.path.join(self.github_dir, "copilot-instructions.md")

    def install_hooks(self, runner_path: Optional[str] = None, strict: bool = False) -> str:
        """Writes or updates .github/hooks/sclass.json non-destructively."""
        from adapters import resolve_runner_path
        from adapters.common import backup_config_file, safe_read_json_config, get_python_executable, merge_hook_list
        os.makedirs(self.hooks_dir, exist_ok=True)
        r_path = resolve_runner_path(self.workspace_dir, runner_path)
        norm_runner = r_path.replace("\\", "/")
        py_bin = get_python_executable()

        strict_flag = " --strict" if strict else ""

        backup_config_file(self.hooks_file)

        existing_cfg = safe_read_json_config(self.hooks_file)
        if existing_cfg is None:
            import logging
            logging.getLogger("sclass_copilot_adapter").warning(f"Refusing to overwrite unparseable hooks file '{self.hooks_file}'")
            return self.hooks_file

        if "version" not in existing_cfg:
            existing_cfg["version"] = 1

        hooks = existing_cfg.setdefault("hooks", {})

        sclass_pre_tool = {
            "type": "command",
            "matcher": "edit|create|apply_patch|write_to_file",
            "bash": f'"{py_bin}" "{norm_runner}" --platform copilot --event-type pre_tool_use{strict_flag}',
            "powershell": f'"{py_bin}" "{norm_runner}" --platform copilot --event-type pre_tool_use{strict_flag}',
            "timeoutSec": 60,
        }
        sclass_session_start = {
            "type": "command",
            "bash": f'"{py_bin}" "{norm_runner}" --platform copilot --event-type session_start{strict_flag}',
            "powershell": f'"{py_bin}" "{norm_runner}" --platform copilot --event-type session_start{strict_flag}',
            "timeoutSec": 10,
        }

        pre_list = hooks.get("preToolUse", [])
        if not isinstance(pre_list, list):
            pre_list = [pre_list] if isinstance(pre_list, dict) else []
        hooks["preToolUse"] = merge_hook_list(pre_list, sclass_pre_tool, identity_marker="--platform copilot")

        session_list = hooks.get("sessionStart", [])
        if not isinstance(session_list, list):
            session_list = [session_list] if isinstance(session_list, dict) else []
        hooks["sessionStart"] = merge_hook_list(session_list, sclass_session_start, identity_marker="--platform copilot")

        with open(self.hooks_file, "w", encoding="utf-8") as f:
            json.dump(existing_cfg, f, indent=2)

        return self.hooks_file

    def generate_instructions(self, project_context: str = "") -> str:
        """Writes .github/copilot-instructions.md advisory markdown."""
        os.makedirs(self.github_dir, exist_ok=True)
        content = f"""# S-Class Governance: GitHub Copilot Instructions

> [!IMPORTANT]
> This repository is governed by the S-Class authoritative execution microkernel.

## Architectural Governance
- Do not commit hardcoded secrets, API tokens, or private keys.
- Avoid insecure dynamic execution (`eval()`, `exec()`, `pickle.loads()`).
- All architectural decisions must satisfy evidence gates.

{project_context}
"""
        with open(self.instructions_file, "w", encoding="utf-8") as f:
            f.write(content)

        return self.instructions_file

    def check_desync(self, local_phase: str, local_task_id: Optional[str] = None) -> tuple[bool, str]:
        """Detects if Copilot state has drifted from authoritative kernel state."""
        from adapters.state_sync import StateSyncManager
        return StateSyncManager.check_desync(local_phase, self.workspace_dir, local_task_id)

    def sync_state(self, local_phase: Optional[str] = None) -> Dict[str, Any]:
        """Synchronizes Copilot plugin state with authoritative kernel state."""
        from adapters.state_sync import StateSyncManager
        if local_phase:
            is_desynced, msg = StateSyncManager.check_desync(local_phase, self.workspace_dir)
            if is_desynced:
                import logging
                logging.getLogger("sclass_copilot_adapter").warning(f"[CopilotAdapter] State desync detected: {msg}")
        return StateSyncManager.reconcile(self.workspace_dir)

