"""
S-Class V13: Windsurf / Cascade Hook Adapter (adapters/windsurf.py)

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
        """Writes .windsurf/hooks.json with pre/post hooks."""
        os.makedirs(self.windsurf_dir, exist_ok=True)
        r_path = runner_path or os.path.join(self.workspace_dir, "hook_runner.py")
        norm_runner = r_path.replace("\\", "/")

        cfg: Dict[str, Any] = {
            "hooks": {
                "pre_write_code": [
                    {
                        "command": f'python "{norm_runner}" --platform windsurf --event-type pre_write_code',
                    }
                ],
                "pre_run_command": [
                    {
                        "command": f'python "{norm_runner}" --platform windsurf --event-type pre_run_command',
                    }
                ],
                "post_write_code": [
                    {
                        "command": f'python "{norm_runner}" --platform windsurf --event-type post_write_code',
                    }
                ],
            }
        }

        with open(self.hooks_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

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
