"""
S-Class v6: Windsurf / Cascade Hook Adapter (adapters/windsurf.py)

Generates:
1. .windsurf/hooks.json: pre_write_code, pre_run_command, post_write_code
   Critical Protocol: Windsurf treats exit code 2 as DENY (exit 1 = crash).
2. .windsurfrules: Advisory architectural context file
"""

from __future__ import annotations
import os
import json
from typing import Dict, Any, Optional


class WindsurfAdapter:
    """Installs and configures Windsurf/Cascade hooks and rules."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self.windsurf_dir = os.path.join(self.workspace_dir, ".windsurf")
        self.hooks_file = os.path.join(self.windsurf_dir, "hooks.json")
        self.rules_file = os.path.join(self.workspace_dir, ".windsurfrules")

    def install_hooks(self, runner_path: Optional[str] = None, strict: bool = False) -> str:
        """Writes or updates .windsurf/hooks.json with pre/post hooks non-destructively."""
        from adapters import resolve_runner_path
        from adapters.common import backup_config_file, safe_read_json_config, get_python_executable, merge_hook_list
        os.makedirs(self.windsurf_dir, exist_ok=True)
        r_path = resolve_runner_path(self.workspace_dir, runner_path)
        norm_runner = r_path.replace("\\", "/")
        py_bin = get_python_executable()

        strict_flag = " --strict" if strict else ""

        backup_config_file(self.hooks_file)

        existing_cfg = safe_read_json_config(self.hooks_file)
        if existing_cfg is None:
            import logging
            logging.getLogger("sclass_windsurf_adapter").warning(f"Refusing to overwrite unparseable hooks file '{self.hooks_file}'")
            return self.hooks_file

        hooks = existing_cfg.setdefault("hooks", {})

        sclass_hooks_spec = {
            "pre_write_code": {
                "command": f'"{py_bin}" "{norm_runner}" --platform windsurf --event-type pre_write_code{strict_flag}',
            },
            "pre_run_command": {
                "command": f'"{py_bin}" "{norm_runner}" --platform windsurf --event-type pre_run_command{strict_flag}',
            },
            "post_write_code": {
                "command": f'"{py_bin}" "{norm_runner}" --platform windsurf --event-type post_write_code{strict_flag}',
            },
        }

        for event_name, hook_entry in sclass_hooks_spec.items():
            curr_list = hooks.get(event_name, [])
            if not isinstance(curr_list, list):
                curr_list = [curr_list] if isinstance(curr_list, dict) else []
            hooks[event_name] = merge_hook_list(curr_list, hook_entry, identity_marker="--platform windsurf")

        with open(self.hooks_file, "w", encoding="utf-8") as f:
            json.dump(existing_cfg, f, indent=2)

        return self.hooks_file

    def generate_rules(self, project_context: str = "") -> str:
        """Writes .windsurfrules advisory context."""
        content = f"""# S-Class Governance: Windsurf Rules

> [!IMPORTANT]
> This workspace is governed by the S-Class authoritative execution microkernel.

- Security: Hardcoded secrets and insecure dynamic execution are strictly denied.
- Blast Radius: Avoid modifications with high downstream caller ripple effects.
- Verification: Satisfy all S-Class evidence gates prior to release.

{project_context}
"""
        with open(self.rules_file, "w", encoding="utf-8") as f:
            f.write(content)

        return self.rules_file
